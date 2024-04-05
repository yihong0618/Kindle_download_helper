import base64
import json
from pathlib import Path
import re
import os
import shutil
import random
import time
from collections import namedtuple
from datetime import datetime
from enum import Enum
from io import BytesIO
from zipfile import ZipFile
import cloudscraper

import requests
from requests.utils import cookiejar_from_dict
import xmltodict
from amazon.ion import simpleion
from moki import extract
from rich import print

from kindle_download_helper import amazon_api
from kindle_download_helper.config import (
    API_MANIFEST_URL,
    DEFAULT_OUT_DEDRM_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_OUT_EPUB_DIR,
)
from kindle_download_helper.user_agents import USER_AGENTS
from kindle_download_helper.dedrm import MobiBook, get_pid_list
from kindle_download_helper.utils import trim_title_suffix, replace_readme_comments
from kindle_download_helper.dedrm.kfxdedrm import KFXZipBook
from kindle_download_helper.third_party.ion import DrmIon, DrmIonVoucher
from kindle_download_helper.third_party.kfxlib import YJ_Book

DEBUG = False
DEFAULT_TIMEOUT = 180
old_send = requests.Session.send


def new_send(*args, **kwargs):
    if kwargs.get("timeout", None) is None:
        kwargs["timeout"] = DEFAULT_TIMEOUT
    return old_send(*args, **kwargs)


requests.Session.send = new_send

# some same logic for kindle
MY_KINDLE_STATS_INFO_HEAD = "## 我的 kindle 回忆\n\n"
KINDLE_TABLE_HEAD = "| ID | Title | Authors | Acquired | Last_READ| Highlight_Count | Price |\n| ---- | ---- | ---- | ---- | ---- |  ---- | ---- | ---- |\n"
KINDLE_STAT_TEMPLATE = "| {id} | {title} | {authors} | {acquired} | {last_read} | {highlight}| {price} | \n"


class Scope(Enum):
    REQUIRED = 1
    PREFERRED = 2
    DEFERRED = 3

    def should_download(self, s: str):
        r = Scope[s.upper()]
        return self.value >= r.value


Request = namedtuple("Request", ["method", "url", "fn", "headers"])


def _build_correlation_id(device, serial, asin, timestamp):
    if timestamp is None:
        timestamp = datetime.utcnow().timestamp()
        timestamp = str(int(timestamp) * 1000)
    return f"Device:{device}:{serial};kindle.EBOK:{asin}:{timestamp}"


