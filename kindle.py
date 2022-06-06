"""
Note some download code from: https://github.com/sghctoma/bOOkp
Great Thanks
"""

from http.cookies import SimpleCookie
import os
import re
import json
import urllib
import urllib3

import requests
import argparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUT_DIR = "DOWNLOADS"
KINDLE_BOOKALL_URL = "https://www.amazon.com/hz/mycd/myx#/home/content/booksAll"
KINDLE_CN_BOOKALL_URL = "https://www.amazon.cn/hz/mycd/myx#/home/content/booksAll"

KINDLE_HEADER = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/1AE148",
}

## download url ##
KINDLE_CN_DOWNLOAD_URL = "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type=EBOK&key={}&fsn={}&device_type={}&customerId={}&authPool=AmazonCN"
KINDLE_DOWNLOAD_URL = "https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent?type=EBOK&key={}&fsn={}&device_type={}&customerId={}"

## payload url ##
KINDLE_PAYLOAD_URL = "https://www.amazon.com/hz/mycd/ajax"
KINDLE_CN_PAYLOAD_URL = "https://www.amazon.cn/hz/mycd/ajax"


class Kindle:
    def __init__(self, cookie, csrf_token, is_cn=True):
        self.kindle_cookie = cookie
        self.session = requests.Session()
        self.header = KINDLE_HEADER
        self.is_cn = is_cn
        self.DOWNLOAD_URL = (
            KINDLE_CN_DOWNLOAD_URL if self.is_cn else KINDLE_DOWNLOAD_URL
        )
        self.PAYLOAD_URL = KINDLE_CN_PAYLOAD_URL if self.is_cn else KINDLE_PAYLOAD_URL
        self.BOOK_ALL_URL = KINDLE_CN_BOOKALL_URL if self.is_cn else KINDLE_BOOKALL_URL
        self.has_session = False
        self.csrf_token = csrf_token

    def _parse_kindle_cookie(self):
        cookie = SimpleCookie()
        cookie.load(self.kindle_cookie)
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
        r = self.session.get(
            "https://www.amazon.cn/hz/mycd/digital-console/deviceprivacycentre"
        )
        match = re.search('var csrfToken = "(.*)";', r.text)
        if not match:
            raise Exception("There's not csrf token here, please check")
        self.csrf_token = match.group(1)

    def get_devices(self):
        payload = {"param": {"GetDevices": {}}}
        r = self.session.post(
            self.PAYLOAD_URL,
            data={
                "data": json.dumps(payload),
                "csrfToken": self.csrf_token,
            },
            headers=self.header,
        )
        devices = r.json()
        if devices.get("error"):
            raise Exception(
                f"Error: {devices.get('error')}, please visit {self.BOOK_ALL_URL} to revoke the csrftoken and cookie"
            )
        devices = r.json()["GetDevices"]["devices"]
        return [device for device in devices if "deviceSerialNumber" in device]

    def get_all_asins(self):
        """
        TODO: refactor this function
        """
        startIndex = 0
        batchSize = 100
        payload = {
            "param": {
                "OwnershipData": {
                    "sortOrder": "DESCENDING",
                    "sortIndex": "DATE",
                    "startIndex": startIndex,
                    "batchSize": batchSize,
                    "contentType": "Ebook",
                    "itemStatus": ["Active"],
                    "originType": ["Purchase"],
                }
            }
        }

        asins = []
        while True:
            r = self.session.post(
                KINDLE_CN_PAYLOAD_URL,
                data={"data": json.dumps(payload), "csrfToken": self.csrf_token},
                headers=self.header,
            )
            result = r.json()
            asins += [book["asin"] for book in result["OwnershipData"]["items"]]

            if result["OwnershipData"]["hasMoreItems"]:
                startIndex += batchSize
                payload["param"]["OwnershipData"]["startIndex"] = startIndex
            else:
                break
        return asins

    def make_session(self):
        cookies = self._parse_kindle_cookie()
        if not cookies:
            raise Exception("Please make sure your amazon cookie is right")
        self.session.cookies = cookies
        self.has_session = True

    def download_one_book(self, asin, device):
        try:
            download_url = self.DOWNLOAD_URL.format(
                asin,
                device["deviceSerialNumber"],
                device["deviceType"],
                device["customerId"],
            )
            r = self.session.get(
                download_url, headers=self.header, verify=False, stream=True
            )
            name = re.findall(
                "filename\*=UTF-8''(.+)", r.headers["Content-Disposition"]
            )[0]
            name = urllib.parse.unquote(name)
            name = name.replace("/", "_")
            total_size = r.headers["Content-length"]
            out = os.path.join(OUT_DIR, name)
            print(f"downloading {name} {total_size} bytes")
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=512):
                    f.write(chunk)
            print(f"{name} downloaded")
        except Exception as e:
            print(str(e))
            print(f"{asin} download failed")

    def download_books(self):
        # use default device
        device = self.get_devices()[0]
        asins = self.get_all_asins()
        l = []
        for asin in asins:
            self.download_one_book(asin, device)

        print(
            "\n\nAll done!\nNow you can use apprenticeharper's DeDRM tools "
            "(https://github.com/apprenticeharper/DeDRM_tools)\n"
            "with the following serial number to remove DRM: "
            + device["deviceSerialNumber"]
        )
        with open(os.path.join(OUT_DIR, "key.txt"), "w") as f:
            f.write(f"Key is: {device['deviceSerialNumber']}")


if __name__ == "__main__":
    if not os.path.exists(OUT_DIR):
        os.mkdir(OUT_DIR)
    parser = argparse.ArgumentParser()
    parser.add_argument("cookie", help="amazon or amazon cn cookie")
    parser.add_argument("csrf_token", help="amazon or amazon cn csrf token")
    parser.add_argument(
        "--is-cn",
        dest="is_cn",
        action="store_true",
        help="if amazon accout is cn",
    )
    options = parser.parse_args()
    kindle = Kindle(options.cookie, options.csrf_token, options.is_cn)
    kindle.make_session()
    kindle.download_books()
