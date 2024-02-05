from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import datetime
import decimal
import io
import posixpath
import re
import uuid
import zipfile

from lxml import etree

from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    EPUB2_ALT_MIMETYPES,
    MIMETYPE_OF_EXT,
    make_unique_name,
    urlrelpath,
)

if IS_PYTHON2:
    from .python_transition import str, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


GENERATE_EPUB2_NCX_DOCTYPE = False
REPORT_CONFLICTING_VIEWPORTS = False
CONSOLIDATE_HTML = True
BEAUTIFY_HTML = True
USE_HIDDEN_ATTRIBUTE = True


STANDARD_GUIDE_TYPE = {
    "srl": "text",
}

EPUB3_VOCABULARY_OF_GUIDE_TYPE = {
    "cover": "cover",
    "text": "bodymatter",
    "toc": "toc",
}

DEFAULT_LABEL_OF_GUIDE_TYPE = {
    "cover": "Cover",
    "text": "Beginning",
    "toc": "Table of Contents",
}

TOC_PRIORITY_OF_GUIDE_TYPE = {
    "toc": 1,
    "text": 2,
    "cover": 3,
}

PERIODICAL_NCX_CLASSES = {
    0: "section",
    1: "article",
}

MANIFEST_ITEM_PROPERTIES = {
    "cover-image",
    "mathml",
    "nav",
    "remote-resources",
    "scripted",
    "svg",
    "switch",
}

SPINE_ITEMREF_PROPERTIES = {
    "page-spread-left",
    "page-spread-right",
    "rendition:align-x-center",
    "rendition:flow-auto",
    "rendition:flow-paginated",
    "rendition:flow-scrolled-continuous",
    "rendition:flow-scrolled-doc",
    "rendition:layout-pre-paginated",
    "rendition:layout-reflowable",
    "rendition:orientation-auto",
    "rendition:orientation-landscape",
    "rendition:orientation-portrait",
    "rendition:page-spread-center",
    "rendition:spread-auto",
    "rendition:spread-both",
    "rendition:spread-landscape",
    "rendition:spread-none",
    "rendition:spread-portrait",
    "facing-page-left",
    "facing-page-right",
    "layout-blank",
}

OPF_PROPERTIES = MANIFEST_ITEM_PROPERTIES | SPINE_ITEMREF_PROPERTIES


XML_NS_URI = "http://www.w3.org/XML/1998/namespace"

DC_NS_URI = "http://purl.org/dc/elements/1.1/"
OPF_NS_URI = "http://www.idpf.org/2007/opf"

NCX_NS_URI = "http://www.daisy.org/z3986/2005/ncx/"

XHTML_NS_URI = "http://www.w3.org/1999/xhtml"
EPUB_NS_URI = "http://www.idpf.org/2007/ops"
IDX_NS_URI = "https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf"
MBP_NS_URI = "https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf"

XHTML_NAMESPACES = {
    None: XHTML_NS_URI,
    "epub": EPUB_NS_URI,
    "idx": IDX_NS_URI,
}

SVG_NS_URI = "http://www.w3.org/2000/svg"
XLINK_NS_URI = "http://www.w3.org/1999/xlink"

SVG_NAMESPACES = {
    None: SVG_NS_URI,
    "xlink": XLINK_NS_URI,
}

MATHML_NS_URI = "http://exslt.org/math"

MATHML_NAMESPACES = {
    None: MATHML_NS_URI,
}