class NoKindle:
    def __init__(
        self,
        email,
        password,
        domain,
        out_dir=DEFAULT_OUT_DIR,
        out_dedrm_dir=DEFAULT_OUT_DEDRM_DIR,
        out_epub_dir=DEFAULT_OUT_EPUB_DIR,
        cut_length=76,
    ):
        self.domain = domain
        self.out_dir = out_dir
        self.out_dedrm_dir = out_dedrm_dir
        self.out_epub_dir = out_epub_dir
        self.session = cloudscraper.create_scraper()
        self.ebooks = []
        self.pdocs = []
        self.ebook_library_dict = {}
        self.pdoc_library_dict = {}
        self.cut_length = cut_length
        self.book_name_set = set()
        self.error_price_list = []

        print("Authenticating . . .")
        self.tokens = amazon_api.login(email, password, domain)

    def decrypt_voucher(self, voucher_data):
        with BytesIO(voucher_data) as voucher_data_io:
            for pid in [""] + [self.tokens["device_id"]]:
                for dsn_len, secret_len in [
                    (0, 0),
                    (16, 0),
                    (16, 40),
                    (32, 40),
                    (40, 0),
                    (40, 40),
                ]:
                    if len(pid) == dsn_len + secret_len:
                        break  # split pid into DSN and account secret
                    else:
                        continue
            voucher = DrmIonVoucher(voucher_data_io, pid[:dsn_len], pid[dsn_len:])
            voucher.parse()
            voucher.decryptvoucher()
        return voucher

    def decrypt_kfx(self, kfx_data):
        if kfx_data[:8] != b"\xeaDRMION\xee":
            return kfx_data

        with BytesIO() as decrypted_data:
            DrmIon(BytesIO(kfx_data[8:-8]), lambda name: self.drm_voucher).parse(
                decrypted_data
            )
            return decrypted_data.getvalue()

    def get_resource(self, resource, asin):
        resp = self.session.send(
            amazon_api.signed_request(
                "GET",
                resource["endpoint"]["url"],
                asin=asin,
                tokens=self.tokens,
                request_id=resource["id"],
                request_type=resource["type"],
            )
        )

        filename = resource["id"]
        if resource["type"] == "DRM_VOUCHER":
            filename += ".ast"
        else:
            filename += ".kfx"

        return (resp.content, filename)

    def make_library(self, last_sync=None):
        """Fetches the user library."""
        url = "https://todo-ta-g7g.amazon.com/FionaTodoListProxy/syncMetaData"
        params = {"item_count": 10000}

        if isinstance(last_sync, dict):
            try:
                last_sync = last_sync["sync_time"]
            except KeyError as exc:
                raise ValueError("`last_sync` doesn't contain `sync_time`.") from exc

        if last_sync is not None:
            params["last_sync_time"] = last_sync

        r = self.session.send(
            amazon_api.signed_request(
                "GET",
                url,
                tokens=self.tokens,
            )
        )
        library = xmltodict.parse(r.text)
        library = json.loads(json.dumps(library))
        library = library["response"]["add_update_list"]
        meta_data = library["meta_data"]
        if isinstance(meta_data, dict):
            meta_data = [meta_data]
        ebooks = []
        pdocs = []
        for i in meta_data:
            if i["cde_contenttype"] == "EBOK" and self._is_ebook(i):
                ebooks.append(i)
            elif i["cde_contenttype"] == "PDOC":
                pdocs.append(i)
        unknown_index = 1

        for i in ebooks + pdocs:
            if isinstance(i["title"], dict):
                if i["ASIN"] in self.ebook_library_dict:
                    unknown_index += 1
                book_title = i["title"].get("#text", str(unknown_index))
            else:
                book_title = i["title"]
            book_title = re.sub(
                r"(\（[^)]*\）)|(\([^)]*\))|(\【[^)]*\】)|(\[[^)]*\])|(\s)",
                "",
                book_title,
            )
            book_title = book_title.replace(" ", "")
            is_pdoc = i.get("origins") is None
            if not is_pdoc:
                order_id = i["origins"]["origin"]["id"]
            if i["authors"] is None:
                book_authors = ""
            elif isinstance(i.get("authors", {}).get("author"), list):
                book_authors = i.get("authors", {}).get("author", "")
            else:
                if is_pdoc:
                    book_authors = i["authors"].get("author", "")
                elif isinstance(i["authors"].get("author"), str):
                    book_authors = i["authors"].get("author", "")
                elif i["authors"].get("author", {}).get("#text", ""):
                    book_authors = i["authors"].get("author", {}).get("#text", "")
            if isinstance(book_authors, list):
                if len(book_authors) > 2:
                    book_authors = ",".join(book_authors[:3]) + "..."
                else:
                    book_authors = ",".join(book_authors)
            if is_pdoc:
                self.pdoc_library_dict[i["ASIN"]] = {
                    "title": book_title,
                    "authors": book_authors,
                }
            else:
                self.ebook_library_dict[i["ASIN"]] = {
                    "title": book_title,
                    "order_id": order_id,
                    "purchase_date": i["purchase_date"],
                    "authors": book_authors,
                }
        self.ebooks = ebooks
        self.pdocs = pdocs

    @staticmethod
    def _is_ebook(book_info):
        # https://github.com/yihong0618/Kindle_download_helper/issues/149#issuecomment-1805966855
        # TODO maybe refactor
        if not isinstance(book_info.get("origins"), dict):
            return False
        # https://github.com/yihong0618/Kindle_download_helper/issues/149#issuecomment-1806748160
        if not isinstance(book_info.get("origins", {}).get("origin"), dict):
            return False
        return (
            book_info.get("origins", {}).get("origin", {}).get("type", "") == "Purchase"
        )

    def pdoc_bookmark(self, asin):
        url = f"https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/sidecar?type=PDOC&key={asin}"
        try:
            r = self.session.send(
                amazon_api.signed_request(
                    "GET",
                    url,
                    tokens=self.tokens,
                )
            )
            return r.json()
        except:
            return None

    def make_all_ebook_info(self):
        self.highlight_index = 0
        for asin, v in self.ebook_library_dict.items():
            self.highlight_index += 1
            # for easily generate csv file
            v["last_read"] = ""
            v["highlight_count"] = ""
            manifest, _, info = self.get_book(asin)
            if not manifest:
                print(f"Error to download ASIN: {asin}, error: {str(info)}")
                continue
            print(
                f"[{self.highlight_index} / {len(self.ebooks)}] Getting highlight book: {v['title']}"
            )
            for r in manifest["resources"]:
                if r["type"] == "KINDLE_USER_ANOT":
                    url = r["endpoint"]["url"]
                    book_mark_info = self.ebook_bookmark(url)
                    if not book_mark_info:
                        continue
                    records = book_mark_info["payload"]["records"]
                    if not records:
                        continue
                    for record in records:
                        if record.get("type", "") == "kindle.most_recent_read":
                            v["last_read"] = record.get("creationTime")
                            v["highlight_count"] = (
                                len(records) - 2
                            )  # recent and kindle.lpr are not book mark
                            break

    def _make_all_ebook_price(self, from_index=None):
        # to make sure the website cookies
        amazon_api.refresh(self.tokens)
        s = time.time()
        self.price_index = 0
        for k, v in self.ebook_library_dict.items():
            if isinstance(from_index, int) and self.price_index < from_index:
                self.price_index += 1
                continue
            self.price_index += 1
            if self.price_index % 100 == 0:
                # refresh the cookie to make sure it
                amazon_api.refresh(self.tokens)
                self.session = cloudscraper.create_scraper()
            try:
                self._make_one_book_price(v)
                # spider rule
                time.sleep(1)
            except Exception as e:
                amazon_api.refresh(self.tokens)
                self.session = cloudscraper.create_scraper()
                print(f"{k} error {str(e)}")
                self.error_price_list.append(v)

        l = len(self.ebooks)
        index = 0
        while self.error_price_list and index < l * 2:
            print(f"Left: {len(self.error_price_list)}, Try index: {index}: {l*2}")
            try:
                error_b = self.error_price_list.pop(0)
                self._make_one_book_price(error_b)
            except:
                self.error_price_list.append(error_b)
            # to make sure we do not have forever loop here
            index += 1
        print(f"Get all price cost: {time.time() - s}")
        self.price_index = 0

    def _make_one_book_price(self, v):
        order_id = v.get("order_id")
        if not order_id:
            print(f"No order id for {v['title']}")
            return
        url = f"https://www.amazon.{self.domain}/gp/digital/your-account/order-summary.html?ie=UTF8&orderID={order_id}&print=1"
        self.session.cookies = cookiejar_from_dict(self.tokens["website_cookies"])

        for i in range(3):
            self.session.headers = {
                "User-Agent": random.choice(USER_AGENTS),
            }
            r = self.session.send(
                amazon_api.signed_request(
                    "GET",
                    url,
                    tokens=self.tokens,
                ),
            )
            if r.text.find("developer.amazonservices.com") != -1:
                # another chance.
                print(f"Sleep {i+2}, Another chance for {order_id}")
                time.sleep(i + 2)
            else:
                # if you are on other contries or other languages PR welcome here
                # TODO
                if self.domain == "cn":
                    price_re = re.findall("订单总额(.*)</b>", r.text)
                else:
                    price_re = re.findall("Total for this Order:(.*)</b>", r.text)
                if not price_re:
                    v["price"] = ""
                    return
                price = (
                    price_re[0]
                    .replace("￥", "")
                    .replace(" ", "")
                    .replace("：", "")
                    .replace("$", "")
                    .replace(":", "")
                )
                print(
                    f"[{self.price_index} / {len(self.ebooks)}] Order: {order_id}, Book: {v.get('title', '')} Price: {price} Done"
                )
                v["price"] = price
                break
        else:
            print(f"Order error to error list {order_id}")
            self.error_price_list.append(v)

    def ebook_bookmark(self, sidecar_url):
        r = self.session.send(
            amazon_api.signed_request(
                "GET",
                sidecar_url,
                tokens=self.tokens,
            )
        )
        try:
            # tricky
            return r.json()
        except:
            return None

    @staticmethod
    def _b64ion_to_dict(b64ion: str):
        ion = base64.b64decode(b64ion)
        ion = simpleion.loads(ion)
        return dict(ion)

    def get_book(self, asin):
        manifest_resp = self.session.send(
            amazon_api.signed_request(
                "GET",
                API_MANIFEST_URL + asin.upper(),
                asin=asin,
                tokens=self.tokens,
                request_type="manifest",
            )
        )
        try:
            resources_data = manifest_resp.json()
            if resources_data.get("resources") is None:
                print(f"wrong resource for asin {asin} error: {resources_data}")
                data = self._list_book_consumptions(asin)
                devices_ids_string = ",".join(
                    [
                        i["deviceAccountId"]
                        for i in data["ListConsumptionsResponse"]["result"]["entry"][
                            "value"
                        ]["entry"]["value"]["member"]
                    ]
                )
                print(devices_ids_string)
                self._remove_book_consumptions(asin, devices_ids_string)
                # do it again
                manifest_resp = self.session.send(
                    amazon_api.signed_request(
                        "GET",
                        API_MANIFEST_URL + asin.upper(),
                        asin=asin,
                        tokens=self.tokens,
                        request_type="manifest",
                    )
                )
                resources_data = manifest_resp.json()
                resources = resources_data["resources"]
            else:
                resources = resources_data["resources"]
        except Exception as e:
            print(resources_data, str(e))
            return None, False, str(e)
        # azw3 is not so hard
        drm_voucher_list = [
            resource for resource in resources if resource["type"] == "DRM_VOUCHER"
        ]
        if not drm_voucher_list:
            return resources_data, False, "Succeed"

        drm_voucher = drm_voucher_list[0]
        try:
            self.drm_voucher = self.decrypt_voucher(
                self.get_resource(drm_voucher, asin)[0]
            )
        except:
            print("Could not decrypt the drm voucher!")

        resources_data["responseContext"] = self._b64ion_to_dict(
            resources_data["responseContext"]
        )
        for resource in resources_data["resources"]:
            if "responseContext" in resource:
                resource["responseContext"] = self._b64ion_to_dict(
                    resource["responseContext"]
                )
        return resources_data, True, "Succeed"

    def _list_book_consumptions(self, asin):
        url = f"https://prod.us-east-1.library-relay.kindle.amazon.dev/list-consumptions?contentInput=%5B%7B%22id%22%3A%22{asin}%22%2C%22type%22%3A%22EBook%22%2C%22pid%22%3A%22%22%7D%5D"

        r = requests.get(
            url,
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Authorization": f"Bearer {self.tokens['access_token']}",
                "client": "KindleForiOS",
            },
        )
        try:
            print(xmltodict.parse(r.text))
            return xmltodict.parse(r.text)
        except Exception as e:
            print(e)
            return None

    def _remove_book_consumptions(self, asin, devices_id_string):
        headers = {
            "Authorization": f"Bearer {self.tokens['access_token']}",
            "Upload-Incomplete": "?0",
            "Upload-Draft-Interop-Version": "3",
            "client": "KindleForiOS",
        }

        json_data = {
            "id": asin,
            "type": "EBook",
            "pid": "",
            "deviceAccountIds": devices_id_string,
        }

        try:
            requests.post(
                "https://prod.us-east-1.library-relay.kindle.amazon.dev/remove-consumptions",
                headers=headers,
                json=json_data,
            )
        except Exception as e:
            print(f"Something is wrong for delete devices for {asin} error: {str(e)}")

    def download_book(self, asin, error=None):
        manifest, is_kfx, info = self.get_book(asin)
        if not manifest:
            print(f"Error to download ASIN: {asin}, error: {str(info)}")
            return
        if is_kfx:
            self._download_kfx(manifest, asin)
        else:
            self._download_azw(manifest, asin)

    def _save_to_epub(self, drm_file, out_epub):
        try:
            # save to EPUB
            epub_dir, epub_file = extract(str(drm_file))
            shutil.copy2(epub_file, out_epub)
            # delete it
            shutil.rmtree(epub_dir)
        except Exception as e:
            print(str(e))

    def download_pdoc(self, asin):
        """from mkb79/kindle Downloading personal added documents"""
        url = "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type=PDOC&key={asin}&is_archived_items=1&software_rev=1184370688"
        r = self.session.send(
            amazon_api.signed_request(
                "GET",
                url.format(asin=asin),
                asin=asin,
                tokens=self.tokens,
            )
        )

        book_name = trim_title_suffix(
            self.pdoc_library_dict.get(asin, {}).get("title").encode("utf8").decode()
        )
        print(book_name)
        # we should support the dup name here
        name = book_name
        if book_name in self.book_name_set:
            name = book_name + "_" + asin[:4]
        else:
            self.book_name_set.add(book_name)
        azw3_name = name + ".azw3"
        epub_name = name + ".epub"
        content_bytes = r.content
        if content_bytes[0x3C : 0x3C + 8] != b"BOOKMOBI":
            print(
                f"Book {asin}, {book_name} faild first content {str(content_bytes[:100])}"
            )
            self.book_name_set.discard(book_name)
            return
        out_epub = Path(self.out_epub_dir) / Path(epub_name)
        pdoc_path_drm = Path(self.out_dir) / Path(azw3_name)
        pdoc_path_drm.write_bytes(content_bytes)
        self._save_to_epub(pdoc_path_drm, out_epub)

    def _download_kfx(self, manifest, asin):
        resources = manifest["resources"]
        parts = []
        scope = Scope.DEFERRED
        if isinstance(scope, str):
            try:
                scope = Scope[scope.upper()]
            except KeyError:
                allowed_scopes = [s.name.lower() for s in Scope]
                raise ValueError(
                    "Scope must be in %s, got %s" % (", ".join(allowed_scopes), scope)
                )
        for resource in resources:
            if not scope.should_download(resource["requirement"]):
                continue
            try:
                url = (
                    resource.get("optimalEndpoint", {}).get("directUrl")
                    or resource.get("endpoint")["url"]
                )
            except KeyError:
                raise RuntimeError("No url found for item with id %s." % resource["id"])
            headers = {}
            fn = None

            if resource["type"] == "DRM_VOUCHER":
                fn = resource["id"] + ".voucher"
                correlation_id = _build_correlation_id(
                    "A2A33MVZVPQKHY",
                    self.tokens["device_id"],
                    asin=manifest["content"]["id"],
                    timestamp=manifest["responseContext"]["manifestTime"],
                )

                headers = {
                    "User-Agent": "Kindle/1.0.235280.0.10 CFNetwork/1220.1 Darwin/20.3.0",
                    "X-ADP-AttemptCount": "1",
                    "X-ADP-CorrelationId": correlation_id,
                    "X-ADP-Transport": str(manifest["responseContext"]["transport"]),
                    "x-amzn-accept-type": "application/x.amzn.digital.deliverymanifest@1.0",
                    "X-ADP-SW": str(manifest["responseContext"]["swVersion"]),
                    "X-ADP-LTO": "60",
                    "Accept": "application/x-com.amazon.drm.Voucher@1.0",
                }
                if "country" in manifest["responseContext"]:
                    headers["X-ADP-Country"] = str(
                        manifest["responseContext"]["country"]
                    )

                url += "&supportedVoucherVersions=V1"
            elif resource["type"] == "KINDLE_MAIN_BASE":
                fn = manifest["content"]["id"] + "_EBOK.azw"
            elif resource["type"] == "KINDLE_MAIN_METADATA":
                fn = resource["id"] + ".azw.md"
            elif resource["type"] == "KINDLE_MAIN_ATTACHABLE":
                fn = resource["id"] + ".azw.res"
            elif resource["type"] == "KINDLE_USER_ANOT":
                fn = manifest["content"]["id"] + "_EBOK.mbpV2"

            parts.append(Request(method="GET", url=url, fn=fn, headers=headers))

        files = []
        for part in parts:
            r = self.session.send(
                amazon_api.signed_request(
                    part.method,
                    part.url,
                    asin=asin,
                    tokens=self.tokens,
                    headers=part.headers,
                )
            )
            fn = part.fn

            if fn is None:
                cd = r.headers.get("content-disposition")
                fn = re.findall('filename="(.+)"', cd)
                fn = fn[0]

            fn = Path(self.out_dir) / Path(fn)
            files.append(fn)
            fn.write_bytes(r.content)
            print(f"Book part successfully saved to {fn}")

        asin = manifest["content"]["id"].upper()
        manifest_file = Path(f"{asin}.manifest")
        manifest_json_data = json.dumps(manifest)
        manifest_file.write_text(manifest_json_data)
        files.append(manifest_file)
        name = trim_title_suffix(
            self.ebook_library_dict.get(asin, {})
            .get("title", "")
            .encode("utf8")
            .decode()
        )
        if len(name) > self.cut_length:
            name = name[: self.cut_length - 10]
        fn = name + "_" + asin + "_EBOK.kfx-zip"
        fn = Path(self.out_dir) / Path(fn)
        out_epub = Path(self.out_epub_dir) / Path(name + ".epub")
        with ZipFile(fn, "w") as myzip:
            for file in files:
                myzip.write(file)
                file.unlink()

        fn_dec = name + "_" + asin + "_EBOK.kfx-zip.tmp"
        kfx_book = KFXZipBook(fn, self.tokens["device_id"])
        kfx_book.voucher = self.drm_voucher
        kfx_book.processBook()
        kfx_book.getFile(fn_dec)
        Path(fn).unlink()
        Path(fn_dec).rename(fn)
        b = YJ_Book(str(fn))
        epub_data = b.convert_to_epub()
        with open(out_epub, "wb") as f:
            f.write(epub_data)

    def _download_azw(self, manifest, asin):
        resources = manifest["resources"]
        url = resources[0]["endpoint"]["url"]
        r = self.session.send(
            amazon_api.signed_request(
                "GET",
                url,
                asin=asin,
                tokens=self.tokens,
            )
        )
        name = trim_title_suffix(
            self.ebook_library_dict.get(asin, {})
            .get("title", "")
            .encode("utf8")
            .decode()
        )
        if len(name) > self.cut_length:
            name = name[: self.cut_length - 10]
        out = Path(self.out_dir) / Path(name + ".azw3")
        out_epub = Path(self.out_epub_dir) / Path(name + ".epub")

        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=512):
                f.write(chunk)
        out_dedrm = Path(self.out_dedrm_dir) / Path(name)
        time.sleep(1)
        mb = MobiBook(out)
        md1, md2 = mb.get_pid_meta_info()
        totalpids = get_pid_list(md1, md2, [self.tokens["device_id"]], [])
        totalpids = list(set(totalpids))
        mb.make_drm_file(totalpids, out_dedrm)
        time.sleep(1)
        self._save_to_epub(out_dedrm, out_epub)

    def download_all_ebooks(self):
        for b in self.ebooks:
            try:
                self.download_book(b["ASIN"])
            except Exception as e:
                import traceback

                traceback.print_exc()
                print(e)
            # spider rule
            time.sleep(1)

    def download_all_pdocs(self):
        for b in self.pdocs:
            try:
                self.download_pdoc(b["ASIN"])
            except Exception as e:
                import traceback

                traceback.print_exc()
                print(e)
            # spider rule
            time.sleep(1)

    def make_ebook_memory(self, from_index=None, only_price=False):
        self._make_all_ebook_price(from_index=from_index)
        if not only_price:
            self.make_all_ebook_info()
        s = MY_KINDLE_STATS_INFO_HEAD
        s += KINDLE_TABLE_HEAD
        index = 1
        headers = None
        for _, book_info in self.ebook_library_dict.items():
            s += KINDLE_STAT_TEMPLATE.format(
                id=str(index),
                title=book_info.get("title", ""),
                authors=book_info.get("authors", ""),
                acquired=book_info.get("purchase_date", "")[:10],
                last_read=book_info.get("last_read", "")[:10],
                highlight=book_info.get("highlight_count", ""),
                price=book_info.get("price", ""),
            )
            index += 1
        if not os.path.exists("my_kindle_stats.md"):
            with open("my_kindle_stats.md", "a") as f:
                f.write(
                    """<!--START_SECTION:my_kindle-->
<!--END_SECTION:my_kindle-->
                """
                )
        if not only_price:
            replace_readme_comments("my_kindle_stats.md", s, "my_kindle")

        ####### CSV #######
        book_list = list(self.ebook_library_dict.values())
        if only_price:
            book_list = book_list[from_index:]
        headers = book_list[0].keys()

        import csv

        csv_name = (
            "my_kindle_stats.csv"
            if not only_price
            else "my_kindle_stats_only_price.csv"
        )
        with open(csv_name, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)

            writer.writeheader()
            for row in book_list:
                writer.writerow(row)
        print("File: my_kindle_stats.csv and my_kindle_stats.md have been generated")

    def make_all_bookmark(self):
        """
        this include both ebooks and pdocs
        """
        amazon_api.refresh(self.tokens)
        # make all ebooks bookmark
        ebook_bookmark_dict_list = []
        pdoc_bookmarl_dict_list = []
        for asin, value in self.ebook_library_dict.items():
            manifest, _, info = self.get_book(asin)
            if not manifest:
                continue
            for r in manifest["resources"]:
                if r["type"] == "KINDLE_USER_ANOT":
                    url = r["endpoint"]["url"]
                    book_mark_info = self.ebook_bookmark(url)
                    if book_mark_info:
                        value.update(book_mark_info)
            print(value)
            ebook_bookmark_dict_list.append(value)
        with open("ebooks_bookmark.json", "w", encoding="utf8") as f:
            json.dump(ebook_bookmark_dict_list, f, indent=4, ensure_ascii=False)

        # make all pdoc bookmark
        for asin, value in self.pdoc_library_dict.items():
            pdoc_bookmark = self.pdoc_bookmark(asin)
            if pdoc_bookmark:
                value.update(pdoc_bookmark)
            print(value)
            pdoc_bookmarl_dict_list.append(value)
        with open("pdocs_bookmark.json", "w", encoding="utf8") as f:
            json.dump(pdoc_bookmarl_dict_list, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    kindle = NoKindle()
    kindle.make_library()
