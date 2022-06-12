"""
Note some download code from: https://github.com/sghctoma/bOOkp
Great Thanks
"""

import argparse
import atexit
import html
import json
import logging
import os
import pickle
import re
import urllib
from http.cookies import SimpleCookie

import browser_cookie3
import requests
from requests.adapters import HTTPAdapter
import urllib3

logger = logging.getLogger("kindle")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_OUT_DIR = "DOWNLOADS"
DEFAULT_SESSION_FILE = ".kindle_session"

KINDLE_HEADER = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/1AE148",
}

CONTENT_TYPES = {
    "EBOK": "Ebook",
    "PDOC": "KindlePDoc",
}

KINDLE_URLS = {
    "cn": {
        "bookall": "https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}&authPool=AmazonCN",
        "payload": "https://www.amazon.cn/hz/mycd/ajax",
    },
    "jp": {
        "bookall": "https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.co.jp/hz/mycd/ajax",
    },
    "com": {
        "bookall": "https://www.amazon.com/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.com/hz/mycd/ajax",
    },
}


class Kindle:
    def __init__(
        self,
        csrf_token=None,
        domain="cn",
        out_dir=DEFAULT_OUT_DIR,
        cut_length=100,
        session_file=DEFAULT_SESSION_FILE,
    ):
        self.urls = KINDLE_URLS[domain]
        self._csrf_token = csrf_token
        self.total_to_download = 0
        self.out_dir = out_dir
        self.cut_length = cut_length
        self.not_done = False
        self.session_file = session_file
        self.session = self.make_session()
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
            self.set_cookie(browser_cookie3.load())

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

    def _get_csrf_token(self):
        """
        TODO: I do not know why I have to get csrf token in the page not in this way
        maybe figure out why in the future
        """
        r = self.session.get(self.urls["bookall"])
        match = re.search(r'var csrfToken = "(.*)";', r.text)
        if not match:
            self.revoke_cookie_token(open_page=True)
            raise Exception(
                "Can't get the csrf token, "
                f"please refresh the page at {self.urls['bookall']} and retry"
            )
        return match.group(1)

    def revoke_cookie_token(self, open_page=False):
        # help user open it directly.
        import webbrowser

        logger.info(
            "Opening the url to get cookie...You can wait for the page to finish loading and retry"
        )
        self._csrf_token = None  # reset the token
        # clear the cookies so the next time it can be reloaded from the browsers
        self.session.cookies.clear()
        if not open_page:
            return
        try:
            webbrowser.open(self.urls["bookall"])
        except Exception:
            # just do nothing
            pass

    def get_devices(self):
        # This method must be called before each download, so we ensure
        # the session cookies before it is called
        self.ensure_session_cookie()
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
        if not devices:
            raise Exception("No devices are bound to this account")
        return [device for device in devices if "deviceSerialNumber" in device]

    def get_all_books(self, start_index=0, filetype="EBOK"):
        """
        TODO: refactor this function
        """
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
        while True:
            r = self.session.post(
                self.urls["payload"],
                data={"data": json.dumps(payload), "csrfToken": self.csrf_token},
            )
            if r.status_code == 503:
                # amazon limit this api
                self.not_done = True
                logger.error(
                    f"Amazon api limit when this download done.\n You can add command `resume-from {startIndex}`"
                )
                break
            result = r.json()
            items = result["OwnershipData"]["items"]
            if filetype == "PDOC":
                for item in items:
                    item["title"] = html.unescape(item["title"])
                    item["authors"] = html.unescape(item.pop("author", ""))

            books.extend(items)
            if not self.total_to_download:
                self.total_to_download = result["OwnershipData"]["numberOfItems"]

            if result["OwnershipData"]["hasMoreItems"]:
                startIndex += batchSize
                payload["param"]["OwnershipData"]["startIndex"] = startIndex
            else:
                break
        return books

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
        return session

    def download_one_book(self, book, device, index, filetype="EBOK"):
        title = book["title"]
        try:
            download_url = self.urls["download"].format(
                filetype,
                book["asin"],
                device["deviceSerialNumber"],
                device["deviceType"],
                device["customerId"],
            )
            r = self.session.get(download_url, verify=False, stream=True)
            r.raise_for_status()
            name = re.findall(
                r"filename\*=UTF-8''(.+)", r.headers["Content-Disposition"]
            )[0]
            name = urllib.parse.unquote(name)
            name = re.sub(r'[\\/:*?"<>|]', "_", name)
            if len(name) > self.cut_length:
                name = name[: self.cut_length - 5] + name[-5:]
            total_size = r.headers["Content-length"]
            out = os.path.join(self.out_dir, name)
            logger.info(
                f"({index + 1}/{self.total_to_download})downloading {name} {total_size} bytes"
            )
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=512):
                    f.write(chunk)
            logger.info(f"{name} downloaded")
        except Exception as e:
            logger.error(str(e))
            logger.error(f"{title} download failed")

    def download_books(self, start_index=0, filetype="EBOK"):
        # use default device
        device = self.get_devices()[0]
        books = self.get_all_books(filetype=filetype, start_index=start_index)
        if start_index > 0:
            print(f"resuming the download {start_index + 1}/{self.total_to_download}")
        index = start_index
        for book in books:
            self.download_one_book(book, device, index, filetype)
            index += 1
        if self.not_done:
            logger.error(
                f"\n\nNot All done!\nAmazon api limit when this download done.\n You can add command `resume-from {index}`"
            )
        else:
            logger.info(
                "\n\nAll done!\nNow you can use apprenticeharper's DeDRM tools "
                "(https://github.com/apprenticeharper/DeDRM_tools)\n"
                "with the following serial number to remove DRM: "
                + device["deviceSerialNumber"]
            )
        with open(os.path.join(self.out_dir, "key.txt"), "w") as f:
            f.write(f"Key is: {device['deviceSerialNumber']}")