RESERVED_OPF_VALUE_PREFIXES = {
    "a11y": "http://www.idpf.org/epub/vocab/package/a11y/#",
    "dcterms": "http://purl.org/dc/terms/",
    "marc": "http://id.loc.gov/vocabulary/",
    "media": "http://www.idpf.org/epub/vocab/overlays/#",
    "onix": "http://www.editeur.org/ONIX/book/codelists/current.html#",
    "rendition": "http://www.idpf.org/vocab/rendition/#",
    "schema": "http://schema.org/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


class OPFProperties(object):
    def __init__(self, opf_properties):
        self.opf_properties = set(opf_properties)

    @property
    def is_fxl(self):
        return "rendition:layout-pre-paginated" in self.opf_properties

    @is_fxl.setter
    def is_fxl(self, value):
        if value:
            self.opf_properties.add("rendition:layout-pre-paginated")
        else:
            self.opf_properties.discard("rendition:layout-pre-paginated")

    @property
    def is_nav(self):
        return "nav" in self.opf_properties

    @is_nav.setter
    def is_nav(self, value):
        if value:
            self.opf_properties.add("nav")
        else:
            self.opf_properties.discard("nav")

    @property
    def is_cover_image(self):
        return "cover-image" in self.opf_properties

    @is_cover_image.setter
    def is_cover_image(self, value):
        if value:
            self.opf_properties.add("cover-image")
        else:
            self.opf_properties.discard("cover-image")


class BookPart(OPFProperties):
    def __init__(
        self,
        filename,
        part_index,
        html,
        opf_properties=set(),
        linear=None,
        omit=False,
        idref=None,
    ):
        self.filename = filename
        self.part_index = part_index
        self.html = html
        OPFProperties.__init__(self, opf_properties)
        self.linear = linear
        self.omit = omit
        self.idref = idref

        self.is_cover_page = False

    def head(self):
        head = self.html.find("head")
        if head is None:
            head = etree.Element("head")
            self.html.insert(0, head)

        return head

    def body(self):
        body = self.html.find("body")
        if body is None:
            body = etree.SubElement(self.html, "body")

        return body


class ManifestEntry(OPFProperties):
    def __init__(self, filename, opf_properties, linear, external, id):
        self.filename = filename
        OPFProperties.__init__(self, opf_properties)
        self.linear = linear
        self.external = external
        self.id = id


class TocEntry(object):
    def __init__(
        self,
        title,
        target=None,
        children=None,
        description=None,
        icon=None,
        anchor=None,
    ):
        self.title = title
        self.target = target
        self.children = children if children else []
        self.description = description
        self.icon = icon
        self.anchor = anchor


class GuideEntry(object):
    def __init__(self, guide_type, title, target=None, anchor=None):
        self.guide_type = guide_type
        self.title = title
        self.target = target
        self.anchor = anchor


class PageMapEntry(object):
    def __init__(self, label, target=None, anchor=None):
        self.label = label
        self.target = target
        self.anchor = anchor

    def __repr__(self):
        return "%s=%s" % (self.label, self.anchor)


class OutputFile(object):
    def __init__(self, binary_data, mimetype, height=None, width=None):
        self.binary_data = binary_data
        self.mimetype = mimetype
        self.height = height
        self.width = width


class EPUB_Output(object):
    DEBUG = False

    GENERATE_EPUB2_COMPATIBLE = True
    PLACE_FILES_IN_SUBDIRS = False

    OEBPS_DIR = "OEBPS"

    OPF_FILEPATH = "/content.opf"
    NCX_FILEPATH = "/toc.ncx"
    TEXT_FILEPATH = "/part%04d.xhtml"
    NAV_FILEPATH = "/nav%s.xhtml"
    FONT_FILEPATH = "/%s"
    IMAGE_FILEPATH = "/%s"
    PDF_FILEPATH = "/%s"
    STYLES_CSS_FILEPATH = "/stylesheet.css"
    RESET_CSS_FILEPATH = "/reset.css"
    LAYOUT_CSS_FILEPATH = "/layout%04d.css"

    if PLACE_FILES_IN_SUBDIRS:
        TEXT_FILEPATH = "/xhtml" + TEXT_FILEPATH
        NAV_FILEPATH = "/xhtml" + NAV_FILEPATH
        FONT_FILEPATH = "/fonts" + FONT_FILEPATH
        IMAGE_FILEPATH = "/images" + IMAGE_FILEPATH
        PDF_FILEPATH = "/misc" + PDF_FILEPATH
        STYLES_CSS_FILEPATH = "/css" + STYLES_CSS_FILEPATH
        RESET_CSS_FILEPATH = "/css" + RESET_CSS_FILEPATH
        LAYOUT_CSS_FILEPATH = "/css" + LAYOUT_CSS_FILEPATH

    def __init__(self, epub2_desired=False):
        self.epub2_desired = epub2_desired
        self.generate_epub2 = epub2_desired

        self.oebps_files = {}
        self.book_parts = []
        self.ncx_toc = []
        self.manifest = []
        self.manifest_files = {}
        self.manifest_ids = set()
        self.guide = []
        self.css_files = set()
        self.pagemap = []

        self.asin = ""
        self.title = ""
        self.title_pronunciation = ""
        self.authors = []
        self.author_pronunciations = []
        self.publisher = ""
        self.pubdate = ""
        self.description = ""
        self.subject = ""
        self.rights = ""
        self.language = ""
        self.source_language = self.target_language = ""
        self.is_sample = False
        self.is_dictionary = False
        self.override_kindle_font = False
        self.ncx_location = None
        self.toc_ncx_id = None
        self.orientation_lock = "none"
        self.min_aspect_ratio = self.max_aspect_ratio = None
        self.original_width = self.original_height = None
        self.fixed_layout = False
        self.region_magnification = False
        self.virtual_panels = False
        self.illustrated_layout = False
        self.html_cover = False
        self.guided_view_native = False
        self.remove_html_cover = False
        self.scrolled_continuous = False

        self.set_book_type(None)
        self.set_primary_writing_mode("horizontal-lr")

        log.info("Converting book to EPUB %s" % ("2" if self.generate_epub2 else "3"))

    def set_book_type(self, book_type):
        self.book_type = book_type
        self.is_children = self.is_comic = self.is_magazine = self.is_print_replica = (
            False
        )

        if self.book_type is None:
            pass
        elif self.book_type == "children":
            self.is_children = True
        elif self.book_type == "comic":
            self.is_comic = True
        elif self.book_type == "magazine":
            self.is_magazine = True
        elif self.book_type == "print replica":
            self.is_print_replica = True
        else:
            log.error("Unexpected bookType: %s" % self.book_type)

    def set_primary_writing_mode(self, primary_writing_mode):
        if primary_writing_mode == "horizontal-lr":
            self.writing_mode = "horizontal-tb"
            self.page_progression_direction = "ltr"
        elif primary_writing_mode == "horizontal-rl":
            self.writing_mode = "horizontal-tb"
            self.page_progression_direction = "rtl"
        elif primary_writing_mode == "vertical-rl":
            self.writing_mode = "vertical-tb"
            self.page_progression_direction = "rtl"
        else:
            log.error("Unexpected PrimaryWritingMode: %s" % primary_writing_mode)

    def manifest_resource(
        self,
        filename,
        opf_properties=None,
        linear=None,
        external=False,
        data=None,
        mimetype=None,
        height=None,
        width=None,
        idref=None,
        report_dupe=True,
    ):
        if filename in self.manifest_files:
            if report_dupe:
                log.error("Duplicate file name in manifest: %s" % filename)

            return

        idref = self.fix_html_id(idref or filename.rpartition("/")[2][:64])
        idref = make_unique_name(idref, self.manifest_ids, sep="_")

        manifest_entry = ManifestEntry(
            filename, opf_properties or set(), linear, external, id=idref
        )
        self.manifest.append(manifest_entry)
        self.manifest_files[filename] = manifest_entry
        self.manifest_ids.add(idref)

        if data is not None:
            self.add_oebps_file(
                filename,
                data,
                mimetype or self.mimetype_of_filename(filename),
                height,
                width,
            )

        return manifest_entry

    def add_guide_entry(self, guide_type, title, target=None, anchor=None):
        std_guide_type = STANDARD_GUIDE_TYPE.get(guide_type, guide_type)

        self.guide.append(
            GuideEntry(
                std_guide_type,
                title or DEFAULT_LABEL_OF_GUIDE_TYPE.get(std_guide_type) or guide_type,
                target=target,
                anchor=anchor,
            )
        )

    def add_pagemap_entry(self, label, target=None, anchor=None):
        self.pagemap.append(PageMapEntry(label, target=target, anchor=anchor))

    def add_oebps_file(self, filename, binary_data, mimetype, height=None, width=None):
        self.oebps_files[filename] = OutputFile(binary_data, mimetype, height, width)

    def generate_epub(self):
        if self.asin:
            self.uid = "urn:asin:" + self.asin
        else:
            self.uid = "urn:uuid:" + str(uuid.uuid4())

        if not self.authors:
            self.authors = ["Unknown"]

        if not self.title:
            self.title = "Unknown"

        if self.is_sample:
            self.title += " - Sample"

        desc = []
        if self.is_dictionary:
            desc.append("dictionary")
        if self.is_sample:
            desc.append("sample")
        if self.fixed_layout:
            desc.append("fixed layout")
        if self.illustrated_layout:
            desc.append("illustrated layout")
        if self.book_type:
            desc.append(self.book_type)

        if desc:
            log.info("Format is %s" % " ".join(desc))

        if len(self.ncx_toc) == 0 and self.book_parts:
            for g in sorted(
                self.guide,
                key=lambda g: TOC_PRIORITY_OF_GUIDE_TYPE.get(g.guide_type, 999),
            ):
                self.ncx_toc.append(TocEntry(g.title, target=g.target))
                break
            else:
                if self.book_parts:
                    self.ncx_toc.append(
                        TocEntry("Content", target=self.book_parts[0].filename)
                    )

        self.check_epub_version()

        self.identify_cover()
        if self.remove_html_cover:
            self.do_remove_html_cover()

        if not self.generate_epub2:
            for book_part in self.book_parts:
                if book_part.is_nav:
                    break
            else:
                self.create_epub3_nav()

        if (
            self.fixed_layout
            and (not self.is_print_replica)
            and (self.original_height is None or self.original_width is None)
        ):
            self.compare_fixed_layout_viewports()

        self.save_book_parts()

        if self.ncx_location is None and (
            self.generate_epub2 or self.GENERATE_EPUB2_COMPATIBLE
        ):
            self.create_ncx()

        self.create_opf()

        if self.generate_epub2 is not self.epub2_desired:
            log.warning(
                "Book converted to EPUB %s to accommodate content not supported in EPUB %s"
                % (
                    "2" if self.generate_epub2 else "3",
                    "2" if self.epub2_desired else "3",
                )
            )

        return self.zip_epub()

    def fix_html_id(self, id):
        if self.illustrated_layout:
            id = id.replace(".", "_")

        id = re.sub(
            "[\u0660-\u0669\u06f0-\u06f9]",
            lambda m: chr((ord(m.group()) & 0x0F) + 0x30),
            id,
        )

        id = re.sub(r"[^A-Za-z0-9_.-]", "_", id)

        if len(id) == 0 or not re.match(r"^[A-Za-z]", id):
            id = "id_" + id

        return id

    def new_book_part(
        self,
        filename=None,
        opf_properties=set(),
        linear=True,
        omit=False,
        html=None,
        idref=None,
    ):
        part_index = len(self.book_parts)

        if filename is None:
            filename = self.TEXT_FILEPATH % part_index

        if html is None:
            html = new_xhtml()

        book_part = BookPart(
            filename, part_index, html, opf_properties, linear, omit, idref
        )
        self.book_parts.append(book_part)

        if self.DEBUG:
            log.debug("new_book_part %s" % filename)

        return book_part

    def link_css_file(self, book_part, css_file, css_type="text/css"):
        self.css_files.add(css_file)
        link = etree.SubElement(book_part.html.find("head"), "link")
        link.set("rel", "stylesheet")
        link.set("type", css_type)
        link.set(
            "href",
            urllib.parse.quote(urlrelpath(css_file, ref_from=book_part.filename)),
        )

    def identify_cover(self):
        if self.book_parts:
            for g in sorted(self.guide, key=lambda ge: (ge.guide_type, ge.title)):
                if g.guide_type == "cover":
                    cover_page = remove_url_fragment(g.target)
                    break
            else:
                for manifest_entry in self.manifest:
                    if manifest_entry.is_cover_image:
                        cover_page = self.book_parts[0].filename
                        break
                else:
                    cover_page = None

            if cover_page:
                for book_part in self.book_parts:
                    if book_part.filename == cover_page:
                        book_part.is_cover_page = True

                        if book_part.part_index != 0:
                            log.warning(
                                "Cover page is not first in book: %s" % cover_page
                            )

                        break
                else:
                    log.warning("Cover page %s not found in book" % cover_page)

    def do_remove_html_cover(self):
        for i, book_part in enumerate(self.book_parts):
            if book_part.is_cover_page:
                self.book_parts.pop(i)
                break

        for i, g in enumerate(self.guide):
            if g.guide_type == "cover":
                self.guide.pop(i)
                break

    def is_book_part_filename(self, filename):
        for book_part in self.book_parts:
            if book_part.filename == filename:
                return False

        return True

    def compare_fixed_layout_viewports(self):
        viewport_count = collections.defaultdict(int)
        for book_part in self.book_parts:
            if not book_part.is_cover_page:
                head = book_part.html.find("head")
                if head is not None:
                    for meta in head.iterfind("meta"):
                        if meta.get("name") == "viewport":
                            content = meta.get("content", "")
                            mw = re.search("width=([0-9]+)", content)
                            mh = re.search("height=([0-9]+)", content)
                            if mw and mh:
                                viewport_count[
                                    (int(mw.group(1)), int(mh.group(1)))
                                ] += 1

        if len(viewport_count) == 0:
            log.error("No viewports found for fixed layout book")
        else:
            viewports_by_count = sorted(viewport_count.items(), key=lambda x: -x[1])
            self.original_width, self.original_height = viewports_by_count[0][0]

            viewports_by_size = sorted(
                viewport_count.items(), key=lambda x: -(x[0][0] + x[0][1])
            )
            best_width, best_height = viewports_by_size[0][0]
            if self.original_width != best_width or self.original_height != best_height:
                log.info(
                    "Largest viewport is not the most common: %s"
                    % (
                        ", ".join(
                            [
                                "%dw x %dh (%d)" % (fw, fh, ct)
                                for (fw, fh), ct in viewports_by_size
                            ]
                        )
                    )
                )
            elif len(viewports_by_count) > 1 and REPORT_CONFLICTING_VIEWPORTS:
                log.warning(
                    "Conflicting viewport sizes (best %dw x %dh): %s"
                    % (
                        best_width,
                        best_height,
                        ", ".join(
                            [
                                "%dw x %dh (%d)" % (fw, fh, ct)
                                for (fw, fh), ct in viewports_by_count
                            ]
                        ),
                    )
                )

    def check_epub_version(self):
        if not self.generate_epub2:
            return

        if self.fixed_layout or self.author_pronunciations or self.title_pronunciation:
            self.generate_epub2 = False
            return

        for oebps_file in self.oebps_files.values():
            if oebps_file.mimetype in [
                "application/octet-stream",
                "application/xml",
                "text/javascript",
                "text/html",
            ]:
                self.generate_epub2 = False
                return

        for book_part in self.book_parts:
            if book_part.is_nav or book_part.is_fxl:
                self.generate_epub2 = False
                return

            for elem in book_part.html.iter("*"):
                if elem.tag in {
                    "article",
                    "aside",
                    "audio",
                    "bdi",
                    "canvas",
                    "details",
                    "dialog",
                    "embed",
                    "figcaption",
                    "figure",
                    "footer",
                    "header",
                    "main",
                    "mark",
                    "meter",
                    "nav",
                    "picture",
                    "progress",
                    "rt",
                    "ruby",
                    "section",
                    "source",
                    "summary",
                    "template",
                    "time",
                    "track",
                    "video",
                    "wbr",
                }:
                    self.generate_epub2 = False
                    return

                for attrib in elem.attrib.keys():
                    if attrib.startswith("data-") or attrib in [EPUB_PREFIX, EPUB_TYPE]:
                        self.generate_epub2 = False
                        return

    def save_book_parts(self):
        for book_part in self.book_parts:
            if self.DEBUG:
                log.debug(
                    "%s: %s" % (book_part.filename, etree.tostring(book_part.html))
                )

            book_part.html.tag = HTML

            head = book_part.head()
            body = book_part.body()

            if head.find("title") is None:
                title = etree.SubElement(head, "title")
                title.text = book_part.filename.replace("/", "").replace(".xhtml", "")

            if CONSOLIDATE_HTML:
                self.consolidate_html(body)

            if BEAUTIFY_HTML:
                self.beautify_html(book_part)

            if body.find(".//%s" % SVG) is not None:
                book_part.opf_properties.add("svg")

            if body.find(".//{*}math") is not None:
                book_part.opf_properties.add("mathml")

            for e in body.iterfind(".//*[@src]"):
                src = e.get("src", "")
                if src.startswith("http://") or src.startswith("https://"):
                    book_part.opf_properties.add("remote-resources")
                    break

            for e in body.iterfind(".//*"):
                if e.get(EPUB_TYPE, "").startswith("amzn:"):
                    book_part.html.set(
                        qname(EPUB_NS_URI, "prefix"),
                        "amzn: https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf",
                    )
                    break

            etree.cleanup_namespaces(book_part.html)

            if self.DEBUG:
                log.debug(
                    "%s: %s" % (book_part.filename, etree.tostring(book_part.html))
                )

            if not book_part.omit:
                document = etree.ElementTree(book_part.html)
                doctype = b"<!DOCTYPE html>"
                doctype = b"<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' 'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'>"

                html_str = etree.tostring(
                    document, encoding="utf-8", doctype=doctype, xml_declaration=True
                )

                if not self.generate_epub2:
                    html_str = html_str.replace(doctype + b"\n", b"")

                self.manifest_resource(
                    book_part.filename,
                    book_part.opf_properties,
                    book_part.linear,
                    idref=book_part.idref,
                    data=html_str,
                    mimetype="application/xhtml+xml",
                )

    def consolidate_html(self, body):
        for toptag in body.findall("*"):
            changed = True
            while changed:
                changed = False
                for e in toptag.iterdescendants():
                    if e.tag in {
                        "a",
                        "b",
                        "em",
                        "i",
                        "span",
                        "strong",
                        "sub",
                        "sup",
                        "u",
                    }:
                        n = e.getnext()
                        while (
                            (not e.tail)
                            and (n is not None)
                            and n.tag == e.tag
                            and tuple(sorted(dict(e.attrib).items()))
                            == tuple(sorted(dict(n.attrib).items()))
                        ):
                            if n.text:
                                if len(e) > 0:
                                    tt = e[-1]
                                    tt.tail = (tt.tail + n.text) if tt.tail else n.text
                                else:
                                    e.text = (e.text + n.text) if e.text else n.text

                                n.text = ""

                            while len(n) > 0:
                                c = n[0]
                                n.remove(c)
                                e.append(c)

                            if n.tail:
                                e.tail = n.tail

                            n.getparent().remove(n)

                            changed = True

                            n = e.getnext()

                        if changed:
                            break

        TEMP_TAG = "temporary-tag"
        temp_tag_used = False

        for e in body.iter("span"):
            if e.tag == "span" and len(e.attrib) == 0:
                e.tag = TEMP_TAG
                temp_tag_used = True

        if temp_tag_used:
            etree.strip_tags(body, TEMP_TAG)
            temp_tag_used = False

        while True:
            for e in body.iter("div"):
                if len(e.attrib) == 0:
                    parent = e.getparent()
                    if len(parent) == 1 and not parent.text:
                        if parent.tag in {
                            "aside",
                            "div",
                            "figure",
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                            "li",
                            "td",
                            "caption",
                            IDX_ENTRY,
                        }:
                            e.tag = TEMP_TAG
                        elif parent.tag == "body" and not e.text:
                            for child in e.iterfind("*"):
                                if (
                                    child.tag
                                    not in {
                                        "aside",
                                        "div",
                                        "figure",
                                        "h1",
                                        "h2",
                                        "h3",
                                        "h4",
                                        "h5",
                                        "h6",
                                        "hr",
                                        "iframe",
                                        "ol",
                                        "table",
                                        "ul",
                                        IDX_ENTRY,
                                    }
                                    or child.tail
                                ):
                                    break
                            else:
                                e.tag = TEMP_TAG

                        if e.tag == TEMP_TAG:
                            etree.strip_tags(parent, TEMP_TAG)
                            break
            else:
                break

    def beautify_html(self, book_part):
        html = book_part.html
        head = book_part.head()
        body = book_part.body()

        for e in [html] + html.findall("*") + head.findall("*") + body.findall("*"):
            if e.tag in {HTML, "head", "body"}:
                e.text = (e.text or "") + "\n"

            if e.tag in {
                "head",
                "title",
                "link",
                "meta",
                "style",
                "body",
                "aside",
                "div",
                "figure",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "hr",
                "nav",
                "table",
                "ul",
                "ol",
                IDX_ENTRY,
            }:
                e.tail = (e.tail or "") + "\n"

            if e.tag == "div" and e.get("id", "").startswith("amzn_master_range_"):
                for ee in e.iterfind("*"):
                    if (
                        ee.tag
                        in {
                            "aside",
                            "div",
                            "figure",
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                            "hr",
                            "table",
                            "ul",
                            "ol",
                            IDX_ENTRY,
                        }
                        and not ee.tail
                    ):
                        ee.tail = "\n"

    def create_opf(self):
        def add_metadata_meta_name_content(name, content):
            add_meta_name_content(metadata, name, content)

        def add_metadata_meta_property(prop, text):
            meta_property = add_attribs(
                etree.SubElement(metadata, "meta"), "property", prop
            )
            meta_property.text = text

        def add_metadata_meta_refines_property(refines, prop, text, scheme=None):
            meta_refines = add_attribs(
                etree.SubElement(metadata, "meta"), "refines", refines, "property", prop
            )
            if scheme:
                meta_refines.set("scheme", scheme)
            meta_refines.text = text

        def prefix(value):
            if ":" in value:
                used_prefixes.add(value.partition(":")[0])
            return value

        used_prefixes = set()

        ALT_OPF_NS_URI = OPF_NS_URI + "?"
        OPF_NAMESPACES = {
            None: OPF_NS_URI,
            "dc": DC_NS_URI,
            "opf": ALT_OPF_NS_URI,
        }
        package = etree.Element(
            qname(OPF_NS_URI, "package"),
            nsmap=OPF_NAMESPACES,
            attrib={
                "version": ("2.0" if self.generate_epub2 else "3.0"),
                "unique-identifier": "bookid",
            },
        )

        metadata = etree.SubElement(package, "metadata")

        identifier = etree.SubElement(
            metadata, qname(DC_NS_URI, "identifier"), attrib={"id": "bookid"}
        )
        identifier.text = self.uid

        if self.uid.startswith("urn:uuid:") and self.generate_epub2:
            identifier.set(qname(ALT_OPF_NS_URI, "scheme"), "uuid")

        title = etree.SubElement(metadata, qname(DC_NS_URI, "title"))
        title.text = self.title
        if self.title_pronunciation and not self.generate_epub2:
            title.set("id", "title")
            add_metadata_meta_refines_property(
                "#title", "alternate-script", self.title_pronunciation
            )

        for i, author in enumerate(self.authors):
            creator = etree.SubElement(metadata, qname(DC_NS_URI, "creator"))
            creator.text = author

            if not self.generate_epub2:
                author_id = "creator%d" % i
                creator.set("id", author_id)

                add_metadata_meta_refines_property(
                    "#" + author_id, "role", "aut", prefix("marc:relators")
                )

                if len(self.author_pronunciations) > i:
                    add_metadata_meta_refines_property(
                        "#" + author_id,
                        "alternate-script",
                        self.author_pronunciations[i],
                    )
            else:
                creator.set(qname(ALT_OPF_NS_URI, "role"), "aut")

        language = etree.SubElement(metadata, qname(DC_NS_URI, "language"))
        language.text = self.language if self.language else "und"

        if self.publisher:
            publisher = etree.SubElement(metadata, qname(DC_NS_URI, "publisher"))
            publisher.text = self.publisher

        if self.pubdate:
            pubdate = etree.SubElement(metadata, qname(DC_NS_URI, "date"))

            if self.generate_epub2:
                pubdate.set(qname(ALT_OPF_NS_URI, "event"), "publication")

            pubdate.text = str(self.pubdate)[0:10]

        if self.description:
            description = etree.SubElement(metadata, qname(DC_NS_URI, "description"))
            description.text = self.description

        if self.subject:
            subject = etree.SubElement(metadata, qname(DC_NS_URI, "subject"))
            subject.text = self.subject

        if self.rights:
            rights = etree.SubElement(metadata, qname(DC_NS_URI, "rights"))
            rights.text = self.rights

        if not self.generate_epub2:
            add_metadata_meta_property(
                "dcterms:modified",
                datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            )

        if self.fixed_layout:
            if not self.generate_epub2:
                add_metadata_meta_property(prefix("rendition:layout"), "pre-paginated")

            add_metadata_meta_name_content("fixed-layout", "true")

            if self.original_width and self.original_height:
                if self.orientation_lock == "none":
                    self.orientation_lock = (
                        "landscape"
                        if self.original_width > self.original_height
                        else "portrait"
                    )

                add_metadata_meta_name_content(
                    "original-resolution",
                    "%dx%d" % (self.original_width, self.original_height),
                )

        if self.scrolled_continuous and not self.generate_epub2:
            add_metadata_meta_property(prefix("rendition:flow"), "scrolled-continuous")

        if self.book_type in {"children", "comic"}:
            add_metadata_meta_name_content("book-type", self.book_type)

        if self.orientation_lock != "none":
            if not self.generate_epub2:
                add_metadata_meta_property(
                    prefix("rendition:orientation"),
                    (
                        self.orientation_lock
                        if self.orientation_lock != "none"
                        else "auto"
                    ),
                )

            add_metadata_meta_name_content("orientation-lock", self.orientation_lock)

        if self.override_kindle_font:
            add_metadata_meta_name_content("Override-Kindle-Fonts", "true")

        if self.writing_mode == "horizontal-tb":
            primary_writing_mode = (
                "horizontal-rl"
                if self.page_progression_direction == "rtl"
                else "horizontal-lr"
            )
        else:
            primary_writing_mode = self.writing_mode

        if primary_writing_mode != "horizontal-lr":
            add_metadata_meta_name_content("primary-writing-mode", primary_writing_mode)

        if self.region_magnification:
            add_metadata_meta_name_content("RegionMagnification", "true")

            if self.virtual_panels:
                log.error("Virtual panels used with region magnification")

        if self.illustrated_layout:
            add_metadata_meta_name_content("amzn:kindle-illustrated", "true")

        if self.html_cover:
            add_metadata_meta_name_content("amzn:cover-as-html", "true")

        if self.guided_view_native:
            add_metadata_meta_name_content("amzn:guided-view-native", "true")

        if self.min_aspect_ratio:
            add_metadata_meta_name_content(
                "amzn:min-aspect-ratio", value_str(self.min_aspect_ratio)
            )

        if self.max_aspect_ratio:
            add_metadata_meta_name_content(
                "amzn:max-aspect-ratio", value_str(self.max_aspect_ratio)
            )

        if self.is_dictionary:
            x_metadata = etree.SubElement(metadata, "x-metadata")

            in_language = etree.SubElement(x_metadata, "DictionaryInLanguage")
            in_language.text = self.source_language

            out_language = etree.SubElement(x_metadata, "DictionaryOutLanguage")
            out_language.text = self.target_language

        if self.is_magazine:
            x_metadata = etree.SubElement(metadata, "x-metadata")

            etree.SubElement(
                x_metadata,
                "output",
                attrib={
                    "content-type": "application/x-mobipocket-subscription-magazine",
                    "encoding": "utf-8",
                },
            )

        if used_prefixes:
            package.set(
                "prefix",
                " ".join(
                    [
                        "%s: %s" % (p, RESERVED_OPF_VALUE_PREFIXES[p])
                        for p in sorted(list(used_prefixes))
                    ]
                ),
            )

        man = etree.SubElement(package, "manifest")
        toc_idref = None

        for manifest_entry in sorted(self.manifest, key=lambda m: m.filename):
            if (
                manifest_entry.filename == self.ncx_location
                or manifest_entry.filename.endswith(".ncx")
            ):
                toc_idref = manifest_entry.id

            if manifest_entry.external:
                mimetype = self.mimetype_of_filename(manifest_entry.filename)
                href = manifest_entry.filename
            else:
                mimetype = self.oebps_files[manifest_entry.filename].mimetype
                href = urlrelpath(
                    urllib.parse.quote(manifest_entry.filename),
                    ref_from=self.OPF_FILEPATH,
                )

            if self.generate_epub2:
                mimetype = EPUB2_ALT_MIMETYPES.get(mimetype, mimetype)

            item = etree.SubElement(
                man,
                "item",
                attrib={"href": href, "id": manifest_entry.id, "media-type": mimetype},
            )

            if manifest_entry.is_cover_image and not (self.html_cover or self.is_comic):
                add_metadata_meta_name_content("cover", manifest_entry.id)

            if self.fixed_layout:
                if manifest_entry.is_fxl:
                    manifest_entry.opf_properties.discard(
                        "rendition:layout-pre-paginated"
                    )
                else:
                    manifest_entry.opf_properties.add("rendition:layout-reflowable")

            item_properties = manifest_entry.opf_properties & MANIFEST_ITEM_PROPERTIES
            if len(item_properties) and not self.generate_epub2:
                item.set("properties", " ".join(sorted(list(item_properties))))

            unknown_properties = manifest_entry.opf_properties - OPF_PROPERTIES
            if len(unknown_properties):
                log.error(
                    'Manifest file %s has %d unknown OPF properties: "%s"'
                    % (
                        manifest_entry.filename,
                        len(unknown_properties),
                        " ".join(sorted(list(unknown_properties))),
                    )
                )

        spine = etree.SubElement(package, "spine")

        if (self.generate_epub2 or self.GENERATE_EPUB2_COMPATIBLE) and toc_idref:
            spine.set("toc", toc_idref)

        if self.page_progression_direction != "ltr" and not self.generate_epub2:
            spine.set("page-progression-direction", self.page_progression_direction)

        for manifest_entry in self.manifest:
            if manifest_entry.linear is not None:
                itemref = etree.SubElement(
                    spine, "itemref", attrib={"idref": manifest_entry.id}
                )

                itemref_properties = (
                    manifest_entry.opf_properties & SPINE_ITEMREF_PROPERTIES
                )
                if len(itemref_properties) and not self.generate_epub2:
                    itemref.set(
                        "properties",
                        " ".join([prefix(p) for p in sorted(list(itemref_properties))]),
                    )

                if manifest_entry.linear is False:
                    itemref.set("linear", "no")

        if self.guide and (self.generate_epub2 or self.GENERATE_EPUB2_COMPATIBLE):
            gd = etree.SubElement(package, "guide")

            for g in self.guide:
                etree.SubElement(
                    gd,
                    "reference",
                    attrib={
                        "type": g.guide_type,
                        "title": g.title,
                        "href": urlrelpath(g.target, ref_from=self.OPF_FILEPATH),
                    },
                )

        etree.cleanup_namespaces(package)

        data = etree.tostring(
            package, encoding="utf-8", pretty_print=True, xml_declaration=True
        )
        data = data.replace(ALT_OPF_NS_URI.encode("utf-8"), OPF_NS_URI.encode("utf-8"))

        self.add_oebps_file(self.OPF_FILEPATH, data, "application/oebps-package+xml")

    def container_xml(self):
        NS_URI = "urn:oasis:names:tc:opendocument:xmlns:container"
        container = etree.Element(
            qname(NS_URI, "container"), nsmap={None: NS_URI}, attrib={"version": "1.0"}
        )
        rootfiles = etree.SubElement(container, "rootfiles")
        etree.SubElement(
            rootfiles,
            "rootfile",
            attrib={
                "full-path": (self.OEBPS_DIR + self.OPF_FILEPATH),
                "media-type": "application/oebps-package+xml",
            },
        )

        return etree.tostring(
            container, encoding="utf-8", pretty_print=True, xml_declaration=True
        )

    def create_ncx(self):
        doctype = (
            None
            if not (self.generate_epub2 or GENERATE_EPUB2_NCX_DOCTYPE)
            else '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
        )

        emit_playorder = doctype is not None

        NCX_NAMESPACES = {None: NCX_NS_URI, "mbp": MBP_NS_URI}

        ncx = etree.Element(
            qname(NCX_NS_URI, "ncx"), nsmap=NCX_NAMESPACES, attrib={"version": "2005-1"}
        )
        head = etree.SubElement(ncx, "head")
        add_meta_name_content(head, "dtb:uid", self.uid)

        doc_title = etree.SubElement(ncx, ("docTitle"))
        doc_title_text = etree.SubElement(doc_title, "text")
        doc_title_text.text = self.title

        for author in self.authors:
            doc_author = etree.SubElement(ncx, "docAuthor")
            doc_author_text = etree.SubElement(doc_author, "text")
            doc_author_text.text = author

        self.nav_id_count = 0
        self.uri_playorder = {}

        nav_map = etree.SubElement(ncx, "navMap")
        self.create_navmap(nav_map, self.ncx_toc, emit_playorder, 0)

        if len(self.pagemap) > 0:
            pl = etree.SubElement(ncx, "pageList")

            nl = etree.SubElement(pl, "navLabel")
            nlt = etree.SubElement(nl, "text")
            nlt.text = "Pages"
            page_ids = set()

            for p in self.pagemap:
                pt = etree.SubElement(pl, "pageTarget")

                p_id = make_unique_name(
                    self.fix_html_id("page_%s" % p.label), page_ids, sep="_"
                )
                pt.set("id", p_id)
                page_ids.add(p_id)

                if re.match("^[0-9]+$", p.label):
                    pt.set("value", p.label)
                    pt.set("type", "normal")
                elif re.match("^[ivx]+$", p.label, flags=re.IGNORECASE):
                    pt.set("value", str(roman_to_int(p.label)))
                    pt.set("type", "front")
                else:
                    pt.set("type", "special")

                if emit_playorder:
                    pt.set("playOrder", self.get_next_playorder(p.target))

                nl = etree.SubElement(pt, "navLabel")
                nlt = etree.SubElement(nl, "text")
                nlt.text = p.label

                ct = etree.SubElement(pt, "content")
                ct.set("src", urlrelpath(p.target, ref_from=self.NCX_FILEPATH))

        etree.cleanup_namespaces(ncx)

        data = etree.tostring(
            ncx,
            encoding="utf-8",
            pretty_print=True,
            xml_declaration=True,
            doctype=doctype,
        )
        self.manifest_resource(
            self.NCX_FILEPATH,
            idref=self.toc_ncx_id,
            data=data,
            mimetype="application/x-dtbncx+xml",
        )
        self.ncx_location = self.NCX_FILEPATH

    def get_next_playorder(self, uri):
        if (uri not in self.uri_playorder) or (uri is None):
            self.uri_playorder[uri] = "%d" % (len(self.uri_playorder) + 1)

        return self.uri_playorder[uri]

    def create_navmap(self, root, ncx_toc, emit_playorder, depth):
        for toc_entry in ncx_toc:
            nav_point = etree.SubElement(
                root, "navPoint", attrib={"id": "nav%d" % self.nav_id_count}
            )

            if self.is_magazine and depth in PERIODICAL_NCX_CLASSES:
                nav_point.set("class", PERIODICAL_NCX_CLASSES[depth])

            if emit_playorder:
                nav_point.set("playOrder", self.get_next_playorder(toc_entry.target))

            self.nav_id_count += 1

            nav_label = etree.SubElement(nav_point, "navLabel")
            nav_label_text = etree.SubElement(nav_label, "text")
            nav_label_text.text = toc_entry.title

            if toc_entry.target:
                etree.SubElement(
                    nav_point,
                    "content",
                    attrib={
                        "src": urlrelpath(toc_entry.target, ref_from=self.NCX_FILEPATH)
                    },
                )

            if toc_entry.description:
                meta = etree.SubElement(
                    nav_point, qname(MBP_NS_URI, "meta"), attrib={"name": "description"}
                )
                meta.text = toc_entry.description

            if toc_entry.icon:
                meta = etree.SubElement(
                    nav_point,
                    qname(MBP_NS_URI, "meta-img"),
                    attrib={
                        "name": "mastheadImage",
                        "src": urlrelpath(toc_entry.icon, ref_from=self.NCX_FILEPATH),
                    },
                )

            if toc_entry.children:
                self.create_navmap(
                    nav_point, toc_entry.children, emit_playorder, depth + 1
                )

    def create_epub3_nav(self):
        filename = self.NAV_FILEPATH % ""

        count = 0
        while not self.is_book_part_filename(filename):
            filename = self.NAV_FILEPATH % ("%d" % count)
            count += 1

        book_part = self.new_book_part(filename=filename, linear=None)
        book_part.is_nav = True

        body = etree.SubElement(book_part.html, "body")

        nav = etree.SubElement(body, "nav")
        nav.set(EPUB_TYPE, "toc")

        if not self.is_magazine:
            self.hide_element(nav)

        h1 = etree.SubElement(nav, "h1")
        h1.text = "Table of contents"

        self.create_nav_list(nav, self.ncx_toc, book_part)

        if self.guide:
            nav = etree.SubElement(body, "nav")
            nav.set(EPUB_TYPE, "landmarks")

            if not self.is_magazine:
                self.hide_element(nav)

            h2 = etree.SubElement(nav, "h2")
            h2.text = "Guide"

            ol = etree.SubElement(nav, "ol")

            for g in sorted(self.guide, key=lambda ge: (ge.guide_type, ge.title)):
                li = etree.SubElement(ol, "li")
                a = etree.SubElement(li, "a")

                if g.guide_type in EPUB3_VOCABULARY_OF_GUIDE_TYPE:
                    a.set(EPUB_TYPE, EPUB3_VOCABULARY_OF_GUIDE_TYPE[g.guide_type])

                a.set("href", urlrelpath(g.target, ref_from=book_part.filename))
                a.text = g.title

        if len(self.pagemap) > 0:
            nav = etree.SubElement(body, "nav")
            nav.set(EPUB_TYPE, "page-list")

            if not self.is_magazine:
                self.hide_element(nav)

            ol = etree.SubElement(nav, "ol")

            for p in self.pagemap:
                li = etree.SubElement(ol, "li")
                a = etree.SubElement(
                    li,
                    "a",
                    attrib={"href": urlrelpath(p.target, ref_from=book_part.filename)},
                )
                a.text = p.label

    def hide_element(self, elem):
        if USE_HIDDEN_ATTRIBUTE:
            elem.set("hidden", "")
        else:
            self.add_style(elem, {"display": "none"})

    def create_nav_list(self, parent, ncx_toc, book_part):
        ol = etree.SubElement(parent, "ol")

        for toc_entry in ncx_toc:
            li = etree.SubElement(ol, "li")
            a = etree.SubElement(li, "a")
            a.text = toc_entry.title or "."

            if toc_entry.target:
                a.set("href", urlrelpath(toc_entry.target, ref_from=book_part.filename))

            if toc_entry.children:
                self.create_nav_list(li, toc_entry.children, book_part)

    def zip_epub(self):
        file = io.BytesIO()

        with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "mimetype",
                "application/epub+zip".encode("ascii"),
                compress_type=zipfile.ZIP_STORED,
            )
            zf.writestr("META-INF/container.xml", self.container_xml())

            for filename, oebps_file in sorted(self.oebps_files.items()):
                zf.writestr(self.OEBPS_DIR + filename, oebps_file.binary_data)

        data = file.getvalue()
        file.close()

        return data

    def add_style(self, elem, style):
        elem.set("style", " ".join(["%s: %s;" % (p, v) for p, v in style.items()]))

    def mimetype_of_filename(self, filename, default="application/octet-stream"):
        ext = posixpath.splitext("x" + filename)[1].lower()
        return MIMETYPE_OF_EXT.get(ext, default)

    def fixup_ns_prefixes(self, tree):
        def fixup(name, elem):
            fixed = memo.get(name)
            if fixed is not None:
                return fixed

            if name.startswith("{"):
                if name.startswith(default_ns_prefix):
                    memo[name] = tag = name[len(default_ns_prefix) :]
                    return tag

            elif ":" in name:
                namespace, sep, localname = name.rpartition(":")
                uri = elem.nsmap.get(namespace) or tree.nsmap.get(namespace)
                if uri:
                    memo[name] = tag = qname(uri, localname)
                    return tag

                log.error(
                    "namespace of element %s is undefined in %s"
                    % (name, repr(elem.nsmap))
                )

            return None

        default_ns = tree.nsmap.get(None)

        if default_ns is None:
            default_ns = XHTML_NS_URI

        default_ns_prefix = "{" + default_ns + "}"
        memo = {}

        for elem in tree.getiterator():
            name = fixup(elem.tag, elem)
            if name:
                elem.tag = name

            for key, value in list(elem.items()):
                name = fixup(key, elem)
                if name:
                    elem.attrib.pop(key)
                    elem.set(name, value)

        tree.tag = qname(default_ns, tree.tag)


