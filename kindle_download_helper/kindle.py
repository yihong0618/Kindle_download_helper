"""
Note some download code from: https://github.com/sghctoma/bOOkp
Great Thanks
"""

import atexit
import html
import json
import logging
import os
import pathlib
import pickle
import re
import shutil
import time
import urllib
from http.cookies import SimpleCookie

import requests
import urllib3
from moki import extract
from requests.adapters import HTTPAdapter

from kindle_download_helper.config import (
    CONTENT_TYPES,
    DEFAULT_OUT_DEDRM_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_OUT_EPUB_DIR,
    DEFAULT_SESSION_FILE,
    ERROR_LOG_FILE,
    KINDLE_HEADER,
    KINDLE_STAT_TEMPLATE,
    KINDLE_TABLE_HEAD,
    KINDLE_URLS,
    MY_KINDLE_STATS_INFO,
    MY_KINDLE_STATS_INFO_HEAD,
)
from kindle_download_helper.dedrm import MobiBook, get_pid_list
from kindle_download_helper.utils import replace_readme_comments, trim_title_suffix

try:
    import browser_cookie3
except ModuleNotFoundError:
    print("not found browser_cookie3 here, you should use --cookie command")

logger = logging.getLogger("kindle")
fh = logging.FileHandler(ERROR_LOG_FILE)
fh.setLevel(logging.ERROR)
logger.addHandler(fh)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Kindle:
    def __init__(
        self,
        csrf_token=None,
        domain="cn",
        out_dir=DEFAULT_OUT_DIR,
        out_dedrm_dir=DEFAULT_OUT_DEDRM_DIR,
        out_epub_dir=DEFAULT_OUT_EPUB_DIR,
        cut_length=76,
        session_file=DEFAULT_SESSION_FILE,
        **kwargs,
    ):
        self.urls = KINDLE_URLS[domain]
        self._csrf_token = csrf_token
        self.total_to_download = 0
        self.out_dir = out_dir
        self.out_dedrm_dir = out_dedrm_dir
        self.out_epub_dir = out_epub_dir
        self.dedrm = False
        self.cut_length = cut_length
        self.not_done = False
        self.session_file = session_file
        self.session = self.make_session()
        self.is_browser_cookie = False
        self.to_resolve_duplicate_names = False
        self.books_info_dict = {}
        self.file_type_list = ["EBOOK", "PDOC"]
        self.device_sn = kwargs["device_sn"] if "device_sn" in kwargs else ""
        atexit.register(self.dump_session)

    def set_cookie(self, cookiejar):
        if not cookiejar:
            raise Exception("Please make sure your amazon cookie is right")
        self.session.cookies.clear()
        self.session.cookies.update(cookiejar)

    def set_cookie_from_string(self, cookie_string):
        cj = self._parse_kindle_cookie(cookie_string)
        self.set_cookie(cj)

    def dump_session(self):
        with open(self.session_file, "wb") as f:
            pickle.dump(self.session, f)

    @property
    def csrf_token(self):
        if not self._csrf_token:
            self._csrf_token = self._get_csrf_token()
        return self._csrf_token

    @csrf_token.setter
    def csrf_token(self, csrf_token):
        self._csrf_token = csrf_token

    def ensure_session_cookie(self):
        if not self.session.cookies:
            logger.debug("No cookie found, trying to load from browsers")
            try:
                self.set_cookie(browser_cookie3.load())
            except:
                print("not found browser_cookie3 here, you should use --cookie command")

    @staticmethod
    def _parse_kindle_cookie(kindle_cookie):
        cookie = SimpleCookie()
        cookie.load(kindle_cookie)
        cookies_dict = {}
        cookiejar = None
        for key, morsel in cookie.items():
            cookies_dict[key] = morsel.value
            cookiejar = requests.utils.cookiejar_from_dict(
                cookies_dict, cookiejar=None, overwrite=True
            )
        return cookiejar

    def find_device(self):
        devices = self.get_devices()
        device_sn = self.device_sn

        if isinstance(device_sn, str) and device_sn != "":
            for device in devices:
                if device["deviceSerialNumber"] == device_sn.strip():
                    logger.info(
                        f"Using specified device with serial number: {device['deviceSerialNumber']}"
                    )
                    return device
            else:
                logger.info(f"Can't find device with serial number: {device_sn}")
        logger.info(
            f"Using default device serial Number: {devices[0]['deviceSerialNumber']}"
        )
        self.device_serial_number = devices[0]["deviceSerialNumber"]
        return devices[0]

    def _get_csrf_token(self):
        """
        TODO: I do not know why I have to get csrf token in the page not in this way
        maybe figure out why in the future
        """
        r = self.session.get(self.urls["bookall"])
        match = re.search(r'var csrfToken = "(.*)";', r.text)
        if not match:
            self.revoke_cookie_token(open_page=self.is_browser_cookie)
            raise Exception(
                "Can't get the csrf token, "
                f"please refresh the page at {self.urls['bookall']} and retry"
            )
        return match.group(1)

    def refresh_browser_cookie(self):
        import webbrowser

        try:
            webbrowser.open(self.urls["bookall"])
        except Exception:
            pass

    def revoke_cookie_token(self, open_page=False):
        # help user open it directly.
        logger.info(
            "Opening the url to get cookie...You can wait for the page to finish loading and retry"
        )
        self._csrf_token = None  # reset the token
        # clear the cookies so the next time it can be reloaded from the browsers
        self.session.cookies.clear()
        if open_page:
            self.refresh_browser_cookie()

    def ensure_cookie_token(self):
        if not self._csrf_token:
            if not self.session.cookies:
                self.refresh_browser_cookie()
                self.ensure_session_cookie()
            self._csrf_token = self._get_csrf_token()
        logger.debug(
            f"session-id: { self.session.cookies.get_dict().get('session-id') }"
        )

    def make_session(self):
        if os.path.exists(self.session_file):
            with open(self.session_file, "rb") as f:
                session = pickle.load(f)
        else:
            session = requests.Session()
            session.headers.update(KINDLE_HEADER)
            session.mount(
                # will retry 5 times after 0.5, 1.0, 2.0, 4.0, ... seconds for
                # (413, 429, 503) statuses
                "https://",
                HTTPAdapter(max_retries=urllib3.Retry(5, backoff_factor=0.5)),
            )

        logger.debug(f"user-agent: { session.headers.get('User-Agent') }")
        return session

    def get_devices(self):
        """
        This method must be called before each download, so we ensure
        the session cookies before it is called
        """
        self.ensure_cookie_token()

        payload = {"param": {"GetDevices": {}}}
        r = self.session.post(
            self.urls["payload"],
            data={
                "data": json.dumps(payload),
                "csrfToken": self.csrf_token,
            },
        )
        r.raise_for_status()
        devices = r.json()
        if devices.get("error"):
            self.revoke_cookie_token(open_page=True)
            raise Exception(
                f"Error: {devices.get('error')}, please visit {self.urls['bookall']} to revoke the csrftoken and cookie"
            )
        devices = r.json()["GetDevices"]["devices"]
        # sleep get device first time.
        logger.info("Amazon bot check detected, sleep 3 sec")
        time.sleep(3)
        if not devices:
            raise Exception("No devices are bound to this account")
        return [device for device in devices if "deviceSerialNumber" in device]

    def get_all_books(self, start_index=0, filetype="EBOK"):
        """
        TODO: refactor this function
        """
        # some info
        if filetype == "PDOC":
            logger.info(
                "It will take some time to get all PDOC books list, please wait"
            )
        startIndex = start_index
        batchSize = 100
        payload = {
            "param": {
                "OwnershipData": {
                    "sortOrder": "DESCENDING",
                    "sortIndex": "DATE",
                    "startIndex": startIndex,
                    "batchSize": batchSize,
                    "contentType": CONTENT_TYPES[filetype],
                    "itemStatus": ["Active"],
                }
            }
        }

        if filetype == "EBOK":
            payload["param"]["OwnershipData"].update(
                {
                    "originType": ["Purchase"],
                }
            )
        else:
            batchSize = 18
            payload["param"]["OwnershipData"].update(
                {
                    "batchSize": batchSize,
                    "isExtendedMYK": False,
                }
            )

        books = []
        ### added by yihong0618 2022.06.27
        ### this ugly code is for amazon open their bot check
        ### if the bot check close
        ### will delete the try and try code
        break_times = 0
        while True:
            # anyway sleep 0.5
            time.sleep(0.5)
            r = self.session.post(
                self.urls["payload"],
                data={"data": json.dumps(payload), "csrfToken": self.csrf_token},
            )
            # try three times for bot check
            if r.status_code == 503:
                # sleep and try again
                sleep_seconds = 5 + 2 * break_times
                time.sleep(sleep_seconds)
                logger.info(
                    f"Amazon bot check detected, sleep {sleep_seconds} sec and try this api again, now index: {startIndex}/{self.total_to_download}"
                )
                if break_times < 7:
                    break_times += 1
                r = self.session.post(
                    self.urls["payload"],
                    data={"data": json.dumps(payload), "csrfToken": self.csrf_token},
                )
                if not r.ok:
                    if r.status_code == 503:
                        time.sleep(sleep_seconds)
                        logger.info(
                            f"Amazon bot check detected, sleep {sleep_seconds} sec last time and try this api again, now index: {startIndex}/{self.total_to_download}"
                        )
                        logger.info("Next time fail will break the loop")
                        r = self.session.post(
                            self.urls["payload"],
                            data={
                                "data": json.dumps(payload),
                                "csrfToken": self.csrf_token,
                            },
                        )
                        break_times += 1
                    if not r.ok:
                        # amazon limit this api
                        if startIndex == 0:
                            logger.error(
                                "Amazon api limit when this download done.\n Please run it again`"
                            )
                        else:
                            self.not_done = True
                            logger.error(
                                "Amazon api limit when this download done.\n You can add command `--resume-from %s`",
                                startIndex,
                            )
                        break
            result = r.json()
            if not result.get("success", True):
                logger.error("get all books error: %s", result.get("error"))
                break
            try:
                items = result["OwnershipData"]["items"]
            except KeyError:
                logger.error("get all books error: %s", result.get("error"))
                break
            for item in items:
                if filetype == "PDOC":
                    item["title"] = html.unescape(item["title"])
                    item["authors"] = html.unescape(item.pop("author", ""))
                if item.get("readStatus", "") == "READ":
                    self.books_info_dict[item["asin"]] = item

            books.extend(items)
            self.total_to_download = result["OwnershipData"]["numberOfItems"]

            if result["OwnershipData"]["hasMoreItems"]:
                startIndex += batchSize
                payload["param"]["OwnershipData"]["startIndex"] = startIndex
            else:
                break
        return books

    def _get_reading_stats(self):
        insights_url = self.urls["insights"]
        r = self.session.get(insights_url)
        if r.ok:
            return r.json()
        logger.error(f"Something is wrong get the stats data url: {insights_url}")
        raise Exception(f"Something is wrong get the stats data url: {insights_url}")

    def _make_one_book_stats_info(self, book_info):
        book_url = self.urls["book_url"]
        asin = book_info["asin"]
        book = self.books_info_dict.get(asin)
        if not book:
            return
        book_title = book.get("title", "")

        # filter the brackets in the book title
        book_title = re.sub(
            r"(\（[^)]*\）|\([^)]*\)|\【[^)]*\】|\[[^)]*\])", "", book_title
        )

        book_title = book_title.replace(" ", "")
        if book.get("category", "") == "KindleEBook":
            book_url = book_url.format(book_id=asin)
            book_title = f"[{book_title}]({book_url})"
        book_authors = book.get("authors", "")
        if len(book_authors) > 10:
            book_authors = ",".join(book_authors.split(",")[:2]) + "..."
        # only keep date
        read = book_info.get("date_read")[:10]
        acquired = (
            book.get("acquiredDate", "")
            .replace("年", "-")
            .replace("月", "-")
            .replace("日", "")
        )
        return book_title, book_authors, acquired, read

    def make_kindle_stats_readme(self):
        ebooks = self.get_all_books(filetype="EBOK")
        pdocs = self.get_all_books(filetype="PDOC")
        first_ebook, first_pdoc = None, None
        reading_stats = self._get_reading_stats()
        read_list = reading_stats.get("goal_info", {}).get("titles_read")
        if pdocs:
            first_pdoc = pdocs[-1]
        if first_ebook:
            first_ebook = ebooks[-1]

        s = MY_KINDLE_STATS_INFO_HEAD
        kindle_stats_str = ""
        if pdocs or ebooks:
            kindle_stats_str = MY_KINDLE_STATS_INFO.format(
                books_len=len(ebooks) if ebooks else 0,
                pdocs_len=len(pdocs) if pdocs else 0,
                first_book_title=first_ebook["title"] if first_ebook else "",
                first_book_bought_date=(
                    first_ebook["acquiredDate"] if first_ebook else ""
                ),
                first_doc_title=first_pdoc["title"] if first_pdoc else "",
                first_doc_push_date=first_pdoc["acquiredDate"] if first_pdoc else "",
            )
        s += kindle_stats_str
        s += KINDLE_TABLE_HEAD
        index = 1
        for book_info in read_list:
            if not self._make_one_book_stats_info(book_info):
                continue
            book_title, book_authors, acquired, read = self._make_one_book_stats_info(
                book_info
            )
            s += KINDLE_STAT_TEMPLATE.format(
                id=str(index),
                title=book_title,
                authors=book_authors,
                acquired=acquired,
                read=read,
            )
            index += 1
        if not os.path.exists("my_kindle_stats.md"):
            with open("my_kindle_stats.md", "a") as f:
                f.write(
                    """<!--START_SECTION:my_kindle-->
<!--END_SECTION:my_kindle-->
                """
                )
        replace_readme_comments("my_kindle_stats.md", s, "my_kindle")

    def download_one_book(self, book, device, index, filetype="EBOK"):
        title = book["title"]
        asin = book["asin"]
        try:
            download_url = self.urls["download"].format(
                filetype,
                asin,
                device["deviceSerialNumber"],
                device["deviceType"],
                device["customerId"],
            )
            r = self.session.get(download_url, verify=False, stream=True)
            r.raise_for_status()
            origin_name = re.findall(
                r"filename\*=UTF-8''(.+)", r.headers["Content-Disposition"]
            )[0]
            name = origin_name

            name = urllib.parse.unquote(name)
            _, extname = os.path.splitext(name)

            name = title + extname
            name = re.sub(r'[\\/:*?"<>|]', "_", name)

            ##### if you have many duplicate name books #####
            if self.to_resolve_duplicate_names:
                name = f"{asin}_{name}"
            if len(name) > self.cut_length:
                name = name[: self.cut_length - 5] + name[-5:]
            total_size = r.headers["Content-length"]

            out = os.path.join(self.out_dir, name)
            out_dedrm = os.path.join(self.out_dedrm_dir, name)
            out_epub = os.path.join(self.out_epub_dir, name.split(".")[0] + ".epub")

            # normally one owns no more than 9999 books
            count_digit_length = 4

            size_length = 6
            size_in_mb = round(float(total_size) / (1024 * 1024), 3)

            logger.info(
                f"[{index+1:>{count_digit_length}}/{self.total_to_download:>{count_digit_length}}][{size_in_mb:> {size_length}}Mb]Downloading {name}"
            )

            # try if we can write the file
            try:
                pathlib.Path(out).touch()
            except OSError as e:
                if e.errno == 36:  # means file name too long
                    name = trim_title_suffix(title) + extname
                    logger.info(f"Original filename too long, trim to {name}")
                    out = os.path.join(self.out_dir, name)
                    out_dedrm = os.path.join(self.out_dedrm_dir, name)
                else:
                    logger.error(e)

            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=512):
                    f.write(chunk)
            logger.info(f"{name} downloaded")
            # for dedrm
            if self.dedrm:
                try:
                    mb = MobiBook(out)
                    md1, md2 = mb.get_pid_meta_info()
                    totalpids = get_pid_list(md1, md2, [self.device_serial_number], [])
                    totalpids = list(set(totalpids))
                    mb.make_drm_file(totalpids, out_dedrm)
                    time.sleep(1)
                    # save to EPUB
                    epub_dir, epub_file = extract(out_dedrm)
                    print(epub_file)
                    shutil.copy2(epub_file, out_epub)
                    # delete it
                    shutil.rmtree(epub_dir)

                except Exception as e:
                    logger.error("DeDRM failed for %s: %s", name, e)
                    pass
        except Exception as e:
            logger.error(str(e))
            logger.error(
                f"Index: {index + 1}, Title: {title}, Asin: {asin} download failed"
            )

    def download_books(self, start_index=0, filetype="EBOK"):
        # use default device
        device = self.find_device()

        books = self.get_all_books(filetype=filetype, start_index=start_index)
        if start_index > 0:
            print(f"resuming the download {start_index + 1}/{self.total_to_download}")
        index = start_index
        for book in books:
            self.download_one_book(book, device, index, filetype)
            index += 1
        if self.not_done:
            logger.error(
                f"\n\nNot All done!\nAmazon api limit when this download done.\n You can add command `--resume-from {index}` to resume download next time"
            )
        else:
            if not self.dedrm:
                logger.info(
                    "\n\nAll done!\nNow you can use apprenticeharper's DeDRM tools "
                    "(https://github.com/apprenticeharper/DeDRM_tools)\n"
                    "with the following serial number to remove DRM: "
                    + device["deviceSerialNumber"]
                )
            else:
                logger.info(
                    "All done books saved in `DOWNLOAD`, dedrm files saved in `DEDRMS`"
                )

        with open(os.path.join(self.out_dir, "key.txt"), "w") as f:
            f.write(f"Key is: {device['deviceSerialNumber']}")
            logger.info(
                "the device serial number can also be found here: {0}".format(
                    os.path.join(self.out_dir, "key.txt")
                )
            )
