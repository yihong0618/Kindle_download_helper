import argparse
import os
import time
from rich import print

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
        "-o", "--outdir", default=DEFAULT_OUT_DIR, help="download output dir"
    )
    parser.add_argument(
        "-od",
        "--outdedrmdir",
        default=DEFAULT_OUT_DEDRM_DIR,
        help="download output dedrm dir",
    )
    parser.add_argument(
        "-oe",
        "--outepubmdir",
        default=DEFAULT_OUT_EPUB_DIR,
        help="download output epub dir",
    )
    parser.add_argument(
        "--pdoc",
        dest="pdoc",
        action="store_true",
        help="to download personal documents set it true",
    )
    parser.add_argument(
        "--memory",
        dest="memory",
        action="store_true",
        help="Generate your kindle memory to md and csv files",
    )
    parser.add_argument(
        "--bookmark",
        dest="bookmark",
        action="store_true",
        help="Generate your kindle bookmark to md and json files",
    )
    parser.add_argument(
        "--only-price",
        dest="only_price",
        action="store_true",
        help="Only want to get price",
    )
    parser.add_argument(
        "--from-index",
        dest="index",
        type=int,
        default=0,
        help="resume from the index if download failed",
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

    if options.memory:
        if options.only_price and options.index > 0:
            nk.make_ebook_memory(
                only_price=options.only_price, from_index=options.index
            )
        else:
            nk.make_ebook_memory()
        return

    if options.bookmark:
        nk.make_all_bookmark()
        return

    # download books part
    if options.pdoc:
        nk.download_all_pdocs()
    else:
        nk.download_all_ebooks()


if __name__ == "__main__":
    no_main()
