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

try:
    import browser_cookie3
except:
    print("not found browser_cookie3 here, you should use --cookie command")
import requests
from requests.adapters import HTTPAdapter
import urllib3

logger = logging.getLogger("kindle")
fh = logging.FileHandler(".error_books.log")
fh.setLevel(logging.ERROR)
logger.addHandler(fh)

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
        "insights": "https://www.amazon.cn/kindle/reading/insights/data",
        "book_url": "https://www.amazon.cn/dp/{book_id}",
    },
    "jp": {
        "bookall": "https://www.amazon.jp/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.co.jp/hz/mycd/ajax",
        "insights": "https://www.amazon.co.jp/kindle/reading/insights/data",
        "book_url": "https://www.amazon.co.jp/dp/{book_id}",
    },
    "com": {
        "bookall": "https://www.amazon.com/hz/mycd/myx#/home/content/booksAll",
        "download": "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type={}&key={}&fsn={}&device_type={}&customerId={}",
        "payload": "https://www.amazon.com/hz/mycd/ajax",
        "insights": "https://www.amazon.cn/kindle/reading/insights/data",
        "book_url": "https://www.amazon.com/dp/{book_id}",
    },
}

# for kindle stats
GITHUB_README_COMMENTS = (
    "(<!--START_SECTION:{name}-->\n)(.*)(<!--END_SECTION:{name}-->\n)"
)
MY_KINDLE_STATS_INFO_HEAD = "## My Kindle Stats\n"
MY_KINDLE_STATS_INFO = "- I bought {books_len} books\n \
- I pushed {pdocs_len} docks\n \
- My first book is {first_book_title}, bought on {first_book_bought_date}\n \
- My first doc is {first_doc_title}, bought on {first_doc_push_date}\n\n"

KINDLE_TABLE_HEAD = "| ID | Title | Authors | Acquired | Read | \n | ---- | ---- | ---- | ---- | ---- |\n"
KINDLE_STAT_TEMPLATE = "| {id} | {title} | {authors} | {acquired} | {read} |\n"


def replace_readme_comments(file_name, comment_str, comments_name):
    with open(file_name, "r+") as f:
        text = f.read()
        # regrex sub from github readme comments
        text = re.sub(
            GITHUB_README_COMMENTS.format(name=comments_name),
            r"\1{}\n\3".format(comment_str),
            text,
            flags=re.DOTALL,
        )
        f.seek(0)
        f.write(text)
        f.truncate()


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
        self.is_browser_cookie = False
        self.to_resolve_duplicate_names = False
        self.books_info_dict = {}
        self.file_type_list = ["EBOOK", "PDOC"]
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
                self.set_cookie(browser_cookie3.load(domain_name="amazon"))
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
        while True:
            r = self.session.post(
                self.urls["payload"],
                data={"data": json.dumps(payload), "csrfToken": self.csrf_token},
            )
            if r.status_code == 503:
                # amazon limit this api
                if startIndex == 0:
                    logger.error(
                        "Amazon api limit when this download done.\n Please run it again`"
                    )
                else:
                    self.not_done = True
                    logger.error(
                        "Amazon api limit when this download done.\n You can add command `resume-from %s`",
                        startIndex,
                    )
                break
            result = r.json()
            if not result.get("success", True):
                logger.error("get all books error: %s", result.get("error"))
                break
            items = result["OwnershipData"]["items"]
            for item in items:
                if filetype == "PDOC":
                    item["title"] = html.unescape(item["title"])
                    item["authors"] = html.unescape(item.pop("author", ""))
                if item.get("readStatus", "") == "READ":
                    self.books_info_dict[item["asin"]] = item

            books.extend(items)
            if not self.total_to_download:
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
        book_title = book.get("title", "")
        # filter the brackets in the book title
        book_title = re.sub(
            r"(\（[^)]*\）)|(\([^)]*\))|(\【[^)]*\】)|(\[[^)]*\])|(\s)", "", book_title
        )
        book_title = book_title.replace(" ", "")
        if book.get("category", "") == "KindleEBook":
            book_url = book_url.format(book_id=asin)
            book_title = f"[{book_title}]({book_url})"
        book_authors = book.get("authors")
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
        reading_stats = self._get_reading_stats()
        read_list = reading_stats.get("goal_info", {}).get("titles_read")
        ebooks = self.get_all_books(filetype="EBOK")
        pdocs = self.get_all_books(filetype="PDOC")
        first_ebook, first_pdoc = ebooks[-1], pdocs[-1]
        print(len(self.books_info_dict.keys()), first_ebook, first_pdoc)
        print(read_list)

        s = MY_KINDLE_STATS_INFO_HEAD
        kindle_stats_str = MY_KINDLE_STATS_INFO.format(
            books_len=len(ebooks),
            pdocs_len=len(pdocs),
            first_book_title=first_ebook["title"],
            first_book_bought_date=first_ebook["acquiredDate"],
            first_doc_title=first_pdoc["title"],
            first_doc_push_date=first_pdoc["acquiredDate"],
        )
        s += kindle_stats_str
        s += KINDLE_TABLE_HEAD
        index = 1
        for book_info in read_list:
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
            name = re.findall(
                r"filename\*=UTF-8''(.+)", r.headers["Content-Disposition"]
            )[0]
            name = urllib.parse.unquote(name)
            name = re.sub(r'[\\/:*?"<>|]', "_", name)
            ##### if you have many duplicate name books #####
            if self.to_resolve_duplicate_names:
                name = f"{asin}_{name}"
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
            logger.error(f"Title: {title}, Asin: {asin} download failed")

    def download_books(self, start_index=0, filetype="EBOK"):
        # use default device
        device = self.get_devices()[0]
        logger.info(
            f"Using default device serial Number: {device['deviceSerialNumber']}"
        )
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

    logger.setLevel(os.environ.get("LOGGING_LEVEL", "INFO"))

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
    parser.add_argument(
        "--resolve_duplicate_names",
        dest="resolve_duplicate_names",
        action="store_true",
        help="Resolve duplicate names files to download",
    )
    parser.add_argument(
        "--readme",
        dest="readme",
        action="store_true",
        help="If only generate kindle readme stats",
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
    kindle.to_resolve_duplicate_names = options.resolve_duplicate_names
    if options.cookie_file:
        with open(options.cookie_file, "r") as f:
            kindle.set_cookie_from_string(f.read())
    elif options.cookie:
        kindle.set_cookie_from_string(options.cookie)
    else:
        kindle.is_browser_cookie = True

    if options.readme:
        # generate readme stats
        kindle.make_kindle_stats_readme()
    else:
        kindle.download_books(start_index=options.index - 1, filetype=options.filetype)
