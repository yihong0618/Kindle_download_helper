import base64
import datetime
import gzip
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import uuid
from urllib.parse import urlparse

import requests
import xmltodict
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

SCRIPT_PATH = os.path.dirname(os.path.realpath(sys.argv[0]))
DEVICE_ID_PATH = os.path.join(SCRIPT_PATH, ".device_id")
TOKENS_PATH = os.path.join(SCRIPT_PATH, ".tokens")
DEVICE_ID_PATH_COM = os.path.join(SCRIPT_PATH, ".device_id.com")
TOKENS_PATH_COM = os.path.join(SCRIPT_PATH, ".tokens.com")

if os.path.isfile(DEVICE_ID_PATH):
    with open(DEVICE_ID_PATH, "r") as f:
        DEVICE_ID = f.read()
else:
    with open(DEVICE_ID_PATH, "w") as f:
        DEVICE_ID = secrets.token_hex(16)
        f.write(DEVICE_ID)

if os.path.isfile(DEVICE_ID_PATH_COM):
    with open(DEVICE_ID_PATH_COM, "r") as f:
        DEVICE_ID_COM = f.read()
else:
    with open(DEVICE_ID_PATH_COM, "w") as f:
        DEVICE_ID_COM = secrets.token_hex(16)
        f.write(DEVICE_ID_COM)


PID = hashlib.sha256(DEVICE_ID.encode()).hexdigest()[23:31].upper()
PID_COM = hashlib.sha256(DEVICE_ID_COM.encode()).hexdigest()[23:31].upper()


def save_tokens(tokens, is_com=False):
    if is_com:
        with open(TOKENS_PATH_COM, "w") as f:
            f.write(json.dumps(tokens))
    else:
        with open(TOKENS_PATH, "w") as f:
            f.write(json.dumps(tokens))


def get_tokens(is_com=False):
    if is_com:
        if os.path.isfile(TOKENS_PATH_COM):
            with open(TOKENS_PATH_COM, "r") as f:
                return json.loads(f.read())
        else:
            return None
    if os.path.isfile(TOKENS_PATH):
        with open(TOKENS_PATH, "r") as f:
            return json.loads(f.read())
    else:
        return None


APP_NAME = "com.iconology.comix"
APP_VERSION = "1221328936"
DEVICE_NAME = "walleye/google/Pixel 2"
DEVICE_TYPE = "A2A33MVZVPQKHY"
MANUFACTURER = "Google"
OS_VERSION = "google/walleye/walleye:8.1.0/OPM1.171019.021/4565141:user/release-keys"
PFM = "A1F83G8C2ARO7P"
SW_VERSION = "1221328936"


def get_auth_headers(domain):
    return {
        "Accept-Charset": "utf-8",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 2 Build/OPM1.171019.021)",
        "x-amzn-identity-auth-domain": f"api.amazon.{domain}",
        "x-amzn-requestid": str(uuid.uuid4()).replace("-", ""),
    }


def get_api_headers():
    return {
        "accept": "*/*",
        "accept-encoding": "gzip",
        "accept-language": "en-US",
        "currenttransportmethod": "WiFi",
        "is_archived_items": "1",
        "software_rev": SW_VERSION,
        "user-agent": "okhttp/3.12.1",
        "x-adp-app-id": APP_NAME,
        "x-adp-app-sw": SW_VERSION,
        "x-adp-attemptcount": "1",
        "x-adp-cor": "US",
        "x-adp-country": "US",
        "x-adp-lto": "0",
        "x-adp-pfm": PFM,
        "x-adp-reason": "ArchivedItems",
        "x-adp-sw": SW_VERSION,
        "x-adp-transport": "WiFi",
        "x-amzn-accept-type": "application/x.amzn.digital.deliverymanifest@1.0",
    }


def generate_frc(device_id):
    cookies = json.dumps(
        {
            "ApplicationName": APP_NAME,
            "ApplicationVersion": APP_VERSION,
            "DeviceLanguage": "en",
            "DeviceName": DEVICE_NAME,
            "DeviceOSVersion": OS_VERSION,
            "IpAddress": requests.get("https://api.ipify.org").text,
            "ScreenHeightPixels": "1920",
            "ScreenWidthPixels": "1280",
            "TimeZone": "00:00",
        }
    )

    def pkcs7_pad(data):
        padsize = 16 - len(data) % 16
        return data + bytes([padsize]) * padsize

    compressed = gzip.compress(cookies.encode())

    key = PBKDF2(device_id, b"AES/CBC/PKCS7Padding")
    iv = secrets.token_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pkcs7_pad(compressed))

    hmac_ = hmac.new(
        PBKDF2(device_id, b"HmacSHA256"), iv + ciphertext, hashlib.sha256
    ).digest()

    return base64.b64encode(b"\0" + hmac_[:8] + iv + ciphertext).decode()


