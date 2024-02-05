from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import io
import posixpath
import re
import traceback
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from lxml import etree
from PIL import Image

from .utilities import (
    UUID_RE,
    dirname,
    font_file_ext,
    get_url_filename,
    locale_decode,
    natural_sort_key,
    quote_name,
    root_path,
    unroot_path,
    urlabspath,
    urlrelpath,
)

try:
    import calibre.utils.soupparser as soupparser
except ImportError:
    import lxml.html.soupparser as soupparser

from .message_logging import log
from .python_transition import IS_PYTHON2, bytes_, bytes_indexed
from .utilities import sha1

if IS_PYTHON2:
    from .python_transition import repr, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEOBFUSCATE_FONTS = True
FIX_CHARACTER_ENCODING = True
FIX_NCX_ENTITIES = True
FIX_NCX_NAVMAP = True
FIX_NCX_PAGELIST = True
FIX_PAGE_MAP = True
FIX_NAV_TOC = True
FIX_NAV_PAGE_LIST = True
FIX_BODY_ID_REF = True
FIX_OPF_METADATA = True
FIX_OPF_GUIDE = True
FIX_ONLOAD_ATTRIB = True
FIX_DRIVE_LETTER_IN_IMG_SRC = True
FIX_GIF_CONTENT = True
COPY_PAGE_NUMBERS_TO_GUIDE = True
FIX_SPACES_IN_LINKS = True
FIX_AMZN_REMOVED_ATTRIBS = True
FIX_CALIBRE_CLASS_IN_BR = True
FIX_LANGUAGE_SUFFIX = True
FIX_WEBKIT_BOX_SHADOW = True
FIX_EPUB3_SWITCH = True
FIX_VERTICAL_CHINESE = True
FIX_DUPLICATE_OPF_IDS = True
FIX_LEFTOVER_CALIBRE_COVER = True


ENCODING_PATS = [
    r"""(<\?[^<>]+encoding\s*=\s*[\'"])(.*?)([\'"][^<>]*>)""",
    r"""(<meta\s+charset=['"])([-_a-z0-9]+)(['"][^<>]*>(?:\s*</meta>){0,1})""",
    r"""(<meta\s+?[^<>]*?content\s*=\s*['"][^'"]*?charset=)([-_a-z0-9]+)([^'"]*?['"][^<>]*>(?:\s*</meta>){0,1})""",
]

NON_XML_ENTITIES = [
    (b"&nbsp;", "\u00a0".encode("utf-8")),
    (b"&shy;", "\u00ad".encode("utf-8")),
    (b"&lsquo;", "\u2018".encode("utf-8")),
    (b"&rsquo;", "\u2019".encode("utf-8")),
    (b"&ndash;", "\u2013".encode("utf-8")),
    (b"&mdash;", "\u2014".encode("utf-8")),
    (b"&ldquo;", "\u201c".encode("utf-8")),
    (b"&rdquo;", "\u201d".encode("utf-8")),
    (b"&hellip;", "\u2026".encode("utf-8")),
]


DICTIONARY_NSMAP = {
    "mbp": "https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf",
    "idx": "https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf",
}


class EPUBZippedFile(object):
    def __init__(self, info, data):
        self.info = info
        self.data = data
        self.process_filename()
        self.mimetype = None
        self.is_nav = self.is_ncx = self.is_page_map = False
        self.reading_order = None
        self.body_id = None
        self.ids = []

    def rename(self, new_filename):
        self.info.filename = new_filename
        self.process_filename()

    def process_filename(self):
        self.filename = locale_decode(self.info.filename)
        self.is_file = not self.filename.endswith("/")
        self.name = posixpath.split(self.filename)[1]
        self.ext = (
            posixpath.splitext(self.filename)[1].lower()[1:] if self.is_file else "dir"
        )


class AdobeAlgorithm(object):
    name = "Adobe"
    ofs_data_len = 1024
    ofs_key_len = 16

    @staticmethod
    def key_of_ident(identifier):
        hex_key = identifier.lower().replace("urn:uuid:", "").replace("-", "")
        if not re.match("^[0-9a-f]{32}$", hex_key):
            return None

        return bytes_.fromhex(hex_key)


class IDPFAlgorithm(object):
    name = "IDPF"
    ofs_data_len = 1040
    ofs_key_len = 20

    @staticmethod
    def key_of_ident(identifier):
        return sha1(re.sub("[ \n\r\t]", "", identifier).encode("utf-8"))


MAX_OFS_DATA_LEN = max(AdobeAlgorithm.ofs_data_len, IDPFAlgorithm.ofs_data_len)
MAX_OFS_KEY_LEN = max(AdobeAlgorithm.ofs_key_len, IDPFAlgorithm.ofs_key_len)


