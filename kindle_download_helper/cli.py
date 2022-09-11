from kindle_download_helper.kindle import Kindle
import argparse
import os
import urllib3
import logging
import json

from kindle_download_helper.config import (
    DEFAULT_OUT_DIR,
    DEFAULT_SESSION_FILE,
    DEFAULT_OUT_DEDRM_DIR,
)

logger = logging.getLogger("kindle")
fh = logging.FileHandler(".error_books.log")
fh.setLevel(logging.ERROR)
logger.addHandler(fh)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
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
        "--de",
        dest="domain",
        action="store_const",
        const="de",
        default="com",
        help="if your account is an amazon.de account",
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
        "-od",
        "--outdedrmdir",
        default=DEFAULT_OUT_DEDRM_DIR,
        help="dwonload output dedrm dir",
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
        help="If you want to generate kindle readme stats",
    )
    parser.add_argument(
        "--dedrm",
        dest="dedrm",
        action="store_true",
        help="If you want to `dedrm` directly",
    )

    parser.add_argument(
        "--list",
        dest="list_only",
        action="store_true",
        help="just list books/pdoc, not to download",
    )

    parser.add_argument(
        "--device_sn",
        dest="device_sn",
        default="",
        help="Download file for device with this serial number",
    )

    options = parser.parse_args()

    if not os.path.exists(options.outdir):
        os.makedirs(options.outdir)
    # for dedrm
    if not os.path.exists(options.outdedrmdir):
        os.makedirs(options.outdedrmdir)
    kindle = Kindle(
        options.csrf_token,
        options.domain,
        options.outdir,
        options.outdedrmdir,
        options.cut_length,
        session_file=options.session_file,
        device_sn=options.device_sn,
    )
    # other args
    kindle.to_resolve_duplicate_names = options.resolve_duplicate_names
    kindle.dedrm = options.dedrm

    if options.cookie_file:
        with open(options.cookie_file, "r") as f:
            kindle.set_cookie_from_string(f.read())
    elif options.cookie:
        kindle.set_cookie_from_string(options.cookie)
    else:
        kindle.is_browser_cookie = True

    if options.list_only:
        kindle.get_devices()
        print(
            json.dumps(
                kindle.get_all_books(filetype=options.filetype),
                indent=4,
                ensure_ascii=False,
            )
        )
        exit()

    if options.readme:
        # generate readme stats
        kindle.make_kindle_stats_readme()
    else:
        kindle.download_books(start_index=options.index - 1, filetype=options.filetype)


if __name__ == "__main__":
    main()