if __name__ == "__main__":

    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser()
    parser.add_argument("csrf_token", help="amazon or amazon cn csrf token", nargs="?")

    cookie_group = parser.add_mutually_exclusive_group()
    cookie_group.add_argument(
        "--cookie", dest="cookie", default="", help="amazon or amazon cn cookie"
    )
    cookie_group.add_argument(
        "--cookie-file", dest="cookie_file", default="", help="load cookie local file"
    )

    parser.add_argument(
        "--cn",
        dest="domain",
        action="store_const",
        const="cn",
        default="com",
        help="if your account is an amazon.cn account",
    )
    parser.add_argument(
        "--jp",
        dest="domain",
        action="store_const",
        const="jp",
        default="com",
        help="if your account is an amazon.jp account",
    )
    parser.add_argument(
        "--resume-from",
        dest="index",
        type=int,
        default=1,
        help="resume from the index if download failed",
    )
    parser.add_argument(
        "--cut-length",
        dest="cut_length",
        type=int,
        default=100,
        help="truncate the file name",
    )
    parser.add_argument(
        "-o", "--outdir", default=DEFAULT_OUT_DIR, help="dwonload output dir"
    )
    parser.add_argument(
        "-s",
        "--session-file",
        default=DEFAULT_SESSION_FILE,
        help="The reusable session dump file",
    )
    parser.add_argument(
        "--pdoc",
        dest="filetype",
        action="store_const",
        const="PDOC",
        default="EBOK",
        help="to download personal documents or ebook",
    )

    options = parser.parse_args()

    if not os.path.exists(options.outdir):
        os.makedirs(options.outdir)
    kindle = Kindle(
        options.csrf_token,
        options.domain,
        options.outdir,
        options.cut_length,
        session_file=options.session_file,
    )
    if options.cookie_file:
        with open(options.cookie_file, "r") as f:
            kindle.set_cookie_from_string(f.read())
    elif options.cookie:
        kindle.set_cookie_from_string(options.cookie)
    kindle.download_books(start_index=options.index - 1, filetype=options.filetype)