def login(email, password, domain="com", device_id=DEVICE_ID):
    is_com = domain == "com"
    if is_com:
        device_id = DEVICE_ID_COM
    tokens = get_tokens(is_com=is_com)
    if (
        tokens
        and tokens["name"] == hashlib.md5(email.encode()).hexdigest()
        and tokens["domain"] == domain
    ):
        return refresh(tokens)

    body = {
        "auth_data": {
            "use_global_authentication": "true",
            "user_id_password": {"password": password, "user_id": email},
        },
        "registration_data": {
            "domain": "DeviceLegacy",
            "device_type": DEVICE_TYPE,
            "device_serial": device_id,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "device_model": DEVICE_NAME,
            "os_version": OS_VERSION,
            "software_version": SW_VERSION,
        },
        "requested_token_type": [
            "bearer",
            "mac_dms",
            "store_authentication_cookie",
            "website_cookies",
        ],
        "cookies": {"domain": f"amazon.{domain}", "website_cookies": []},
        "user_context_map": {"frc": generate_frc(device_id)},
        "device_metadata": {
            "device_os_family": "android",
            "device_type": DEVICE_TYPE,
            "device_serial": device_id,
            "mac_address": secrets.token_hex(64).upper(),
            "manufacturer": MANUFACTURER,
            "model": DEVICE_NAME,
            "os_version": "30",
            "android_id": "e97690019ccaab2b",
            "product": DEVICE_NAME,
        },
        "requested_extensions": ["device_info", "customer_info"],
    }

    response_json = requests.post(
        f"https://api.amazon.{domain}/auth/register",
        headers=get_auth_headers(domain),
        json=body,
    ).json()

    try:
        tokens = {
            "name": hashlib.md5(
                email.encode()
            ).hexdigest(),  # to differentiate tokens from different accounts
            "domain": domain,
            "device_id": device_id,
            "access_token": response_json["response"]["success"]["tokens"]["bearer"][
                "access_token"
            ],
            "refresh_token": response_json["response"]["success"]["tokens"]["bearer"][
                "refresh_token"
            ],
            "device_private_key": response_json["response"]["success"]["tokens"][
                "mac_dms"
            ]["device_private_key"],
            "adp_token": response_json["response"]["success"]["tokens"]["mac_dms"][
                "adp_token"
            ],
        }
        return register_device(tokens, is_com=is_com)
    except:
        print(json.dumps(response_json))
        return None


def refresh(tokens):
    body = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "source_token_type": "refresh_token",
        "source_token": tokens["refresh_token"],
        "requested_token_type": "access_token",
    }
    s = requests.Session()
    response_json = s.post(
        f"https://api.amazon.com/auth/token",
        headers=get_auth_headers(tokens["domain"]),
        json=body,
    ).json()

    try:
        tokens["access_token"] = response_json["access_token"]
    except:
        print(json.dumps(response_json))
    return tokens


def signed_request(
    method,
    url,
    headers=None,
    body=None,
    asin=None,
    tokens=None,
    request_id=None,
    request_type=None,
):
    """
    modified from https://github.com/mkb79/Audible/blob/master/src/audible/auth.py
    """

    if not tokens:
        tokens = get_tokens()
    if not tokens:
        print("Could not retrieve auth tokens")
        return None
    elif "adp_token" not in tokens:
        print("Could not find the adp token in tokens")
        return None
    elif "device_private_key" not in tokens:
        print("Could not find the private key in tokens")
        return None

    if not request_id:
        request_id = str(uuid.uuid4()).replace("-", "")
    else:
        request_id += str(int(time.time())) + "420"

    if not body:
        body = ""

    date = datetime.datetime.utcnow().isoformat("T")[:-7] + "Z"
    u = urlparse(url)
    path = f"{u.path}"
    if u.query != "":
        path += f"{u.params}?{u.query}"
    data = f"{method}\n{path}\n{date}\n{body}\n{tokens['adp_token']}"

    key = RSA.import_key(base64.b64decode(tokens["device_private_key"]))
    signed_encoded = base64.b64encode(pkcs1_15.new(key).sign(SHA256.new(data.encode())))
    signature = f"{signed_encoded.decode()}:{date}"

    if not headers:
        headers = get_api_headers()
    if asin:
        headers["x-adp-correlationid"] = f"{asin}-{int(time.time())}420.kindle.ebook"
    if request_type == "DRM_VOUCHER":
        headers["accept"] = "application/x-com.amazon.drm.Voucher@1.0"

    headers.update(
        {
            "x-adp-token": tokens["adp_token"],
            "x-adp-alg": "SHA256WithRSA:1.0",
            "x-adp-signature": signature,
            "x-amzn-requestid": request_id,
        }
    )

    return requests.Request(method, url, headers, data=body).prepare()


def register_device(tokens=None, is_com=False):
    if not tokens:
        tokens = get_tokens()

    url = "https://firs-ta-g7g.amazon.com/FirsProxy/registerAssociatedDevice"
    headers = {
        "Content-Type": "text/xml",
        "Expect": "",
    }
    pid = PID_COM if is_com else PID
    body = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><request><parameters><deviceType>{DEVICE_TYPE}</deviceType><deviceSerialNumber>{tokens['device_id']}</deviceSerialNumber><pid>{pid}</pid><deregisterExisting>false</deregisterExisting><softwareVersion>{SW_VERSION}</softwareVersion><softwareComponentId>{APP_NAME}</softwareComponentId><authToken>{tokens['access_token']}</authToken><authTokenType>ACCESS_TOKEN</authTokenType></parameters></request>"
    s = requests.session()
    resp = s.send(signed_request("POST", url, headers, body, tokens=tokens))

    if resp.status_code == 200:
        parsed_response = xmltodict.parse(resp.text)
        tokens["device_private_key"] = parsed_response["response"]["device_private_key"]
        tokens["adp_token"] = parsed_response["response"]["adp_token"]
    save_tokens(tokens, is_com=is_com)
    return tokens


if __name__ == "__main__":
    arg_count = len(sys.argv)
    if arg_count != 4:
        print("usage: amazon_auth.py <email> <password> <domain>")
        print("domains: com, co.uk, co.jp, de")
        exit()

    tokens = login(sys.argv[1], sys.argv[2], sys.argv[3])

    if tokens == None:
        print("Could not login!")
    else:
        print(json.dumps(tokens))
