from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import copy
import decimal
import re

from .epub_output import EPUB_Output
from .ion import (
    IonAnnotation,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    ion_type,
)
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import UUID_MATCH_RE, check_empty, list_symbols, truncate_list
from .yj_structure import SYM_TYPE
from .yj_to_epub_content import KFX_EPUB_Content
from .yj_to_epub_metadata import KFX_EPUB_Metadata
from .yj_to_epub_misc import KFX_EPUB_Misc
from .yj_to_epub_navigation import KFX_EPUB_Navigation
from .yj_to_epub_properties import GENERIC_FONT_NAMES, KFX_EPUB_Properties
from .yj_to_epub_resources import KFX_EPUB_Resources

if IS_PYTHON2:
    from .python_transition import str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


REPORT_MISSING_FONTS = True

RETAIN_USED_FRAGMENTS = False
RETAIN_UNUSED_RESOURCES = False


FRAGMENT_NAME_SYMBOL = {
    "$266": "$180",
    "$164": "$175",
    "$391": "$239",
    "$393": "$240",
    "$260": "$174",
    "$608": "$598",
    "$259": "$176",
    "$157": "$173",
}


class KFX_EPUB(
    KFX_EPUB_Content,
    KFX_EPUB_Metadata,
    KFX_EPUB_Misc,
    KFX_EPUB_Navigation,
    KFX_EPUB_Properties,
    KFX_EPUB_Resources,
):
    DEBUG = False

    def __init__(self, book, epub2_desired=False):
        self.book = book
        self.book_symbols = set()
        self.book_data = self.organize_fragments_by_type(book.fragments)
        self.is_kpf = book.kpf_container is not None
        self.used_fragments = {}
        self.epub = EPUB_Output(epub2_desired)
        self.epub.get_anchor_uri = self.get_anchor_uri

        self.determine_book_symbol_format()

        decimal.getcontext().prec = 6

        self.page_label_anchor_id = {}
        self.reported_duplicate_page_label = set()
        self.reported_pdf_errors = set()
        self.used_kfx_styles = set()
        self.missing_kfx_styles = set()
        self.css_rules = {}
        self.css_files = set()
        self.missing_special_classes = set()
        self.media_queries = collections.defaultdict(dict)
        self.font_names = set()
        self.missing_font_names = set()
        self.font_name_replacements = {}
        self.font_faces = []
        self.location_filenames = {}
        self.reported_characters = set()
        self.text_combine_in_use = False
        self.incorrect_font_quoting = set()

        for name in GENERIC_FONT_NAMES:
            self.fix_font_name(name, add=True, generic=True)

        self.nav_container_section = {}
        self.navto_anchor = {}
        self.toc_entry_count = 0
        self.anchor_uri = {}
        self.anchor_elem = {}
        self.anchor_id = {}
        self.anchor_ids = set()
        self.position_anchors = {}
        self.anchor_positions = {}
        self.used_anchors = set()
        self.immovable_anchors = set()
        self.page_anchor_id_label = {}
        self.fix_condition_href = False
        self.has_conditional_content = False
        self.context_ = []
        self.save_resources = True

        self.cde_content_type = ""

        self.resource_cache = {}
        self.used_raw_media = set()

        self.process_fonts()
        self.process_document_data()
        self.process_content_features()
        self.process_metadata()

        if self.epub.illustrated_layout:
            raise Exception("Illustrated layout (Kindle in Motion) is not supported.")

        self.set_condition_operators()

        self.process_anchors()
        self.process_navigation()

        for style_name, yj_properties in self.book_data.get("$157", {}).items():
            self.check_fragment_name(yj_properties, "$157", style_name, delete=False)

        self.process_reading_order()

        if self.cover_resource and not self.epub.html_cover:
            try:
                self.process_external_resource(
                    self.cover_resource
                ).manifest_entry.is_cover_image = True
            except:
                print(self.cover_resource, "+++++++++")
                pass

        self.fixup_anchors_and_hrefs()
        self.update_default_font_and_language()
        self.set_html_defaults()
        self.fixup_styles_and_classes()
        self.create_css_files()
        self.prepare_book_parts()

        if self.position_anchors:
            pos = []
            for id in self.position_anchors:
                for offset in self.position_anchors[id]:
                    pos.append("%s.%s" % (id, offset))

            log.error(
                "Failed to locate %d referenced positions: %s"
                % (len(pos), ", ".join(truncate_list(sorted(pos))))
            )

        if RETAIN_UNUSED_RESOURCES:
            for external_resource in self.book_data.get("$164", {}):
                self.process_external_resource(external_resource)

        self.check_empty(self.book_data.pop("$164", {}), "external_resource")

        self.report_duplicate_anchors()

        raw_media = self.book_data.pop("$417", {})
        for used_raw_media in self.used_raw_media:
            raw_media.pop(used_raw_media)

        self.check_empty(raw_media, "raw_media")
        self.check_empty(self.book_data.pop("$260", {}), "$260")

        storyline = self.book_data.pop("$259", {})
        if not self.book.is_kpf_prepub:
            self.check_empty(storyline, "$259")

        kfx_styles = self.book_data.pop("$157", {})
        for used_kfx_style in self.used_kfx_styles:
            kfx_styles.pop(used_kfx_style)

        self.check_empty(kfx_styles, "kfx styles")

        self.book_data.pop("$270", None)
        self.book_data.pop("$593", None)
        self.book_data.pop("$ion_symbol_table", None)
        self.book_data.pop("$270", None)
        self.book_data.pop("$419", None)
        self.book_data.pop("$145", None)
        self.book_data.pop("$608", None)
        self.book_data.pop("$692", None)
        self.book_data.pop("$756", None)

        self.book_data.pop("$550", None)

        self.book_data.pop("$265", None)

        self.book_data.pop("$264", None)

        if "$395" in self.book_data:
            resource_path = self.book_data.pop("$395")
            for ent in resource_path.pop("$247", []):
                ent.pop("$175", None)
                ent.pop("$166", None)
                self.check_empty(ent, "%s %s" % ("$395", "$247"))

            self.check_empty(resource_path, "$395")

        self.book_data.pop("$609", None)
        self.book_data.pop("$621", None)

        self.book_data.pop("$597", None)
        self.book_data.pop("$610", None)
        self.book_data.pop("$611", None)

        self.book_data.pop("$387", None)
        self.book_data.pop("$267", None)

        self.check_empty(self.book_data, "Book fragments")

        if self.missing_font_names:
            if REPORT_MISSING_FONTS:
                log.warning(
                    "Missing font family names: %s"
                    % list_symbols(self.missing_font_names)
                )
            else:
                log.info(
                    "Missing referenced font family names: %s"
                    % list_symbols(self.missing_font_names)
                )

            if self.font_names:
                log.info(
                    "Present referenced font family names: %s"
                    % list_symbols(self.font_names)
                )

    def decompile_to_epub(self):
        return self.epub.generate_epub()

    def organize_fragments_by_type(self, fragment_list):
        font_count = 0
        categorized_data = {}
        last_container_id = None

        for fragment in fragment_list:
            id = fragment.fid
            self.book_symbols.add(id)

            if fragment.ftype == "$270":
                id = last_container_id = IonSymbol(
                    "%s:%s"
                    % (fragment.value.get("$161", ""), fragment.value.get("$409", ""))
                )
            elif fragment.ftype == "$593":
                id = last_container_id
            elif fragment.ftype == "$262":
                id = IonSymbol("%s-font-%03d" % (id, font_count))
                font_count += 1
            elif fragment.ftype == "$387":
                id = IonSymbol("%s:%s" % (id, fragment.value["$215"]))

            dt = categorized_data.setdefault(fragment.ftype, {})

            if id not in dt:
                dt[id] = self.replace_ion_data(fragment.value)
            else:
                log.error("Book contains multiple %s fragments" % str(fragment))

        for category, ids in categorized_data.items():
            if len(ids) == 1:
                id = list(ids)[0]
                if id == category:
                    categorized_data[category] = categorized_data[category][id]
            elif None in ids:
                log.error(
                    "Fragment list contains mixed null/non-null ids of type '%s'"
                    % category
                )

        return categorized_data

    def determine_book_symbol_format(self):
        sym_type_counts = collections.defaultdict(lambda: 0)

        for book_symbol in self.book_symbols:
            symbol_type = self.book.classify_symbol(book_symbol)
            sym_type_counts[symbol_type] += 1

        sym_type_counts[SYM_TYPE.ORIGINAL] += sym_type_counts[SYM_TYPE.UNKNOWN] // 10

        symbol_quarum = (
            sym_type_counts[SYM_TYPE.DICTIONARY]
            + sym_type_counts[SYM_TYPE.SHORT]
            + sym_type_counts[SYM_TYPE.BASE64]
            + sym_type_counts[SYM_TYPE.ORIGINAL]
        ) // 2

        if sym_type_counts[
            SYM_TYPE.SHORT
        ] >= symbol_quarum or "max_id" in self.book_data.get("$538", {}):
            self.book_symbol_format = SYM_TYPE.SHORT
        elif sym_type_counts[SYM_TYPE.DICTIONARY] >= symbol_quarum:
            self.book_symbol_format = SYM_TYPE.DICTIONARY
        elif sym_type_counts[SYM_TYPE.BASE64] >= symbol_quarum:
            self.book_symbol_format = SYM_TYPE.BASE64
        else:
            self.book_symbol_format = SYM_TYPE.ORIGINAL

        if self.book_symbol_format != SYM_TYPE.SHORT:
            log.info("Book symbol format is %s" % self.book_symbol_format)

    def unique_part_of_local_symbol(self, symbol):
        name = str(symbol)

        if self.book_symbol_format == SYM_TYPE.SHORT:
            name = re.sub(r"^resource/", "", name, count=1)
            pass
        elif self.book_symbol_format == SYM_TYPE.DICTIONARY:
            name = re.sub(r"^G", "", name, count=1)
        elif self.book_symbol_format == SYM_TYPE.BASE64:
            name = re.sub(r"^(resource/)?[a-zA-Z0-9_-]{22}", "", name, count=1)
        else:
            name = re.sub(
                r"^V_[0-9]_[0-9](-PARA|-CHAR)?-[0-9]_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}",
                "",
                name,
                count=1,
            )
            name = re.sub(
                r"^(fonts/|images/)?(res|resource)_[0-9]_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}_",
                "",
                name,
                count=1,
            )
            name = re.sub(UUID_MATCH_RE, "", name, count=1)

        while name.startswith("-") or name.startswith("_"):
            name = name[1:]

        return name

    def prefix_unique_part_of_symbol(self, unique_part, prefix):
        if not unique_part:
            return prefix

        if re.match("^[A-Za-z0-9]+(-.+)?$", unique_part) or not re.match(
            "^[A-Za-z]", unique_part
        ):
            return "%s_%s" % (prefix, unique_part)

        return unique_part

    def replace_ion_data(self, f):
        data_type = ion_type(f)

        if data_type is IonAnnotation:
            return self.replace_ion_data(f.value)

        if data_type is IonList:
            return [self.replace_ion_data(fc) for fc in f]

        if data_type is IonSExp:
            return IonSExp([self.replace_ion_data(fc) for fc in f])

        if data_type is IonStruct:
            newf = IonStruct()
            for fk, fv in f.items():
                newf[self.replace_ion_data(fk)] = self.replace_ion_data(fv)

            return newf

        if data_type is IonSymbol:
            self.book_symbols.add(f)

        return f

    def get_fragment(self, ftype=None, fid=None, delete=True):
        if ion_type(fid) not in [IonString, IonSymbol]:
            return fid

        if ftype in self.book_data:
            fragment_container = self.book_data[ftype]
        elif ftype == "$393" and "$394" in self.book_data:
            fragment_container = self.book_data["$394"]
        else:
            fragment_container = {}

        data = (
            fragment_container.pop(fid, None) if delete else fragment_container.get(fid)
        )
        if data is None:
            used_data = self.used_fragments.get((ftype, fid))
            if used_data is not None:
                if RETAIN_USED_FRAGMENTS:
                    log.warning(
                        "book fragment used multiple times: %s %s" % (ftype, fid)
                    )
                    data = used_data
                else:
                    log.error("book fragment used multiple times: %s %s" % (ftype, fid))
                    data = IonStruct()
            else:
                log.error("book is missing fragment: %s %s" % (ftype, fid))
                data = IonStruct()
        else:
            self.used_fragments[(ftype, fid)] = (
                copy.deepcopy(data) if RETAIN_USED_FRAGMENTS else True
            )

        data_name = self.get_fragment_name(data, ftype, delete=False)
        if data_name and data_name != fid:
            log.error("Expected %s named %s but found %s" % (ftype, fid, data_name))
        return data

    def get_named_fragment(self, structure, ftype=None, delete=True, name_symbol=None):
        return self.get_fragment(
            ftype=ftype,
            fid=structure.pop(name_symbol or FRAGMENT_NAME_SYMBOL[ftype]),
            delete=delete,
        )

    def get_location_id(self, structure):
        id = structure.pop("$155", None) or structure.pop("$598", None)
        if id is not None:
            id = str(id)

        return id

    def check_fragment_name(self, fragment_data, ftype, fid, delete=True):
        name = self.get_fragment_name(fragment_data, ftype, delete)
        if name != fid:
            log.error("Fragment %s %s has incorrect name %s" % (ftype, fid, name))

    def get_fragment_name(self, fragment_data, ftype, delete=True):
        return self.get_structure_name(
            fragment_data, FRAGMENT_NAME_SYMBOL[ftype], delete
        )

    def get_structure_name(self, structure, name_key, delete=True):
        return (
            structure.pop(name_key, None) if delete else structure.get(name_key, None)
        )

    def check_empty(self, a_dict, dict_name):
        check_empty(a_dict, dict_name)

    def fix_html_id(self, id):
        return self.epub.fix_html_id(id)
