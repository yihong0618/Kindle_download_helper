#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# k4mobidedrm.py
# Copyright © 2008-2020 by Apprentice Harper et al.

__license__ = "GPL v3"
__version__ = "6.0"


import getopt
import html.entities
import os
import re
import sys
import time
import traceback

import kgenpids
import mobidedrm


class DrmException(Exception):
    pass


# Wrap a stream so that output gets flushed immediately
# and also make sure that any unicode strings get
# encoded using "replace" before writing them.
class SafeUnbuffered:
    def __init__(self, stream):
        self.stream = stream
        self.encoding = stream.encoding
        if self.encoding == None:
            self.encoding = "utf-8"

    def write(self, data):
        if isinstance(data, str):
            data = data.encode(self.encoding, "replace")
        self.stream.buffer.write(data)
        self.stream.buffer.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


iswindows = sys.platform.startswith("win")
isosx = sys.platform.startswith("darwin")


def unicode_argv():
    if iswindows:
        # Uses shell32.GetCommandLineArgvW to get sys.argv as a list of Unicode
        # strings.

        # Versions 2.x of Python don't support Unicode in sys.argv on
        # Windows, with the underlying Windows API instead replacing multi-byte
        # characters with '?'.

        from ctypes import POINTER, byref, c_int, cdll, windll
        from ctypes.wintypes import LPCWSTR, LPWSTR

        GetCommandLineW = cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = LPCWSTR

        CommandLineToArgvW = windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
        CommandLineToArgvW.restype = POINTER(LPWSTR)

        cmd = GetCommandLineW()
        argc = c_int(0)
        argv = CommandLineToArgvW(cmd, byref(argc))
        if argc.value > 0:
            # Remove Python executable and commands if present
            start = argc.value - len(sys.argv)
            return [argv[i] for i in range(start, argc.value)]
        # if we don't have any arguments at all, just pass back script name
        # this should never happen
        return ["mobidedrm.py"]
    else:
        argvencoding = sys.stdin.encoding or "utf-8"
        return [
            arg if isinstance(arg, str) else str(arg, argvencoding) for arg in sys.argv
        ]


# cleanup unicode filenames
# borrowed from calibre from calibre/src/calibre/__init__.py
# added in removal of control (<32) chars
# and removal of . at start and end
# and with some (heavily edited) code from Paul Durrant's kindlenamer.py
# and some improvements suggested by jhaisley
def cleanup_name(name):
    # substitute filename unfriendly characters
    name = (
        name.replace("<", "[")
        .replace(">", "]")
        .replace(" : ", " – ")
        .replace(": ", " – ")
        .replace(":", "—")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("|", "_")
        .replace('"', "'")
        .replace("*", "_")
        .replace("?", "")
    )
    # white space to single space, delete leading and trailing while space
    name = re.sub(r"\s", " ", name).strip()
    # delete control characters
    name = "".join(char for char in name if ord(char) >= 32)
    # delete non-ascii characters
    name = "".join(char for char in name if ord(char) <= 126)
    # remove leading dots
    while len(name) > 0 and name[0] == ".":
        name = name[1:]
    # remove trailing dots (Windows doesn't like them)
    while name.endswith("."):
        name = name[:-1]
    if len(name) == 0:
        name = "DecryptedBook"
    return name