class SourceEpub(object):
    def __init__(self, infile):
        self.infile = infile

        self.xml_parser = etree.XMLParser(encoding="utf-8", recover=True)
        self.html_parser = etree.HTMLParser(encoding="utf-8")

        self.data_files = unzip_book(infile)

        self.opf_file = self.find_opf()

        self.opf_identifiers = set()
        self.id_map = {}
        self.id_replace = {}
        self.spine_ids = set()
        self.is_dictionary = self.is_kim = self.is_vertical_rl = (
            self.is_fixed_layout
        ) = self.issue_date = False
        self.book_type = "book"
        self.authors = []
        self.content_languages = collections.defaultdict(lambda: 0)
        self.display_block_classes = set()

        if self.opf_file is not None:
            try:
                self.read_opf(self.opf_file)
            except Exception as e:
                traceback.print_exc()
                log.warning(
                    "Failed to read EPUB OPF %s: %s" % (self.opf_file.filename, repr(e))
                )

        if self.is_dictionary:
            self.full_book_type = "dictionary"
        elif self.is_kim:
            self.full_book_type = "Kindle in Motion"
        elif self.is_fixed_layout:
            self.full_book_type = "fixed-layout %s" % self.book_type
        else:
            self.full_book_type = "book"

    def prepare_for_previewer(self, outfile, conversion_application, sequence_name):
        log.info(
            "Preparing %s %s for conversion"
            % (self.full_book_type, quote_name(self.infile))
        )

        self.prevent_self_closed_divs = sequence_name == "EpubAdapter"

        self.fix_gif = self.copy_page_numbers = (
            conversion_application.TOOL_NAME == "KPR"
            and conversion_application.program_version_sort < natural_sort_key("3.23.0")
        )

        self.fix_webkit_box_shadow = (
            conversion_application.TOOL_NAME == "KPR"
            and conversion_application.program_version_sort
            >= natural_sort_key("3.31.0")
            and conversion_application.program_version_sort
            <= natural_sort_key("3.37.0")
        )

        self.pages = []
        for page_type in range(3):
            for f in self.data_files.values():
                try:
                    if page_type == 0 and f.is_nav:
                        self.get_nav_pages(f)

                    elif page_type == 1:
                        if f.is_ncx:
                            self.get_ncx_pages(f)
                        elif f.ext == "ncx" or f.mimetype == "application/x-dtbncx+xml":
                            log.warning("Ignoring unlinked EPUB NCX: %s" % f.filename)

                    elif page_type == 2:
                        if f.is_page_map:
                            self.get_page_map_pages(f)
                        elif (
                            f.name == "page-map.xml"
                            or f.mimetype == "application/oebps-page-map+xml"
                        ):
                            log.warning(
                                "Ignoring unlinked EPUB page-map: %s" % f.filename
                            )

                except Exception as e:
                    traceback.print_exc()
                    log.warning("Failed to process EPUB %s: %s" % (f.filename, repr(e)))

            if self.pages:
                break

        for f in self.data_files.values():
            if (
                f.ext in ["htm", "html", "xhtml"]
                or f.mimetype == "application/xhtml+xml"
            ):
                try:
                    self.prepare_xhtml_pt1(f)
                except Exception as e:
                    traceback.print_exc()
                    log.warning(
                        "Failed to read EPUB content %s: %s" % (f.filename, repr(e))
                    )

            if f.ext == "css" or f.mimetype == "text/css":
                try:
                    self.prepare_css(f)
                except Exception as e:
                    traceback.print_exc()
                    log.warning(
                        "Failed to prepare EPUB CSS %s: %s" % (f.filename, repr(e))
                    )

        for f in self.data_files.values():
            if self.opf_identifiers and f.ext in ["otf", "ttf", "woff", "eot", "dfont"]:
                try:
                    self.deobfuscate_font(f)
                except Exception as e:
                    traceback.print_exc()
                    log.warning(
                        "Failed to de-obfuscate EPUB font %s: %s"
                        % (f.filename, repr(e))
                    )

            if (
                f.ext in ["htm", "html", "xhtml"]
                or f.mimetype == "application/xhtml+xml"
            ):
                try:
                    self.prepare_xhtml_pt2(f)
                except Exception as e:
                    traceback.print_exc()
                    log.warning(
                        "Failed to prepare EPUB content %s: %s" % (f.filename, repr(e))
                    )

            if self.fix_gif and (f.ext == "gif" or f.mimetype == "image/gif"):
                try:
                    self.prepare_gif(f)
                except Exception as e:
                    traceback.print_exc()
                    log.warning(
                        "Failed to prepare EPUB GIF %s: %s" % (f.filename, repr(e))
                    )

        self.clean_pages()

        if self.opf_file is not None:
            try:
                self.prepare_opf(self.opf_file)
            except Exception as e:
                traceback.print_exc()
                log.warning("Failed to process EPUB OPF %s: %s" % (f.filename, repr(e)))

        for f in self.data_files.values():
            try:
                if f.is_nav:
                    self.prepare_nav(f)
                elif f.is_ncx:
                    self.prepare_ncx(f)
                elif f.is_page_map:
                    self.prepare_page_map(f)

            except Exception as e:
                traceback.print_exc()
                log.warning("Failed to prepare EPUB %s: %s" % (f.filename, repr(e)))

        for fn in ["META-INF/encryption.xml", "META-INF/rights.xml"]:
            self.data_files.pop(fn, None)

        zip_book(self.data_files, outfile)

    def find_opf(self):
        CONTAINER_FILENAME = "META-INF/container.xml"
        if CONTAINER_FILENAME in self.data_files:
            container = etree.fromstring(
                self.data_files[CONTAINER_FILENAME].data, parser=self.xml_parser
            )
            rootfiles = container.find("{*}rootfiles")
            if rootfiles is not None:
                for rootfile in rootfiles.iterfind(".//{*}rootfile"):
                    if rootfile.get("media-type") == "application/oebps-package+xml":
                        full_path = rootfile.get("full-path")
                        if full_path in self.data_files:
                            return self.data_files[full_path]
        else:
            for f in self.data_files.values():
                if f.ext == "opf":
                    log.warning("Located EPUB OPF using fallback")

                    if CONTAINER_FILENAME not in self.data_files:
                        xml_str = (
                            "<?xml version='1.0' encoding='utf-8' standalone='yes'?>\n"
                            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                            '<rootfiles><rootfile full-path="%s" media-type="application/oebps-package+xml" />'
                            "</rootfiles></container>"
                        ) % f.filename
                        self.data_files[CONTAINER_FILENAME] = EPUBZippedFile(
                            ZipInfo(CONTAINER_FILENAME), xml_str.encode("utf-8")
                        )

                    return f

        log.warning("Failed to locate EPUB OPF")
        return None

    def get_ncx_pages(self, f):
        ncx = etree.fromstring(f.data, parser=self.xml_parser)
        page_list = ncx.find("{*}pageList")

        if page_list is not None:
            log.info("Found EPUB NCX pageList")
            base_dir = dirname(root_path(f.filename))

            for page_target in page_list.iterfind("{*}pageTarget"):
                nav_label = page_target.find("{*}navLabel")
                content = page_target.find("{*}content")
                if (nav_label is not None) and (content is not None):
                    label_text = nav_label.find("{*}text")
                    if label_text is not None:
                        self.pages.append(
                            (
                                label_text.text or page_target.get("value"),
                                urlabspath(content.get("src"), working_dir=base_dir),
                            )
                        )

    def get_page_map_pages(self, f):
        log.info("Found EPUB page-map")

        base_dir = dirname(root_path(f.filename))
        page_map = etree.fromstring(f.data, parser=self.xml_parser)

        for page in page_map.iterfind("{*}page"):
            self.pages.append(
                (page.get("name"), urlabspath(page.get("href"), working_dir=base_dir))
            )

    def get_nav_pages(self, f):
        base_dir = dirname(root_path(f.filename))
        document = self.parse_xhtml_file(f)
        body = tfind(document, "body")

        for nav in body.iterfind(".//{*}nav"):
            if get_epub_type(nav) == "page-list":
                log.info("Found EPUB nav page-list")
                for li in nav.iterfind(".//{*}li"):
                    anchor = li.find("{*}a")
                    if (anchor is not None) and anchor.text:
                        self.pages.append(
                            (
                                anchor.text,
                                urlabspath(anchor.get("href"), working_dir=base_dir),
                            )
                        )

    def read_opf(self, f):
        base_dir = dirname(root_path(f.filename))
        document = etree.fromstring(f.data, parser=self.xml_parser)
        package = tfindc(document, "package")

        manifest = package.find("{*}manifest")
        if manifest is not None:
            all_unique_ids = set()
            case_unique_ids = set()
            for item in manifest.iterfind("{*}item"):
                id = item.get("id")

                if FIX_DUPLICATE_OPF_IDS:
                    if id not in all_unique_ids:
                        all_unique_ids.add(id)
                        id_lower = id.lower()
                        if id_lower in case_unique_ids:
                            new_id = id
                            while new_id.lower() in case_unique_ids:
                                new_id += "_"
                            self.id_replace[id] = new_id
                            case_unique_ids.add(new_id.lower())
                        else:
                            case_unique_ids.add(id_lower)

                mimetype = item.get("media-type")
                href = item.get("href")
                if href:
                    fn = get_url_filename(urlabspath(href, working_dir=base_dir))
                    if fn:
                        target_file = unroot_path(fn)
                        if target_file in self.data_files:
                            if id and href:
                                self.id_map[id] = target_file

                            self.data_files[target_file].mimetype = mimetype

                            if "nav" in item.get("properties", "").split():
                                self.data_files[target_file].is_nav = True

            spine = package.find("{*}spine")
            if spine is not None:
                ncx_file = self.data_files.get(self.id_map.get(spine.get("toc")))
                if ncx_file is not None:
                    ncx_file.is_ncx = True

                page_map_file = self.data_files.get(
                    self.id_map.get(spine.get("page-map"))
                )
                if page_map_file is not None:
                    page_map_file.is_page_map = True

                for i, itemref in enumerate(spine.iterfind("{*}itemref")):
                    idref = itemref.get("idref")
                    self.spine_ids.add(idref)

                    if idref in self.id_map:
                        self.data_files[self.id_map[idref]].reading_order = i

        unique_id = package.get("unique-identifier", None)
        metadata = package.find("{*}metadata")
        if metadata is not None:
            for ident in metadata.iterfind("{*}identifier"):
                if ident.text and (
                    ident.get("id", None) == unique_id
                    or re.match(
                        r"^(urn:uuid:)?%s$" % UUID_RE, ident.text, flags=re.IGNORECASE
                    )
                ):
                    self.opf_identifiers.add(ident.text)

            display_seq = 1
            known_authors = set()
            sequenced_authors = []
            for creator in metadata.iterfind(".//{*}creator"):
                if creator.text and creator.text not in known_authors:
                    creator_id = creator.get("id")
                    if creator_id:
                        creator_fragment = "#" + creator_id
                        for meta in metadata.iterfind(".//{*}meta"):
                            if (
                                meta.get("property", "") == "display-seq"
                                and meta.get("refines", "") == creator_fragment
                                and meta.text
                            ):
                                if re.match("^[0-9]+$", meta.text):
                                    display_seq = int(meta.text)
                                else:
                                    log.warning(
                                        "Unexpected display-seq %s for creator %s"
                                        % (meta.text, creator.text)
                                    )
                                break

                    known_authors.add(creator.text)
                    sequenced_authors.append((display_seq, creator.text))
                    display_seq += 1

            self.authors = [author for display_seq, author in sorted(sequenced_authors)]

            dc_date = metadata.find(".//{*}date")
            if dc_date is not None and dc_date.text is not None:
                m = re.match("[0-9]{4}-[0-9]{2}-[0-9]{2}", dc_date.text)
                if m is not None and m.group(0) != "0101-01-01":
                    self.issue_date = m.group(0)

            self.is_dictionary = metadata.find(".//{*}DictionaryInLanguage") is not None

            for meta in metadata.iterfind(".//{*}meta"):
                meta_name = meta.get("name", "")
                meta_content = meta.get("content", "")

                if meta_name == "amzn:kindle-illustrated" and meta_content == "true":
                    self.is_kim = True

                if meta_name == "book-type" and meta_content != "none":
                    self.book_type = meta_content

                if (meta_name == "fixed-layout" and meta_content == "true") or (
                    meta.get("property", "") == "rendition:layout"
                    and meta.text == "pre-paginated"
                ):
                    self.is_fixed_layout = True

                if (
                    meta_name == "primary-writing-mode"
                    and meta_content == "vertical-rl"
                ):
                    self.is_vertical_rl = True

    def prepare_opf(self, f):
        base_dir = dirname(root_path(f.filename))
        document = etree.fromstring(f.data, parser=self.xml_parser)
        package = tfindc(document, "package")
        fixed = False

        if FIX_LEFTOVER_CALIBRE_COVER:
            manifest = package.find("{*}manifest")
            if manifest is not None:
                for item in manifest.findall("{*}item"):
                    id = item.get("id")
                    href = item.get("href", "")
                    mimetype = item.get("media-type")
                    if (
                        id
                        and id not in self.spine_ids
                        and (
                            href.endswith(".htm")
                            or href.endswith(".html")
                            or href.endswith(".xhtml")
                            or mimetype == "application/xhtml+xml"
                        )
                    ):
                        manifest_file = self.data_files.get(self.id_map.get(id))
                        is_possible_cover_file = (
                            manifest_file
                            and len(manifest_file.data) < 2000
                            and len(re.findall(b"<img ", manifest_file.data))
                            + len(re.findall(b"<svg ", manifest_file.data))
                            == 1
                        )

                        if (
                            is_possible_cover_file
                            or "cover" in id.lower()
                            or "cover" in href.lower()
                        ):
                            log.info("Removing extra leftover cover %s" % href)
                            item.getparent().remove(item)
                            self.id_map.pop(id, None)
                            fixed = True

        if FIX_OPF_METADATA:
            metadata = package.find("{*}metadata")
            if (metadata is not None) and (metadata.find("{*}dc-metadata") is None):
                for meta in metadata.findall("{*}meta"):
                    if meta.get("name", "") == "cover":
                        cover_file = self.id_map.get(meta.get("content", None), None)
                        if (
                            cover_file
                            and cover_file in self.data_files
                            and not self.data_files[cover_file].mimetype.startswith(
                                "image/"
                            )
                        ):
                            log.info(
                                "Removing meta cover '%s' of incorrect type '%s'"
                                % (cover_file, self.data_files[cover_file].mimetype)
                            )
                            meta.getparent().remove(meta)
                            fixed = True

                languages = []
                fix_language_order = False

                for lang in metadata.findall("{*}language"):
                    if lang.text.lower().partition(" ")[0].partition("-")[0] in [
                        "pl",
                        "und",
                        "us",
                    ]:
                        log.info("Changed EPUB language from '%s' to 'en'" % lang.text)
                        lang.text = "en"
                        fixed = True

                    if FIX_LANGUAGE_SUFFIX and "-" not in lang.text:
                        current_language_pattern = re.compile(
                            re.escape(lang.text) + "(-.+)?$", re.IGNORECASE
                        )
                        best_language_variant, best_language_count = lang.text, 0

                        for language, count in self.content_languages.items():
                            if count > best_language_count and re.match(
                                current_language_pattern, language
                            ):
                                best_language_variant, best_language_count = (
                                    language,
                                    count,
                                )

                        if best_language_variant != lang.text:
                            log.info(
                                "Changed EPUB language from '%s' to '%s'"
                                % (lang.text, best_language_variant)
                            )
                            lang.text = best_language_variant
                            fixed = True

                    if (
                        FIX_VERTICAL_CHINESE
                        and lang.text.lower().startswith("zh")
                        and self.is_vertical_rl
                    ):
                        log.info(
                            "Changed EPUB language to allow vertical text conversion"
                        )
                        lang.text = "ja-%s" % (lang.text.replace("-", "="))
                        fixed = True

                    if (
                        languages
                        and (not languages[0].lower().startswith("en"))
                        and lang.text.lower().startswith("en")
                    ):
                        languages.insert(0, lang.text)
                        fix_language_order = True
                    else:
                        languages.append(lang.text)

                if fix_language_order:
                    log.info("Changed EPUB language order to 'en' first")

                    for lang in metadata.findall("{*}language"):
                        lang.text = languages.pop(0)

                    fixed = True

                title_count = 0
                for title in metadata.findall(
                    "{http://purl.org/dc/elements/1.1/}title"
                ):
                    title_count += 1
                    if title_count > 1:
                        log.info("Removed extra EPUB title '%s'" % title.text)
                        title.getparent().remove(title)
                        fixed = True
                    elif not title.text:
                        log.info(
                            "Changed EPUB title from '%s' to 'Unknown'" % title.text
                        )
                        title.text = "Unknown"
                        fixed = True

                if title_count == 0:
                    title = metadata.find("{*}title")
                    if title is not None and title.text:
                        title_text = title.text
                    else:
                        title_text = "Unknown"

                    log.info("Added EPUB title '%s'" % title_text)
                    title = etree.SubElement(
                        metadata, "{http://purl.org/dc/elements/1.1/}title"
                    )
                    title.text = title_text
                    fixed = True

        guide = package.find("{*}guide")
        if FIX_OPF_GUIDE and guide is not None:
            for ref in guide.findall("{*}reference"):
                fixed = self.fix_href(ref, "OPF guide", base_dir) or fixed

        if COPY_PAGE_NUMBERS_TO_GUIDE and self.copy_page_numbers and self.pages:
            if guide is None:
                guide = etree.SubElement(package, "{http://www.idpf.org/2007/opf}guide")

            added = 0
            for sort_key, name, href in self.pages:
                ref = etree.SubElement(guide, "{http://www.idpf.org/2007/opf}reference")
                ref.set("type", "page_list_entry_%d" % added)
                ref.set("title", "page_list_entry:%d:%s" % (added, name))
                ref.set("href", urlrelpath(href, working_dir=base_dir))
                self.fix_href(ref, "OPF guide", base_dir)
                ref.tail = "\n"
                added += 1

            if added:
                log.info("Adding %d page list entries to OPF guide" % added)
                fixed = True

        if FIX_DUPLICATE_OPF_IDS and self.id_replace:

            def replace(elem, attrib, name, fixed):
                orig_id = elem.get(attrib)
                if orig_id is not None:
                    new_id = self.id_replace.get(orig_id)
                    if new_id is not None:
                        log.info(
                            "Replacing OPF %s id %s with %s" % (name, orig_id, new_id)
                        )
                        elem.set(attrib, new_id)
                        return True

                return fixed

            manifest = package.find("{*}manifest")
            if manifest is not None:
                for item in manifest.iterfind("{*}item"):
                    fixed = replace(item, "id", "manifest", fixed)

            spine = package.find("{*}spine")
            if spine is not None:
                fixed = replace(spine, "toc", "toc", fixed)
                fixed = replace(spine, "page-map", "page-map", fixed)

                for i, itemref in enumerate(spine.iterfind("{*}itemref")):
                    fixed = replace(itemref, "idref", "spine", fixed)

            metadata = package.find("{*}metadata")
            if (metadata is not None) and (metadata.find("{*}dc-metadata") is None):
                for meta in metadata.findall("{*}meta"):
                    if meta.get("name", "") == "cover":
                        fixed = replace(meta, "content", "cover", fixed)

        if fixed:
            f.data = etree.tostring(
                document, encoding="utf-8", pretty_print=True, xml_declaration=True
            )

    def prepare_ncx(self, f):
        base_dir = dirname(root_path(f.filename))

        if FIX_NCX_ENTITIES:
            for before, after in NON_XML_ENTITIES:
                f.data = f.data.replace(before, after)

        fixed = False
        ncx = etree.fromstring(f.data, parser=self.xml_parser)

        if FIX_NCX_NAVMAP:
            nav_map = ncx.find("{*}navMap")
            if nav_map is not None:
                for nav_point in nav_map.findall(".//{*}navPoint"):
                    label = None
                    nav_label = nav_point.find("{*}navLabel")
                    if nav_label is not None:
                        label_text = nav_label.find("{*}text")
                        if label_text is not None:
                            label = label_text.text

                    content = nav_point.find("{*}content")
                    if content is not None:
                        orig_src = content.get("src")
                        src = urlabspath(orig_src, working_dir=base_dir)
                        tf, tid, sort_key = self.ref_file_id_and_key(src)

                        if sort_key is None:
                            log.info(
                                "Removed NCX TOC reference to non-existent target: %s"
                                % orig_src
                            )
                            self.delete_navpoint(nav_point)
                            fixed = True

                        elif tid and (label == "Midpoint"):
                            log.info(
                                "Removed NCX TOC reference to 'Midpoint': %s" % orig_src
                            )
                            self.delete_navpoint(nav_point)
                            fixed = True

                        elif FIX_BODY_ID_REF and tid and (tf.body_id == tid):
                            fixed_src = orig_src.rpartition("#")[0]
                            log.info(
                                "Adjusted NCX TOC reference to body element id: %s --> %s"
                                % (orig_src, fixed_src)
                            )
                            content.set("src", fixed_src)
                            fixed = True

                        fixed = self.fix_src(content, "NCX TOC") or fixed

        if FIX_NCX_PAGELIST:
            page_list = ncx.find("{*}pageList")
            if page_list is not None:
                page_urls = set()
                page_labels = set()
                for page_target in page_list.findall("{*}pageTarget"):
                    content = page_target.find("{*}content")
                    if content is not None:
                        fixed = self.fix_src(content, "NCX pageList") or fixed
                        src = content.get("src")

                        if src in page_urls:
                            log.info("Removing duplicate NCX pageTarget: %s" % src)
                            page_list.remove(page_target)
                            fixed = True
                        else:
                            page_urls.add(src)

                            nav_label = page_target.find("{*}navLabel")
                            navlabel_text = (
                                nav_label.find("{*}text")
                                if nav_label is not None
                                else None
                            )
                            label = (
                                navlabel_text.text if navlabel_text is not None else ""
                            ) or ""

                            if not is_page_label(label):
                                log.info(
                                    'Removing NCX pageTarget with incorrect or missing label: "%s"'
                                    % label
                                )
                                page_list.remove(page_target)
                                fixed = True

                            elif label in page_labels:
                                log.info(
                                    'Removing NCX pageTarget with duplicate label: "%s"'
                                    % label
                                )
                                page_list.remove(page_target)
                                fixed = True
                            else:
                                page_labels.add(label)

        if fixed:
            f.data = etree.tostring(
                ncx, encoding="utf-8", pretty_print=True, xml_declaration=True
            )

    def prepare_nav(self, f):
        base_dir = dirname(root_path(f.filename))
        fixed = False
        document = self.parse_xhtml_file(f)
        body = tfind(document, "body")

        if COPY_PAGE_NUMBERS_TO_GUIDE and self.copy_page_numbers and self.pages:
            for nav in body.findall(".//{*}nav"):
                if get_epub_type(nav) == "landmarks":
                    parent = nav.getparent()
                    parent.remove(nav)
                    log.info("Removed NAV landmarks")
                    fixed = True

        if FIX_NAV_TOC:
            for nav in body.findall(".//{*}nav"):
                if get_epub_type(nav) == "toc":
                    for li in nav.findall(".//{*}li"):
                        a = li.find(".//{*}a")
                        if a is not None:
                            orig_href = a.get("href")
                            sort_key = self.ref_file_id_and_key(
                                urlabspath(orig_href, working_dir=base_dir)
                            )[2]
                            if sort_key is None:
                                log.info(
                                    "Removed NAV TOC reference to non-existent target: %s"
                                    % orig_href
                                )
                                li.getparent().remove(li)
                                fixed = True

        if FIX_NAV_PAGE_LIST:
            page_urls = set()
            page_labels = set()

            for nav in body.findall(".//{*}nav"):
                if get_epub_type(nav) == "page-list":
                    for li in nav.findall(".//{*}li"):
                        a = li.find(".//{*}a")
                        if a is not None:
                            href = a.get("href")
                            if href in page_urls:
                                log.info("Removing duplicate NAV page href: %s" % href)
                                li.getparent().remove(li)
                                fixed = True
                            else:
                                page_urls.add(href)

                                if len(a) == 0:
                                    label = a.text or ""
                                    if not is_page_label(label):
                                        log.info(
                                            'Removing NAV page with missing or incorrect label: "%s"'
                                            % label
                                        )
                                        li.getparent().remove(li)
                                        fixed = True
                                    elif label in page_labels:
                                        log.info(
                                            'Removing NAV page with with duplicate label: "%s"'
                                            % label
                                        )
                                        li.getparent().remove(li)
                                        fixed = True
                                    else:
                                        page_labels.add(label)

        if fixed:
            f.data = etree.tostring(
                document, encoding="utf-8", pretty_print=False, xml_declaration=True
            )

    def prepare_page_map(self, f):
        if not FIX_PAGE_MAP:
            return

        fixed = False
        base_dir = dirname(root_path(f.filename))
        page_map = etree.fromstring(f.data, parser=self.xml_parser)
        page_urls = set()

        for page in page_map.findall("{*}page"):
            fixed = self.fix_href(page, "page-map", base_dir) or fixed
            href = page.get("href")
            if href in page_urls:
                log.info("Removing page-map entry with duplicate target: %s" % href)
                page_map.remove(page)
                fixed = True
            else:
                page_urls.add(href)

                name = page.get("name", "")
                if not is_page_label(name):
                    log.info(
                        'Removing page-map entry with missing or incorrect name: "%s"'
                        % name
                    )
                    page_map.remove(page)
                    fixed = True

        if fixed:
            f.data = etree.tostring(
                page_map, encoding="utf-8", pretty_print=True, xml_declaration=True
            )

    def clean_pages(self):
        used_names = set()
        used_hrefs = set()

        good_pages = []
        for name, href in self.pages:
            if name and href:
                sort_key = self.ref_key(href)
                if (
                    (sort_key is not None)
                    and (name not in used_names)
                    and (href not in used_hrefs)
                ):
                    used_hrefs.add(href)
                    used_names.add(name)
                    good_pages.append((sort_key, name, href))

        self.pages = sorted(good_pages)

    def delete_navpoint(self, nav_point):
        parent = nav_point.getparent()
        for sub_nav_point in nav_point.findall("{*}navPoint"):
            nav_point.remove(sub_nav_point)
            parent.insert(parent.index(nav_point), sub_nav_point)

        parent.remove(nav_point)

    def page_nav_point(self, name, href, added, before=True):
        nav_point = etree.Element("navPoint")
        nav_point.set("id", "page_list_entry_%d" % added)
        nav_point.tail = "\n"

        nav_label = etree.SubElement(nav_point, "navLabel")
        label_text = etree.SubElement(nav_label, "text")
        label_text.text = "page_list_entry:%d:%s" % (added, name)

        content = etree.SubElement(nav_point, "content")
        content.set("src", href)

        return nav_point

    def ref_key(self, ref):
        return self.ref_file_id_and_key(ref)[2]

    def ref_file_id_and_key(self, ref):
        url_filename = get_url_filename(ref)
        if not url_filename:
            return (None, None, None)

        target_file = unroot_path(url_filename)
        if target_file not in self.data_files:
            return (None, None, None)

        f = self.data_files[target_file]
        id = urllib.parse.urlparse(ref).fragment

        if (id is None) or (f.reading_order is None):
            return (f, id, None)

        if not id:
            return (f, id, (f.reading_order, 0))

        if id not in f.ids:
            return (f, id, None)

        return (f, id, (f.reading_order, f.ids.index(id) + 1))

    def deobfuscate_font(self, f):
        if font_file_ext(f.data):
            return

        if not DEOBFUSCATE_FONTS:
            return

        for identifier in self.opf_identifiers:
            for algorithm in [AdobeAlgorithm, IDPFAlgorithm]:
                if self.deobfuscate(f, algorithm, identifier=identifier):
                    return

        log.info("Failed to de-obfuscate EPUB font %s" % f.filename)

    def deobfuscate(self, f, algorithm, font_key=None, identifier=None):
        if font_key is None:
            font_key = algorithm.key_of_ident(identifier)

        if font_key is None:
            return False

        new_data = (
            xor_data(font_key, algorithm.ofs_data_len, f.data)
            + f.data[algorithm.ofs_data_len :]
        )

        if not font_file_ext(new_data):
            return False

        f.data = new_data
        log.info("De-obfuscated EPUB %s font %s" % (font_file_ext(f.data), f.filename))
        return True

    def prepare_xhtml_pt1(self, f):
        if FIX_CHARACTER_ENCODING:
            new_data = f.data

            if new_data.startswith(b"\xef\xbb\xbf"):
                new_data = new_data[3:]
                log.info("Removed UTF-8 BOM from %s" % f.name)

            header = new_data[:1024].decode("utf-8", "ignore")

            for pat in ENCODING_PATS:
                m = re.search(pat, header, re.IGNORECASE)
                if m:
                    enc = m.group(2).lower()
                    if enc == "utf8":
                        enc = "utf-8"

                    break
            else:
                log.info("Assuming UTF-8 encoding for %s" % f.name)
                enc = "utf-8"

            try:
                new_text = new_data.decode("utf-8")
            except UnicodeDecodeError:
                if enc == "utf-8":
                    log.warning("Content failed to decode as UTF-8 in %s" % f.name)
                else:
                    log.info(
                        "Changed encoding from %s to UTF-8 in %s"
                        % (enc.upper(), f.name)
                    )

                new_text = new_data.decode(enc, errors="replace")

            if enc != "utf-8":
                for pat in ENCODING_PATS:
                    new_text, i = re.subn(pat, r"\1utf-8\3", new_text, re.IGNORECASE)
                    if i:
                        log.info(
                            "Changed encoding declaration from %s to UTF-8 in %s"
                            % (enc.upper(), f.name)
                        )

            if (
                f.ext == "xhtml" or f.mimetype == "application/xhtml+xml"
            ) and not new_text.strip().startswith("<?xml"):
                new_text = "<?xml version='1.0' encoding='utf-8'?>" + new_text
                log.info("Added XML declaration to %s" % f.name)

            new_text = re.sub(r"<\?xml([^\?]*?)\?><", r"<?xml\1?>\n<", new_text)
            f.data = new_text.encode("utf-8")

        try:
            document = self.parse_xhtml_file(f)
        except Exception:
            return

        body = tfind(document, "body")
        if body is not None:
            f.body_id = body.get("id")

        if self.is_dictionary:
            html = tfind(document, "html")
            for ns, url in DICTIONARY_NSMAP.items():
                if ns not in html.nsmap and ("<%s:" % ns).encode("utf8") in f.data:
                    f.data = f.data.replace(
                        b"<html", ('<html xmlns:%s="%s"' % (ns, url)).encode("utf8"), 1
                    )
                    log.info("Added %s XML namespace to %s" % (ns, f.name))

            if not f.data.startswith(b"<?xml"):
                log.info("Parsing %s as HTML soup" % f.name)
                document = soupparser.fromstring(f.data)
                f.data = etree.tostring(
                    document,
                    encoding="utf-8",
                    pretty_print=False,
                    xml_declaration=False,
                )

    def prepare_xhtml_pt2(self, f):
        base_dir = dirname(root_path(f.filename))

        fixed = False
        br_fix_count = 0
        document = self.parse_xhtml_file(f)

        body = tfind(document, "body")
        if body is not None and FIX_ONLOAD_ATTRIB and "onload" in body.attrib:
            body.attrib.pop("onload")
            log.info("Removed onload attribute from body of %s" % f.filename)
            fixed = True

        for elem in document.iter("*"):
            tag = localname(elem.tag)
            id = elem.get("id")

            if id:
                f.ids.append(id)

            if tag == "a":
                id = elem.get("name")
                if id:
                    f.ids.append(id)

                fixed = (
                    self.fix_href(elem, "HTML", base_dir, fix_spaces=f.is_nav) or fixed
                )

            if (
                FIX_CALIBRE_CLASS_IN_BR
                and tag == "br"
                and set(elem.get("class", "").split()) & self.display_block_classes
            ):
                orig_style = elem.get("style", "")
                elem.set(
                    "style",
                    orig_style + ("; " if orig_style else "") + "display: inline",
                )
                br_fix_count += 1
                fixed = True

            if FIX_DRIVE_LETTER_IN_IMG_SRC and tag == "img":
                src = elem.get("src")
                if src and re.match(r"^[a-zA-Z]:", src):
                    elem.set("src", src[2:])
                    log.info(
                        "Removed '%s' from image reference in %s"
                        % (src[0:2], f.filename)
                    )
                    fixed = True

            if FIX_AMZN_REMOVED_ATTRIBS:
                for removed_attrib in ["data-AmznRemoved", "data-AmznRemoved-M8"]:
                    if removed_attrib in elem.attrib:
                        elem.attrib.pop(removed_attrib, None)
                        log.info(
                            "Removed '%s' attribute from '%s' in %s"
                            % (removed_attrib, elem.tag, f.filename)
                        )
                        fixed = True

            if FIX_LANGUAGE_SUFFIX and tag in ["html", "body"]:
                for k, v in elem.attrib.items():
                    if re.match("({.+})?lang$", k):
                        self.content_languages[v] += 1

            if tag == "style" and elem.text:
                self.inventory_css_styles(elem.text)
                style_text = self.fix_styles(elem.text, f.filename)
                if style_text is not None:
                    elem.text = style_text
                    fixed = True

            if "style" in elem.attrib:
                style_text = self.fix_styles(elem.get("style"), f.filename)
                if style_text is not None:
                    elem.set("style", style_text)
                    fixed = True

            if FIX_EPUB3_SWITCH and tag == "switch":
                log.info("Removed EPUB 3 switch in %s" % f.filename)
                elem.tag = "div"
                if len(elem) > 0:
                    elem[0].tag = "div"
                while len(elem) > 1:
                    elem.remove(elem[1])
                fixed = True

        if br_fix_count:
            log.info("Added display:inline to %d br in %s" % (br_fix_count, f.filename))

        if fixed:
            is_xml = (
                f.ext == "xhtml"
                or f.mimetype == "application/xhtml+xml"
                or f.data[:32].startswith(b"<?xml")
            )
            f.data = etree.tostring(
                document, encoding="utf-8", pretty_print=False, xml_declaration=is_xml
            )

    def prepare_css(self, f):
        self.inventory_css_styles(f.data)
        data = self.fix_styles(f.data, f.filename)
        if data is not None:
            f.data = data

    def inventory_css_styles(self, data):
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        for class_name in re.findall(
            "[.]([A-Za-z0-9_-]*)\\s*{[^}]*display\\s*:\\s*block\\s*[;}]", data
        ):
            self.display_block_classes.add(class_name)

    def fix_styles(self, data, filename):
        if FIX_WEBKIT_BOX_SHADOW and self.fix_webkit_box_shadow:

            def enc(s):
                return s.encode("ascii") if isinstance(data, bytes) else s

            data, num_subs = re.subn(
                enc("-webkit-box-shadow\\s?:"), enc("box-shadow:"), data
            )

            if num_subs:
                log.info(
                    "Replaced -webkit-box-shadow with box-shadow in %s" % (filename)
                )
                return data

        return None

    def fix_href(self, elem, ftype, base_dir, fix_spaces=True):
        fixed = False
        href = elem.get("href")
        if href:
            src = urlabspath(href, working_dir=base_dir)

            tf, tid, sort_key = self.ref_file_id_and_key(src)
            if FIX_BODY_ID_REF and tf and tid and (tf.body_id == tid):
                fixed_href = href.rpartition("#")[0]
                log.info(
                    "Adjusted %s reference to body element id: %s --> %s"
                    % (ftype, href, fixed_href)
                )
                elem.set("href", fixed_href)
                fixed = True

            if FIX_SPACES_IN_LINKS and fix_spaces:
                orig_src = elem.get("href")
                if "%" in orig_src:
                    fixed_src = urllib.parse.unquote(orig_src)
                    if fixed_src != orig_src:
                        log.info("Unquoted %s reference: %s" % (ftype, orig_src))
                        elem.set("href", fixed_src)
                        fixed = True

        return fixed

    def fix_src(self, elem, ftype):
        if FIX_SPACES_IN_LINKS:
            orig_src = elem.get("src")
            if "%" in orig_src:
                fixed_src = urllib.parse.unquote(orig_src)
                if fixed_src != orig_src:
                    log.info("Unquoted %s reference: %s" % (ftype, orig_src))
                    elem.set("src", fixed_src)
                    return True

        return False

    def prepare_gif(self, f):
        if not FIX_GIF_CONTENT:
            return

        im = Image.open(io.BytesIO(f.data))

        if im.mode == "P" and "transparency" in im.info:
            log.info("Removing transparency from GIF: %s" % f.filename)

            palette = im.getpalette()
            trans = im.info["transparency"] * 3
            palette[trans : trans + 3] = [255, 255, 255]
            im.putpalette(palette)

            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, (0, 0))
            outfile = io.BytesIO()
            bg.save(outfile, "gif")
            f.data = outfile.getvalue()

    def parse_xhtml_file(self, f):
        if (
            f.ext == "xhtml"
            or f.mimetype == "application/xhtml+xml"
            or b"xml" in f.data[:32]
        ):
            tree = etree.fromstring(f.data, parser=self.xml_parser)
        else:
            tree = None

        if tree is None:
            log.info("Parsing %s as HTML" % f.name)
            tree = etree.fromstring(f.data, parser=self.html_parser)

        if tree is None:
            raise Exception("failed to parse %s" % f.name)

        return tree


