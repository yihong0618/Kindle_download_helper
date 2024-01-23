import argparse
import json
import logging
import os

import urllib3

from kindle_download_helper.config import (
    DEFAULT_OUT_DEDRM_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_OUT_EPUB_DIR,
    DEFAULT_SESSION_FILE,
)
from kindle_download_helper.kindle import Kindle

logger = logging.getLogger("kindle")
fh = logging.FileHandler(".error_books.log")
fh.setLevel(logging.ERROR)
logger.addHandler(fh)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# download selected books for cli
def download_selected_books(kindle, options):
    # get all books and get the default device
    print("Getting all books, please wait...")
    books = kindle.get_all_books(filetype=options.filetype)
    device = kindle.find_device()

    # print all books
    for idx, book in enumerate(books):
        print(
            "Index: "
            + "{:>5d}".format(idx + 1)
            + " | Title: "
            + book["title"]
            + " | asin: "
            + book["asin"]
        )

    # download loop
    while True:
        # get the indices of the books to download
        indices = input(
            "Input the index of books you want to download, split by space (q to quit, l to list books).\n"
        ).split()

        # if input "q", quit
        # if input "l", list all books again
        if indices[0] == "q":
            break
        elif indices[0] == "l":
            for idx, book in enumerate(books):
                print(
                    "Index: "
                    + "{:>5d}".format(idx + 1)
                    + " | Title: "
                    + book["title"]
                    + " | asin: "
                    + book["asin"]
                )
            continue

        # decode the indices
        downlist = []
        flag = True
        for idx in indices:
            if idx.isnumeric() == False:
                if ":" in idx:
                    # if is not a number, and ":" in it, then it is a range
                    # decode the range
                    idx_begin, idx_end = [int(i) for i in idx.split(":")]
                    # append the range to downlist
                    extend_list = [i for i in range(idx_begin - 1, idx_end)]
                    downlist.extend(extend_list)
                else:
                    # if is not a number, and no ":" in it, then it is an error
                    print("Input error, please input numbers!!!")
                    flag = False
                    break
            else:
                # if is a number, then append it to downlist
                downlist.append(int(idx) - 1)
        if not flag:
            continue

        # remove the duplicate indices
        downlist = list(set(downlist))

        # check if the indices are valid
        if max(downlist) >= len(books) or min(downlist) < 0:
            print(
                "Input error, please input numbers between 1 and "
                + str(len(books))
                + "!!!"
            )
            continue

        # print the books to download
        for idx in downlist:
            print(
                "Index: "
                + "{:>5d}".format(idx + 1)
                + " | Title: "
                + books[idx]["title"]
                + " | asin: "
                + books[idx]["asin"]
            )
        print("Downloading " + str(len(downlist)) + " books:")

        # ask if to continue
        while True:
            flag = input("Continue? (y/n)")
            if flag == "y" or flag == "n":
                break
            else:
                print("Input error, please input y or n")
        if flag == "n":
            continue

        # download the books
        for i, idx in enumerate(downlist):
            print(
                "Downloading "
                + str(i + 1)
                + "/"
                + str(len(downlist))
                + " "
                + books[idx]["title"]
                + " ..."
            )
            kindle.download_one_book(books[idx], device, idx, filetype=options.filetype)
        print("Download finished.")


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
        help="if your account is an amazon.co.jp account",
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
        "--uk",
        dest="domain",
        action="store_const",
        const="uk",
        default="com",
        help="if your account is an amazon.co.uk account",
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

    parser.add_argument(
        "--mode",
        dest="mode",
        default="all",
        help="Mode of download, all: download all files at once, sel: download selected files",
    )

    options = parser.parse_args()

    if not os.path.exists(options.outdir):
        os.makedirs(options.outdir)
    # for dedrm
    if not os.path.exists(options.outdedrmdir):
        os.makedirs(options.outdedrmdir)
    # for epub
    if not os.path.exists(options.outepubmdir):
        os.makedirs(options.outepubmdir)

    kindle = Kindle(
        options.csrf_token,
        options.domain,
        options.outdir,
        options.outdedrmdir,
        options.outepubmdir,
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
        # check the download mode
        if options.mode == "all":
            # download all books
            kindle.download_books(
                start_index=options.index - 1, filetype=options.filetype
            )
        elif options.mode == "sel":
            # download selected books
            download_selected_books(kindle, options)
        else:
            print("mode error, please input all or sel")


if __name__ == "__main__":
    main()