def add_meta_name_content(elem, name, content):
    add_attribs(etree.SubElement(elem, "meta"), "name", name, "content", content)


def add_attribs(elem, *args):
    for i in range(0, len(args), 2):
        elem.set(args[i], args[i + 1])

    return elem


def remove_url_fragment(filename):
    return filename.partition("#")[0]


def value_str(quantity, unit=""):
    if quantity is None:
        return unit

    if type(quantity) is float:
        q_str = "%g" % quantity
        if "e" in q_str:
            q_str = "%.4f" % quantity

    elif type(quantity) is decimal.Decimal and abs(quantity) < 1e-10:
        q_str = "0"
    else:
        q_str = str(quantity)

    if "." in q_str:
        q_str = q_str.rstrip("0").rstrip(".")

    if q_str == "0":
        return q_str

    return q_str + unit


def roman_to_int(input):
    input = input.upper()
    nums = ["M", "D", "C", "L", "X", "V", "I"]
    ints = [1000, 500, 100, 50, 10, 5, 1]
    places = []
    for c in input:
        if c not in nums:
            return 0

    for i in range(len(input)):
        c = input[i]
        value = ints[nums.index(c)]

        try:
            nextvalue = ints[nums.index(input[i + 1])]
            if nextvalue > value:
                value *= -1
        except IndexError:
            pass

        places.append(value)

    sum = 0
    for n in places:
        sum += n

    return sum


