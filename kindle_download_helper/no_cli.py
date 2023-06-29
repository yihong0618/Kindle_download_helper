import argparse
import os
import time

from kindle_download_helper.config import (
    DEFAULT_OUT_DEDRM_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_OUT_EPUB_DIR,
)
from kindle_download_helper.no_kindle import NoKindle


def no_main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        "--email",
        help="amazon login email",
    )
    parser.add_argument(
        "-p",
        "--password",
        help="amazon login password",
    )
    parser.add_argument(
        "--com",
        dest="domain",
        action="store_const",
        const="com",
        default="cn",
        help="if your account is an amazon.co.uk account",
    )
    parser.add_argument(
        "--cn",
        dest="domain",
        action="store_const",
        const="cn",
        default="cn",
        help="if your account is an amazon.cn account",
    )
    parser.add_argument(
        "--jp",
        dest="domain",
        action="store_const",
        const="co.jp",
        default="cn",
        help="if your account is an amazon.co.jp account",
    )
    parser.add_argument(
        "--de",
        dest="domain",
        action="store_const",
        const="de",
        default="cn",
        help="if your account is an amazon.de account",
    )
    parser.add_argument(
        "--uk",
        dest="domain",
        action="store_const",
        const="uk",
        default="cn",
        help="if your account is an amazon.co.uk account",
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
        "-oe",
        "--outepubmdir",
        default=DEFAULT_OUT_EPUB_DIR,
        help="dwonload output epub dir",
    )
    options = parser.parse_args()
    if options.email is None or options.password is None:
        raise Exception("Please provide email and password")

    if not os.path.exists(options.outdir):
        os.makedirs(options.outdir)
    # for epub
    if not os.path.exists(options.outepubmdir):
        os.makedirs(options.outepubmdir)
    # for dedrm
    if not os.path.exists(options.outdedrmdir):
        os.makedirs(options.outdedrmdir)

    nk = NoKindle(options.email, options.password, options.domain)
    nk.make_library()
    for e in nk.ebooks:
        try:
            nk.download_book(e["ASIN"])
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(e)
        # spider rule
        time.sleep(1)


if __name__ == "__main__":
    no_main()
