from __future__ import absolute_import, division, print_function, unicode_literals

"""
from .python_transition import (IS_PYTHON2, bytes_, bytes_indexed, bytes_to_hex, bytes_to_list)
if IS_PYTHON2:
    from .python_transition import (chr, html, http, repr, str, urllib)
else:
    import html
    import html.parser
    import html.entities
    import http.client
    import http.cookiejar
    import urllib.request
    import urllib.parse
"""


import sys

IS_PYTHON2 = sys.version_info[0] == 2

if IS_PYTHON2:
    import cgi
    from urllib import quote, quote_plus, unquote, urlencode

    import cookielib
    import htmlentitydefs
    import HTMLParser
    import httplib
    from urllib2 import (
        HTTPCookieProcessor,
        HTTPError,
        HTTPHandler,
        HTTPRedirectHandler,
        HTTPSHandler,
        Request,
        build_opener,
    )
    from urlparse import parse_qs, urljoin, urlparse, urlunparse

    class Object(object):
        pass

    html = Object()
    html.entities = htmlentitydefs
    html.escape = cgi.escape
    html.parser = HTMLParser
    html.unescape = HTMLParser.HTMLParser().unescape

    http = Object()
    http.client = httplib
    http.cookiejar = cookielib

    parse = Object()
    parse.parse_qs = parse_qs
    parse.quote = quote
    parse.quote_plus = quote_plus
    parse.unquote = unquote
    parse.urlencode = urlencode
    parse.urljoin = urljoin
    parse.urlparse = urlparse
    parse.urlunparse = urlunparse

    request = Object()
    request.build_opener = build_opener
    request.HTTPCookieProcessor = HTTPCookieProcessor
    request.HTTPError = HTTPError
    request.HTTPHandler = HTTPHandler
    request.HTTPSHandler = HTTPSHandler
    request.HTTPRedirectHandler = HTTPRedirectHandler
    request.Request = Request

    urllib = Object()
    urllib.parse = parse
    urllib.request = request

    try:
        unicode
        unichr
    except NameError:
        unicode = unichr = None

    py2_chr = chr
    str = unicode
    chr = unichr

    def repr(obj):
        return obj.__repr__()

    class bytes_(bytes):
        def __new__(cls, x):
            if isinstance(x, bytes):
                return x

            if isinstance(x, bytearray):
                return bytes(x)

            if isinstance(x, int):
                return b"\x00" * x

            if isinstance(x, list):
                return b"".join(py2_chr(i) for i in x)

            raise TypeError("Cannot convert %s to bytes" % type(x).__name__)

        @staticmethod
        def fromhex(s):
            if not isinstance(s, str):
                raise TypeError("fromhex %s" % type(s).__name__)

            return s.decode("hex")

    def bytes_indexed(b, i):
        if not isinstance(b, bytes):
            raise TypeError("bytes_indexed %s" % type(b).__name__)

        return ord(b[i])

    def bytes_to_hex(b):
        if not isinstance(b, bytes):
            raise TypeError("bytes_to_hex %s" % type(b).__name__)

        return b.encode("hex").decode("ascii")

    def bytes_to_list(b):
        if not isinstance(b, bytes):
            raise TypeError("bytes_to_list %s" % type(b).__name__)

        return [ord(c) for c in list(b)]

else:
    bytes_ = bytes

    def bytes_indexed(b, i):
        return b[i]

    def bytes_to_hex(b):
        return b.hex()

    def bytes_to_list(data):
        return list(data)