def is_page_label(s):
    if not s:
        return False

    return re.match("^[0-9\u0660-\u0669\u06f0-\u06f9]+$", s) or re.match(
        "^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", s, re.IGNORECASE
    )


def xor_data(font_key, ofs_data_len, data):
    de = []
    for i in range(min(ofs_data_len, len(data))):
        j = i % len(font_key)
        de.append(bytes_indexed(data, i) ^ bytes_indexed(font_key, j))

    return bytes_(de)


def not_visible(s):
    return (not s) or not (s.replace(" ", "").replace("\u00a0", ""))


def localname(tag):
    return tag.rpartition("}")[2]


def tfind(tree, tag):
    if localname(tree.tag) == tag:
        return tree

    return tree.find(".//{*}" + tag)


def tfindc(tree, tag):
    if localname(tree.tag) == tag:
        return tree

    return tree.find("{*}" + tag)


def get_epub_type(elem):
    for name in elem.attrib.keys():
        if name == "epub:type" or name.endswith("}type"):
            return elem.get(name)

    return None


def unzip_book(infile):
    data_files = collections.OrderedDict()

    with ZipFile(infile, "r") as zf:
        for info in zf.infolist():
            data_files[info.filename] = EPUBZippedFile(info, zf.read(info.filename))

    return data_files


def zip_book(data_files, outfile):
    with ZipFile(outfile, "w", compression=ZIP_DEFLATED) as zf:
        for datafile in data_files.values():
            if datafile.info.filename == "mimetype":
                datafile.info.extra = b""
                zf.writestr(datafile.info, datafile.data, compress_type=ZIP_STORED)
            elif datafile.data is not None:
                zf.writestr(datafile.info, datafile.data)