# must be passed unicode
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(html.entities.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text  # leave as is

    return re.sub("&#?\\w+;", fixup, text)


def GetDecryptedBook(infile, serials, pids, starttime=time.time()):
    # handle the obvious cases at the beginning
    if not os.path.isfile(infile):
        raise DrmException("Input file does not exist.")

    mobi = True
    magic8 = open(infile, "rb").read(8)
    if magic8 == b"\xeaDRMION\xee":
        raise DrmException(
            "The .kfx DRMION file cannot be decrypted by itself. A .kfx-zip archive containing a DRM voucher is required."
        )

    magic3 = magic8[:3]
    if magic3 == b"TPZ":
        mobi = False

    if magic8[:4] == b"PK\x03\x04":
        mb = kfxdedrm.KFXZipBook(infile)
    elif mobi:
        mb = mobidedrm.MobiBook(infile)
    else:
        mb = topazextract.TopazBook(infile)

    # copy list of pids
    totalpids = []
    # extend PID list with book-specific PIDs from seriala and kDatabases
    md1, md2 = mb.get_pid_meta_info()
    totalpids = kgenpids.get_pid_list(md1, md2, serials, [])
    # remove any duplicates
    totalpids = list(set(totalpids))
    print(
        "Found {1:d} keys to try after {0:.1f} seconds".format(
            time.time() - starttime, len(totalpids)
        )
    )

    mb.process_book(totalpids)
    print("Decryption succeeded after {0:.1f} seconds".format(time.time() - starttime))
    return mb


# kDatabaseFiles is a list of files created by kindlekey
def decryptBook(infile, outdir, serials, pids):
    starttime = time.time()

    try:
        book = GetDecryptedBook(infile, serials, pids, starttime)
    except Exception as e:
        print(
            "Error decrypting book after {1:.1f} seconds: {0}".format(
                e.args[0], time.time() - starttime
            )
        )
        traceback.print_exc()
        return 1

    # Try to infer a reasonable name
    orig_fn_root = os.path.splitext(os.path.basename(infile))[0]
    if re.match("^B[A-Z0-9]{9}(_EBOK|_EBSP|_sample)?$", orig_fn_root) or re.match(
        "^{0-9A-F-}{36}$", orig_fn_root
    ):  # Kindle for PC / Mac / Android / Fire / iOS
        clean_title = cleanup_name(book.get_book_title())
        outfilename = "{}_{}".format(orig_fn_root, clean_title)
    else:  # E Ink Kindle, which already uses a reasonable name
        outfilename = orig_fn_root

    # avoid excessively long file names
    if len(outfilename) > 150:
        outfilename = outfilename[:99] + "--" + outfilename[-49:]

    outfilename = outfilename + "_nodrm"
    print("!!!=======", book.get_book_extension(), "=========!!!!")
    outfile = os.path.join(outdir, outfilename + book.get_book_extension())

    book.make_drm_file(outfile)
    print(
        "Saved decrypted book {1:s} after {0:.1f} seconds".format(
            time.time() - starttime, outfilename
        )
    )
    return 0


def cli_main():
    argv = unicode_argv()
    print(
        "K4MobiDeDrm v{0}.\nCopyright © 2008-2020 Apprentice Harper et al.".format(
            __version__
        )
    )

    try:
        opts, args = getopt.getopt(argv[1:], "k:p:s:a:h")
    except getopt.GetoptError as err:
        print("Error in options or arguments: {0}".format(err.args[0]))
        sys.exit(2)
    if len(args) < 2:
        sys.exit(2)

    infile = args[0]
    outdir = args[1]
    kDatabaseFiles = []
    androidFiles = []
    serials = []
    pids = []

    for o, a in opts:
        if o == "-h":
            sys.exit(0)
        if o == "-k":
            if a == None:
                raise DrmException("Invalid parameter for -k")
            kDatabaseFiles.append(a)
        if o == "-p":
            if a == None:
                raise DrmException("Invalid parameter for -p")
            pids = a.encode("utf-8").split(b",")
        if o == "-s":
            if a == None:
                raise DrmException("Invalid parameter for -s")
            serials = a.split(",")
        if o == "-a":
            if a == None:
                raise DrmException("Invalid parameter for -a")
            androidFiles.append(a)
    print("!!!!!!!!!", serials)
    return decryptBook(infile, outdir, serials, pids)


if __name__ == "__main__":
    sys.stdout = SafeUnbuffered(sys.stdout)
    sys.stderr = SafeUnbuffered(sys.stderr)
    sys.exit(cli_main())