def nsprefix(s, namespaces=XHTML_NAMESPACES):
    prefix, sep, local = s.partition(":")
    ns = namespaces.get(prefix)
    if ns:
        return "{%s}%s" % (ns, local)

    return s


def set_nsmap(root, nsmap):
    if root.getparent() is not None:
        raise Exception("set_nsmap: root element has parent")

    new_nsmap = dict(root.nsmap)
    new_nsmap.update(nsmap)

    new_root = etree.Element(
        qname(new_nsmap.get(None), localname(root.tag)), nsmap=new_nsmap
    )
    new_root.text = root.text
    new_root.tail = root.tail

    for k, v in root.items():
        new_root.set(k, v)

    for child in root:
        root.remove(child)
        new_root.append(child)

    return new_root


def xhtmlns(name):
    return qname(XHTML_NS_URI, name)


def new_xhtml():
    return etree.Element(HTML, nsmap=XHTML_NAMESPACES)


def namespace(tag):
    if tag.startswith("{"):
        return tag[1:].partition("}")[0]

    return ""


def localname(tag):
    return tag.rpartition("}")[2]


def qname(ns, name):
    if name.startswith("{"):
        raise Exception("qname - name is already prefixed: %s" % name)

    return "".join(["{", ns, "}", name])


EPUB_PREFIX = qname(EPUB_NS_URI, "prefix")
EPUB_TYPE = qname(EPUB_NS_URI, "type")
HTML = xhtmlns("html")
IDX_ENTRY = qname(IDX_NS_URI, "entry")
IDX_ORTH = qname(IDX_NS_URI, "orth")
IDX_INFL = qname(IDX_NS_URI, "infl")
IDX_IFORM = qname(IDX_NS_URI, "iform")
MATH = qname(MATHML_NS_URI, "math")
SVG = qname(SVG_NS_URI, "svg")
XML_LANG = qname(XML_NS_URI, "lang")
