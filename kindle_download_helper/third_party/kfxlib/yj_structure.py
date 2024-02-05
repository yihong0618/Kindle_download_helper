from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import io
import random
import re
import string

from PIL import Image

from .ion import (
    IS,
    IonAnnotation,
    IonInt,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    ion_data_eq,
    ion_type,
    unannotated,
)
from .kfx_container import KfxContainer
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    EXTS_OF_MIMETYPE,
    UUID_MATCH_RE,
    disable_debug_log,
    jpeg_type,
    list_symbols,
    list_truncated,
    natural_sort_key,
    type_name,
)
from .version import __version__
from .yj_container import (
    ALLOWED_BOOK_FRAGMENT_TYPES,
    CONTAINER_FORMAT_KFX_MAIN,
    CONTAINER_FRAGMENT_TYPES,
    KNOWN_FRAGMENT_TYPES,
    REQUIRED_BOOK_FRAGMENT_TYPES,
    ROOT_FRAGMENT_TYPES,
    SINGLETON_FRAGMENT_TYPES,
    YJFragment,
    YJFragmentKey,
    YJFragmentList,
)
from .yj_versions import is_known_aux_metadata, is_known_kcb_data

if IS_PYTHON2:
    from .python_transition import repr, str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


REPORT_KNOWN_PROBLEMS = None
REPORT_NON_JPEG_JFIF_COVER = False
REPORT_JPEG_VARIANTS = False


MAX_CONTENT_FRAGMENT_SIZE = 8192

APPROXIMATE_PAGE_LIST = "APPROXIMATE_PAGE_LIST"
KFX_COVER_RESOURCE = "kfx_cover_image"

DICTIONARY_RULES_SYMBOL = "dictionary_rules"


METADATA_SYMBOLS = {
    "ASIN": "$224",
    "asset_id": "$466",
    "author": "$222",
    "cde_content_type": "$251",
    "cover_image": "$424",
    "description": "$154",
    "language": "$10",
    "orientation": "$215",
    "publisher": "$232",
    "reading_orders": "$169",
    "support_landscape": "$218",
    "support_portrait": "$217",
    "title": "$153",
}

METADATA_NAMES = {}
for k, v in METADATA_SYMBOLS.items():
    METADATA_NAMES[v] = k


FORMAT_SYMBOLS = {
    "bmp": "$599",
    "gif": "$286",
    "jpg": "$285",
    "jxr": "$548",
    "pbm": "$420",
    "pdf": "$565",
    "png": "$284",
    "pobject": "$287",
    "tiff": "$600",
    "bpg": "$612",
}

SYMBOL_FORMATS = {}
for k, v in FORMAT_SYMBOLS.items():
    SYMBOL_FORMATS[v] = k


CHECKED_IMAGE_FMTS = {
    "bmp",
    "bpg",
    "gif",
    "ico",
    "jpg",
    "pbm",
    "png",
    "svg",
    "tiff",
    "webp",
}
UNCHECKED_IMAGE_FMTS = {"jxr", "kvg", "pdf"}
ALL_IMAGE_FMTS = CHECKED_IMAGE_FMTS | UNCHECKED_IMAGE_FMTS


FRAGMENT_ID_KEYS = {
    "$266": ["$180"],
    "$597": ["$174", "$598"],
    "$418": ["$165"],
    "$417": ["$165"],
    "$394": ["$240"],
    "$145": ["name"],
    "$164": ["$175"],
    "$391": ["$239"],
    "$692": ["name"],
    "$387": ["$174"],
    "$756": ["$757"],
    "$260": ["$174"],
    "$267": ["$174"],
    "$609": ["$174"],
    "$259": ["$176"],
    "$608": ["$598"],
    "$157": ["$173"],
    "$610": ["$602"],
}


COMMON_FRAGMENT_REFERENCES = {
    "$749": "$259",
    "$266": "$266",
    "$597": "$597",
    "$429": "$157",
    "$479": "$164",
    "$145": "$145",
    "$146": "$608",
    "$245": "$164",
    "$179": "$266",
    "$165": "$417",
    "$392": "$391",
    "name": "$145",
    "$167": "$164",
    "$175": "$164",
    "$757": "$756",
    "$174": "$260",
    "$170": "$260",
    "$176": "$259",
    "$157": "$157",
    "$173": "$157",
    "$528": "$164",
    "$214": "$164",
    "$636": "$417",
    "$635": "$164",
}


NESTED_FRAGMENT_REFERENCES = {
    ("$597", "$351"): "$597",
    ("$597", "$538"): "$597",
    ("$597", "$613"): "$597",
    ("$597", "$614"): "$597",
}


SPECIAL_FRAGMENT_REFERENCES = {
    "$391": {
        "$247": "$394",
    },
    "$387": {
        "$213": "$164",
        "$214": "$164",
        "$212": "$164",
    },
}


SPECIAL_PARENT_FRAGMENT_REFERENCES = {
    "$538": {
        "yj.print.style": False,
    },
}


SECTION_DATA_TYPES = {
    "$387",
    "$260",
    "$267",
    "$609",
}


EXPECTED_ANNOTATIONS = {
    ("$164", "$214", "$164"),
    ("$389", "$247", "$393"),
    ("$389", "$392", "$391"),
    ("$259", "$429", "$157"),
    ("$259", "$173", "$157"),
}


EXPECTED_DICTIONARY_ANNOTATIONS = {
    ("$260", "$141", "$608"),
    ("$259", "$146", "$608"),
}


EID_REFERENCES = {
    "$185",
    "$155",
    "$598",
    "$754",
    "$474",
    "$163",
}


class SYM_TYPE:
    COMMON = "common"
    DICTIONARY = "dictionary"
    ORIGINAL = "original"
    BASE64 = "base64"
    SHORT = "short"
    SHARED = "shared"
    UNKNOWN = "unknown"


class BookStructure(object):
    def check_consistency(self):
        fragment_id_types = collections.defaultdict(set)
        for fragment in self.fragments:
            if fragment.ftype not in KNOWN_FRAGMENT_TYPES:
                log.error("Fragment has unknown type: %s" % str(fragment))
            elif fragment.ftype in ROOT_FRAGMENT_TYPES and not (
                fragment.ftype == "$262" and self.is_kpf_prepub
            ):
                if fragment.ftype != fragment.fid:
                    log.error("Root fragment has unexpected id: %s" % str(fragment))
            elif fragment.ftype == fragment.fid:
                log.error("Non-root fragment has same id and type: %s" % str(fragment))

            if fragment.ftype in FRAGMENT_ID_KEYS:
                value_fid = None

                if ion_type(fragment.value) is IonStruct:
                    for id_key in FRAGMENT_ID_KEYS[fragment.ftype]:
                        if id_key in fragment.value:
                            value_fid = fragment.value[id_key]

                            if fragment.ftype == "$609" and (
                                self.is_dictionary or self.is_kpf_prepub
                            ):
                                value_fid = IS(str(value_fid) + "-spm")
                            elif fragment.ftype == "$610" and isinstance(
                                value_fid, int
                            ):
                                value_fid = IonSymbol("eidbucket_%d" % value_fid)
                            break

                    if fragment.fid != value_fid and not (
                        self.is_kpf_prepub and fragment.ftype == "$608"
                    ):
                        log.error(
                            "Fragment type %s id %s has incorrect name %s"
                            % (fragment.ftype, fragment.fid, value_fid)
                        )

            fragment_id_types[fragment.fid].add(fragment.ftype)

        for fid, ftypes in sorted(list(fragment_id_types.items())):
            if len(ftypes) > 1 and (
                len(ftypes - SECTION_DATA_TYPES) > 0
                or self.is_dictionary
                or self.is_kpf_prepub
            ):
                log.error(
                    "Book contains fragment id %s with multiple types %s"
                    % (fid, list_symbols(ftypes))
                )

        for ftype in sorted(list(SINGLETON_FRAGMENT_TYPES)):
            if len(self.fragments.get_all(ftype)) > 1:
                log.error(
                    "Multiple %s fragments present (only one allowed per book)" % ftype
                )

        containers = {}
        entity_map_container_id = None
        for fragment in self.fragments.get_all("$270"):
            if "$409" in fragment.value:
                container_id = fragment.value["$409"]
                containers[container_id] = fragment

                if (
                    fragment.value["$161"] == CONTAINER_FORMAT_KFX_MAIN
                    and not self.is_magazine
                ):
                    asset_id = self.get_asset_id()
                    if asset_id and asset_id != container_id:
                        log.error(
                            "asset_id (%s) != main container_id (%s)"
                            % (asset_id, container_id)
                        )

                for ftype, fid in fragment.value.get("$181", []):
                    if ftype == 419:
                        entity_map_container_id = container_id
                        break

        container_entity_map = self.fragments.get("$419", first=True)
        if container_entity_map is not None:
            cem_container_ids = set()

            for cem_container_info in container_entity_map.value["$252"]:
                container_id = cem_container_info["$155"]
                cem_container_ids.add(container_id)
                cem_fragment_ids = set(cem_container_info.get("$181", []))

                if cem_fragment_ids:
                    container = containers.get(container_id)
                    if container is not None and "$181" in container.value:
                        container_fragment_ids = set(
                            [
                                self.symtab.get_symbol(e[1])
                                for e in container.value["$181"]
                                if e[0] != e[1]
                            ]
                        )

                        cem_missing_fids = (
                            cem_fragment_ids - container_fragment_ids
                        ) - {"$348"}
                        if cem_missing_fids:
                            self.log_known_error(
                                "Entity map references missing fragments in %s: %s"
                                % (container_id, list_truncated(cem_missing_fids))
                            )
                            self.reported_missing_fids.update(cem_missing_fids)

                        extra_fids = (container_fragment_ids - cem_fragment_ids) - {
                            "$348"
                        }
                        if extra_fids:
                            log.error(
                                "Found fragments in %s missing from entity map: %s"
                                % (container_id, list_truncated(extra_fids))
                            )

            actual_container_ids = set(containers.keys())
            missing_container_ids = cem_container_ids - actual_container_ids
            if missing_container_ids:
                print(missing_container_ids, "!!!")
                raise Exception(
                    "Book is incomplete. All of the KFX container files that make up the book must be combined "
                    "into a KFX-ZIP file for successful conversion. (Missing containers %s)"
                    % list_symbols(list(missing_container_ids))
                )
                log.error(
                    "Entity map references missing containers: %s"
                    % list_symbols(missing_container_ids)
                )

            extra_ids = actual_container_ids - cem_container_ids

            if entity_map_container_id:
                extra_ids -= {entity_map_container_id}

            if extra_ids:
                log.error(
                    "Found containers missing from entity map: %s"
                    % list_symbols(extra_ids)
                )

        required_ftypes = REQUIRED_BOOK_FRAGMENT_TYPES.copy()
        allowed_ftypes = ALLOWED_BOOK_FRAGMENT_TYPES.copy()
        present_ftypes = self.fragments.ftypes()

        if self.is_dictionary or self.is_kpf_prepub:
            required_ftypes.remove("$419")
            required_ftypes.remove("$265")
            required_ftypes.remove("$264")
        else:
            required_ftypes.remove("$611")

            if (
                self.get_feature_value(
                    "kfxgen.positionMaps", namespace="format_capabilities"
                )
                != 2
            ):
                allowed_ftypes.remove("$609")
                allowed_ftypes.remove("$621")

        if not self.is_kpf_prepub:
            allowed_ftypes.remove("$610")

        if self.is_dictionary or self.is_magazine or self.is_print_replica:
            required_ftypes.remove("$550")

            if not self.is_dictionary:
                allowed_ftypes.discard("$621")

        if not self.is_magazine:
            allowed_ftypes.remove("$267")
            allowed_ftypes.remove("$390")

        if self.is_kfx_v1:
            required_ftypes.remove("$538")
            required_ftypes.discard("$265")

        allowed_ftypes.update(required_ftypes)

        if "$490" in present_ftypes:
            required_ftypes.remove("$258")
        elif "$258" in present_ftypes:
            required_ftypes.remove("$490")

        missing_ftypes = required_ftypes - present_ftypes
        if missing_ftypes:
            missing_ft = list_symbols(missing_ftypes)

            if missing_ftypes == {"$389"}:
                log.warning("Book incomplete. Missing %s" % missing_ft)
            else:
                raise Exception(
                    "Book is incomplete. All of the KFX container files that make up the book must be combined "
                    "into a KFX-ZIP file for successful conversion. (Missing fragments %s)"
                    % missing_ft
                )
                log.error("Book incomplete. Missing %s" % missing_ft)

        extra_ftypes = present_ftypes - allowed_ftypes
        if extra_ftypes:
            log.error(
                "Book has unexpected fragment types: %s" % list_symbols(extra_ftypes)
            )

        document_data = self.fragments.get("$538", first=True)
        reading_orders = (
            [] if document_data is None else document_data.value.get("$169", [])
        )

        metadata = self.fragments.get("$258", first=True)
        metadata_reading_orders = (
            [] if metadata is None else metadata.value.get("$169", [])
        )

        if document_data is not None:
            if metadata is not None and not ion_data_eq(
                reading_orders, metadata_reading_orders, report_errors=False
            ):
                log.error("document_data and metadata reading_orders do not match")
        else:
            reading_orders = metadata_reading_orders

        reading_order_names = []
        reading_order_sections = []
        for i, reading_order in enumerate(reading_orders):
            reading_order_names.append(reading_order.get("$178", ""))
            reading_order_sections.extend(reading_order.get("$170", []))

            extra_keys = set(reading_order.keys()) - {"$178", "$170"}
            if extra_keys:
                log.error(
                    "Unexpected reading_order %d data: %s"
                    % (i, list_symbols(extra_keys))
                )

        if self.get_metadata_value("periodicals_generation_V2", default=False):
            if len(reading_orders) != 2:
                log.error(
                    "Magazine contains %d reading_orders: %s"
                    % (len(reading_orders), list_symbols(reading_order_names))
                )
            elif reading_order_names != ["$351", "$701"]:
                log.error(
                    "Unexpected magazine reading order names: %s"
                    % list_symbols(reading_order_names)
                )
        else:
            if len(reading_orders) != 1:
                log.error(
                    "Book contains %d reading_orders: %s"
                    % (len(reading_orders), list_symbols(reading_order_names))
                )
            elif (not self.is_magazine) and reading_order_names[0] not in [
                "$351",
                "order-1",
                "TargetReadingOrder",
            ]:
                log.error(
                    "Unexpected book reading order names: %s"
                    % list_symbols(reading_order_names)
                )

        book_navigation = self.fragments.get("$389", first=True)
        if book_navigation is not None:
            reading_order_names = set(reading_order_names)
            nav_reading_order_names = set()

            for nav in book_navigation.value:
                nav_reading_order_names.add(nav.get("$178", ""))
                found_nav_types = set()

                for nav_container in nav.get("$392", []):
                    if ion_type(nav_container) is IonSymbol:
                        nav_container = self.fragments.get(
                            ftype="$391", fid=nav_container
                        )

                    if nav_container is not None:
                        nav_type = unannotated(nav_container).get("$235", None)
                        if nav_type not in {"$212", "$236", "$237", "$213", "$214"}:
                            log.warning("Unexpected nav_type: %s" % nav_type)
                        elif nav_type in found_nav_types:
                            log.warning("Duplicate nav_type: %s" % nav_type)

                        found_nav_types.add(nav_type)

            missing_reading_order_names = reading_order_names - nav_reading_order_names
            if missing_reading_order_names:
                log.warning(
                    "Navigation has missing reading orders: %s"
                    % list_symbols(missing_reading_order_names)
                )

            extra_reading_order_names = nav_reading_order_names - reading_order_names
            if extra_reading_order_names:
                log.warning(
                    "Navigation has extra reading orders: %s"
                    % list_symbols(extra_reading_order_names)
                )

        reading_order_sections = set(reading_order_sections)
        sections = set()
        for fragment in self.fragments.get_all("$260"):
            sections.add(fragment.fid)

        missing_reading_order_sections = sections - reading_order_sections
        if missing_reading_order_sections:
            log.warning(
                "Reading order has missing sections: %s"
                % list_symbols(missing_reading_order_sections)
            )

        extra_reading_order_sections = reading_order_sections - sections
        if extra_reading_order_sections:
            log.warning(
                "Reading order has extra sections: %s"
                % list_symbols(extra_reading_order_sections)
            )

        has_content_fragment = False
        for fragment in self.fragments.get_all("$145"):
            has_content_fragment = True
            content_bytes = 0
            for content in fragment.value["$146"][:-1]:
                content_bytes += len(content.encode("utf8"))

            if content_bytes >= MAX_CONTENT_FRAGMENT_SIZE:
                log.error(
                    "Content %s: %d bytes exceeds maximum (%d bytes)"
                    % (fragment.fid, content_bytes, MAX_CONTENT_FRAGMENT_SIZE)
                )

        for fragment in self.fragments.get_all("$395"):
            if len(fragment.value["$247"]) > 0 and not self.is_magazine:
                log.warning("resource_path of %s contains entries" % self.cde_type)

        is_sample = self.get_metadata_value("is_sample", default=False)
        if (self.cde_type == "EBSP") is not is_sample:
            log.warning(
                "Feature/content mismatch: cde_type=%s, is_sample=%s"
                % (self.cde_type, is_sample)
            )

        has_hdv_image = has_tiles = has_overlapped_tiles = has_jpeg_rst_marker = (
            has_jpeg_xr_image
        ) = False

        for fragment in self.fragments.get_all("$164"):
            resource_name = str(fragment.fid)
            resource = fragment.value

            format_fmt = ""
            format = resource.get("$161")
            if format is not None:
                if format in SYMBOL_FORMATS:
                    format_fmt = SYMBOL_FORMATS[format]
                else:
                    log.error(
                        "External resource %s has unexpected format: %s"
                        % (resource_name, format)
                    )

            mime_fmt = ""
            mime = resource.get("$162")
            if mime is not None:
                if mime in EXTS_OF_MIMETYPE:
                    mime_fmt = EXTS_OF_MIMETYPE[mime][0][1:]

                    if not format_fmt:
                        format_fmt = mime_fmt
                else:
                    log.error(
                        "External resource %s format %s has unknown mime type: %s"
                        % (resource_name, format_fmt, repr(mime))
                    )

            resource_height = resource.get("$423", 0) or resource.get("$67", 0)
            resource_width = resource.get("$422", 0) or resource.get("$66", 0)
            location = resource.get("$165", None)

            if resource_height > 1920 or resource_width > 1920:
                has_hdv_image = True

            if "$636" in resource:
                has_tiles = True

                if "$797" in resource:
                    has_overlapped_tiles = True

            if format_fmt in ALL_IMAGE_FMTS:
                if location is not None:
                    if ion_type(location) is not IonString:
                        log.error(
                            "Resource %s location is type %s"
                            % (str(fragment.fid), type_name(location))
                        )

                    raw_media = self.fragments.get(
                        ftype="$417", fid=location, first=True
                    )
                    if raw_media is not None:
                        image_data = raw_media.value.tobytes()

                        if (
                            format_fmt in UNCHECKED_IMAGE_FMTS
                            or mime_fmt in UNCHECKED_IMAGE_FMTS
                        ):
                            img_ok = True
                            img_format = format_fmt
                            img_transparent = img_animated = False
                            img_width, img_height = (0, 0)
                        else:
                            with disable_debug_log():
                                try:
                                    img = Image.open(io.BytesIO(image_data))
                                    img_format = img.format.lower().replace(
                                        "jpeg", "jpg"
                                    )

                                    img_width, img_height = (
                                        (0, 0)
                                        if img_format in ["gif", "webp"]
                                        else img.size
                                    )

                                    img_transparent = (
                                        img.mode == "P" and "transparency" in img.info
                                    )

                                    try:
                                        img.seek(1)
                                    except EOFError:
                                        img_animated = False
                                    else:
                                        img_animated = True

                                    img.close()

                                except Exception as e:
                                    log.info(repr(e))
                                    img_ok = False
                                else:
                                    img_ok = True

                        if img_ok:
                            if img_format in [
                                "gif",
                                "jpg",
                                "jxr",
                                "kvg",
                                "pdf",
                                "png",
                                "webp",
                            ]:
                                if (
                                    format != "$287"
                                    and format_fmt
                                    and format_fmt != img_format
                                ):
                                    log.warning(
                                        "Resource %s has image format %s and resource format %s"
                                        % (resource_name, img_format, format_fmt)
                                    )

                                if (
                                    mime != "figure"
                                    and mime_fmt
                                    and mime_fmt != img_format
                                ):
                                    if not (
                                        img_format in ["jpg", "jxr"]
                                        and format_fmt == img_format
                                        and mime == "image/svg+xml"
                                    ):
                                        log.warning(
                                            "Resource %s has image format %s and mime type %s"
                                            % (resource_name, img_format, mime)
                                        )

                                if img_format == "jpg" and REPORT_JPEG_VARIANTS:
                                    jtype = jpeg_type(image_data)
                                    if jtype not in ["JPEG"]:
                                        log.warning(
                                            "Resource %s is unexpected JPEG variant %s"
                                            % (resource_name, jtype)
                                        )

                                if (
                                    img_format == "jpg"
                                    and (not has_jpeg_rst_marker)
                                    and re.search(b"\xff[\xd0-\xd7]", image_data)
                                ):
                                    has_jpeg_rst_marker = True

                                if img_format == "jxr":
                                    has_jpeg_xr_image = True

                                if (
                                    img_width
                                    and img_height
                                    and resource_width
                                    and resource_height
                                    and (
                                        img_width != resource_width
                                        or img_height != resource_height
                                    )
                                ):
                                    log.warning(
                                        "Resource %s is %dx%d, image %s is %dx%d"
                                        % (
                                            resource_name,
                                            resource_width,
                                            resource_height,
                                            location,
                                            img_width,
                                            img_height,
                                        )
                                    )

                                if img_transparent and not self.is_magazine:
                                    log.warning(
                                        "Image at location %s has transparency"
                                        % location
                                    )

                                if img_animated and img_format != "webp":
                                    log.warning(
                                        "Image at location %s has animation" % location
                                    )
                            else:
                                log.warning(
                                    "Resource %s has unexpected image format: %s"
                                    % (resource_name, img_format)
                                )
                        else:
                            log.warning(
                                "Resource %s location %s has bad image"
                                % (resource_name, location)
                            )

        yj_hdv = self.get_feature_value("yj_hdv")
        if has_tiles and yj_hdv is None:
            log.warning("HDV image tiles detected without yj_hdv feature")
        elif has_overlapped_tiles and (yj_hdv is None or yj_hdv < 2):
            log.warning("HDV overlapped tiles detected without yj_hdv-2 feature")
        elif yj_hdv is not None and not (has_tiles or has_hdv_image):
            log.warning(
                "Feature/content mismatch: yj_hdv-%s without HDV image/tiles"
                % str(yj_hdv)
            )

        yj_jpg_rst_marker_present = self.get_feature_value("yj_jpg_rst_marker_present")
        if (yj_jpg_rst_marker_present is not None) is not has_jpeg_rst_marker:
            log.warning(
                "Feature/content mismatch: yj_jpg_rst_marker_present=%s has_jpeg_rst_marker=%s"
                % (yj_jpg_rst_marker_present, has_jpeg_rst_marker)
            )

        yj_jpegxr_sd = self.get_feature_value("yj_jpegxr_sd")
        if (yj_jpegxr_sd is not None) is not has_jpeg_xr_image:
            log.warning(
                "Feature/content mismatch: yj_jpegxr_sd=%s has_jpeg_xr_image=%s"
                % (yj_jpegxr_sd, has_jpeg_xr_image)
            )

        if REPORT_NON_JPEG_JFIF_COVER:
            cover_image_data = self.get_cover_image_data()
            if cover_image_data is not None:
                cover_fmt = jpeg_type(cover_image_data[1], cover_image_data[0])
                if cover_fmt != "JPEG":
                    log.warning(
                        "Incorrect cover image format for Kindle lockscreen display: %s"
                        % cover_fmt.upper()
                    )

        if self.has_pdf_resource:
            if self.get_feature_value("yj_non_pdf_fixed_layout") is not None:
                log.warning("yj_non_pdf_fixed_layout feature present with PDF resource")

            if self.get_feature_value("yj_fixed_layout") is None:
                log.warning("PDF resource present without yj_fixed_layout feature")

            if self.get_feature_value("yj_pdf_support") is None:
                log.warning("PDF resource present without yj_pdf_support feature")
        else:
            if self.get_feature_value("yj_fixed_layout") is not None:
                log.warning("yj_fixed_layout feature present without PDF resource")

            if self.get_feature_value("yj_pdf_support") is not None:
                log.warning("yj_pdf_support feature present without PDF resource")

        has_textBlock = False
        format_capability_sets = set()
        for fragment in self.fragments.get_all("$593"):
            fcxs = []
            for fc in fragment.value:
                fcxs.append((fc["$492"], fc["version"]))

            if ("kfxgen.textBlock", 1) in fcxs:
                has_textBlock = True

            format_capability_sets.add(tuple(sorted(fcxs)))

        if len(format_capability_sets) > 1:
            log.error(
                "Book has %d different format capabilities"
                % len(format_capability_sets)
            )
            log.info(str(format_capability_sets))

        if has_textBlock is not has_content_fragment:
            log.error(
                "textBlock=%s content_fragment=%s"
                % (has_textBlock, has_content_fragment)
            )

        for fragment in self.fragments.get_all("$597"):
            if len(set(fragment.value.keys()) - {"$258", "$598"}) > 0:
                log.error("Malformed auxiliary_data: %s" % repr(fragment))
            else:
                for kv in fragment.value.get("$258", []):
                    if len(kv) != 2 or "$492" not in kv or "$307" not in kv:
                        log.error("Malformed auxiliary_data value: %s" % repr(fragment))
                    else:
                        key = kv.get("$492", "")
                        value = kv.get("$307", "")
                        if not is_known_aux_metadata(key, value):
                            log.warning("Unknown auxiliary_data: %s=%s" % (key, value))

        asin = self.get_metadata_value("ASIN")
        content_id = self.get_metadata_value("content_id")
        if asin and content_id and content_id != asin:
            log.error("content_id (%s) != ASIN (%s)" % (content_id, asin))

        self.check_position_and_location_maps()

        if self.kpf_container is not None:
            for kcb_category, kcb_category_data in self.kpf_container.kcb_data.items():
                if kcb_category != "content_hash":
                    for kcb_key, kcb_values in kcb_category_data.items():
                        for kcb_value in (
                            kcb_values if isinstance(kcb_values, list) else [kcb_values]
                        ):
                            if not is_known_kcb_data(kcb_category, kcb_key, kcb_value):
                                log.warning(
                                    "Unknown KCB data: %s/%s=%s"
                                    % (kcb_category, kcb_key, kcb_value)
                                )

    def extract_fragment_id_from_value(self, ftype, value):
        if ion_type(value) is IonStruct and ftype in FRAGMENT_ID_KEYS:
            for id_key in FRAGMENT_ID_KEYS[ftype]:
                if id_key in value:
                    fid = value[id_key]

                    if ftype == "$609" and (self.is_dictionary or self.is_kpf_prepub):
                        fid = IS(str(fid) + "-spm")
                    elif ftype == "$610" and isinstance(fid, int):
                        fid = IonSymbol("eidbucket_%d" % fid)

                    return fid

        return ftype

    def check_fragment_usage(self, rebuild=False, ignore_extra=False):
        discovered = set()

        unreferenced_fragment_types = ROOT_FRAGMENT_TYPES - {"$419"}

        if self.is_kpf_prepub:
            unreferenced_fragment_types.add("$610")

        for fragment in self.fragments:
            if fragment.ftype in unreferenced_fragment_types:
                discovered.add(fragment)

            if fragment.ftype not in KNOWN_FRAGMENT_TYPES:
                discovered.add(fragment)

        cover_fid = self.get_metadata_value("cover_image")
        if cover_fid is not None:
            discovered.add(YJFragmentKey(ftype="$164", fid=cover_fid))

        visited = set()
        mandatory_references = {}
        optional_references = {}
        missing = set()
        eid_defs = set()
        eid_refs = set()

        for ftype in CONTAINER_FRAGMENT_TYPES:
            visited.add(YJFragmentKey(ftype=ftype))
            visited.add(YJFragmentKey(ftype=ftype, fid=ftype))

        while discovered:
            next_visits = discovered - visited
            discovered = set()

            for fragment in self.fragments:
                if fragment in next_visits:
                    mandatory_refs = set()
                    optional_refs = set()

                    self.walk_fragment(
                        fragment, mandatory_refs, optional_refs, eid_defs, eid_refs
                    )

                    visited.add(fragment)
                    mandatory_references[fragment] = mandatory_refs
                    optional_references[fragment] = optional_refs
                    discovered |= mandatory_refs | optional_refs

            missing |= next_visits - visited

        for key in sorted(list(missing)):
            if key.ftype == "$597":
                log.warning("Referenced fragment is missing from book: %s" % str(key))
            else:
                log.error("Referenced fragment is missing from book: %s" % str(key))

        referenced_fragments = YJFragmentList()
        unreferenced_fragments = YJFragmentList()
        already_processed = {}
        diff_dupe_fragments = False

        for fragment in self.fragments:
            if fragment.ftype not in ["$262", "$387"]:
                if fragment in already_processed:
                    if fragment.ftype in ["$270", "$593"]:
                        continue

                    if ion_data_eq(
                        fragment.value,
                        already_processed[fragment].value,
                        report_errors=False,
                    ):
                        if fragment.ftype == "$597":
                            self.log_known_error(
                                "Duplicate fragment: %s" % str(fragment)
                            )
                        else:
                            log.warning("Duplicate fragment: %s" % str(fragment))
                        continue
                    else:
                        log.error(
                            "Duplicate fragment key with different content: %s"
                            % str(fragment)
                        )
                        diff_dupe_fragments = True
                else:
                    already_processed[fragment] = fragment

            if fragment in visited:
                referenced_fragments.append(fragment)
            elif (fragment.ftype in CONTAINER_FRAGMENT_TYPES) or (
                fragment.fid == fragment.ftype
            ):
                log.error("Unexpected root fragment: %s" % str(fragment))
            elif fragment.ftype == "$597" and (self.is_sample or self.is_dictionary):
                pass
            elif not ignore_extra:
                unreferenced_fragments.append(fragment)

        if self.is_kpf_prepub:
            for fragment in list(unreferenced_fragments):
                if fragment.ftype in ["$391", "$266", "$259", "$608"]:
                    unreferenced_fragments.remove(fragment)

        if unreferenced_fragments:
            log.error(
                "Unreferenced fragments: %s" % list_truncated(unreferenced_fragments)
            )

        if diff_dupe_fragments:
            raise Exception(
                "Book appears to have KFX containers from multiple books. (duplicate fragments)"
            )
            pass

        undefined_eids = eid_refs - eid_defs
        if undefined_eids:
            log.error("Undefined EIDs: %s" % list_truncated(undefined_eids))

        if rebuild:
            if not self.is_dictionary:
                container_ids = set()
                kfxgen_application_version = kfxgen_package_version = version = None
                for fragment in self.fragments.get_all("$270"):
                    container_id_ = fragment.value.get("$409", "")
                    if container_id_:
                        container_ids.add(container_id_)

                    kfxgen_application_version = (
                        fragment.value.get("$587") or kfxgen_application_version
                    )
                    kfxgen_package_version = (
                        fragment.value.get("$588") or kfxgen_package_version
                    )
                    version = fragment.value.get("version") or version
                    referenced_fragments.discard(fragment)

                if len(container_ids) == 1:
                    container_id = list(container_ids)[0]
                else:
                    container_id = self.get_asset_id()

                if not container_id:
                    container_id = self.create_container_id()

                referenced_fragments.append(
                    YJFragment(
                        ftype="$270",
                        value=IonStruct(
                            IS("$409"),
                            container_id,
                            IS("$161"),
                            CONTAINER_FORMAT_KFX_MAIN,
                            IS("$587"),
                            kfxgen_application_version or "kfxlib-%s" % __version__,
                            IS("$588"),
                            kfxgen_package_version or "",
                            IS("version"),
                            version or KfxContainer.VERSION,
                        ),
                    )
                )

            self.fragments = YJFragmentList(sorted(referenced_fragments))

            if not self.is_dictionary:
                self.rebuild_container_entity_map(
                    container_id,
                    self.determine_entity_dependencies(
                        mandatory_references, optional_references
                    ),
                )

    def create_container_id(self):
        return "CR!%s" % "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(28)
        )

    def walk_fragment(
        self, fragment, mandatory_frag_refs, optional_frag_refs, eid_defs, eid_refs
    ):
        def walk(data, container=None, container_parent=None, top_level=False):
            data_type = ion_type(data)

            if container is None:
                container = fragment.ftype

            if data_type is IonAnnotation:
                if not top_level:
                    if len(data.annotations) != 1:
                        self.log_error_once(
                            "Found multiple annotations in %s of %s fragment"
                            % (container, fragment.ftype)
                        )

                    for annot in data.annotations:
                        if (
                            fragment.ftype,
                            container,
                            annot,
                        ) not in EXPECTED_ANNOTATIONS and (
                            self.is_dictionary
                            and (fragment.ftype, container, annot)
                            not in EXPECTED_DICTIONARY_ANNOTATIONS
                        ):
                            self.log_error_once(
                                "Found unexpected IonAnnotation %s in %s of %s fragment"
                                % (annot, container, fragment.ftype)
                            )

                walk(data.value, container, container_parent)

            elif data_type is IonList:
                for fc in data:
                    walk(fc, container, container_parent)

            elif data_type is IonStruct:
                for fk, fv in data.items():
                    walk(fv, fk, container)

            elif data_type is IonSExp:
                for fc in data[1:]:
                    walk(fc, data[0], container)

            elif data_type is IonString:
                if container in ["$165", "$636"]:
                    walk(IS(data), container, container_parent)

            elif data_type is IonSymbol:
                if container == "$155" or (self.is_kpf_prepub and container == "$174"):
                    eid_defs.add(data)

                if (
                    container_parent == fragment.ftype
                    and container in FRAGMENT_ID_KEYS.get(fragment.ftype, [])
                ):
                    pass
                else:
                    frag_ref = None

                    special_refs = SPECIAL_FRAGMENT_REFERENCES.get(fragment.ftype)
                    if special_refs is not None:
                        frag_ref = special_refs.get(container)

                    if frag_ref is None:
                        special_refs = SPECIAL_PARENT_FRAGMENT_REFERENCES.get(
                            fragment.ftype
                        )
                        if special_refs is not None:
                            frag_ref = special_refs.get(container_parent)

                    if frag_ref is None:
                        frag_ref = NESTED_FRAGMENT_REFERENCES.get(
                            (container_parent, container)
                        )

                    if frag_ref is None:
                        frag_ref = COMMON_FRAGMENT_REFERENCES.get(container)

                    if frag_ref is not None and frag_ref is not False:
                        if container == "name" and container_parent in ["$249", "$692"]:
                            mandatory_frag_refs.add(
                                YJFragmentKey(ftype="$692", fid=data)
                            )
                        elif (
                            container == "$165"
                            and self.fragments.get(ftype="$418", fid=data, first=True)
                            is not None
                        ):
                            mandatory_frag_refs.add(
                                YJFragmentKey(ftype="$418", fid=data)
                            )
                        elif container == "$635":
                            optional_frag_refs.add(
                                YJFragmentKey(ftype=frag_ref, fid=data)
                            )
                        else:
                            mandatory_frag_refs.add(
                                YJFragmentKey(ftype=frag_ref, fid=data)
                            )

                        if frag_ref == "$260":
                            for ref_key in [
                                YJFragmentKey(ftype="$609", fid=data),
                                YJFragmentKey(ftype="$609", fid=data + "-spm"),
                                YJFragmentKey(ftype="$597", fid=data + "-ad"),
                                YJFragmentKey(ftype="$597", fid=data),
                                YJFragmentKey(ftype="$267", fid=data),
                                YJFragmentKey(ftype="$387", fid=data),
                            ]:
                                if self.fragments.get(ref_key, first=True) is not None:
                                    mandatory_frag_refs.add(ref_key)

            if data_type is IonInt or data_type is IonSymbol:
                if container in {"$155", "$598"} and fragment.ftype not in {
                    "$550",
                    "$265",
                    "$264",
                    "$609",
                    "$610",
                    "$621",
                    "$611",
                }:
                    eid_defs.add(data)
                elif container in EID_REFERENCES:
                    if not (
                        data_type is IonInt and data == 0 and fragment.ftype == "$265"
                    ):
                        eid_refs.add(data)

        try:
            walk(fragment, top_level=True)
        except Exception:
            log.info("Exception processing fragment: %s" % repr(fragment))
            raise

    def determine_entity_dependencies(self, mandatory_references, optional_references):
        deep_references = {}

        for fragment, refs in mandatory_references.items():
            if fragment.ftype == "$387":
                mandatory_references[fragment] = set()

        for fragment, refs in mandatory_references.items():
            old_refs = set()
            new_refs = set(refs)

            if fragment.ftype == "$164":
                for n_fragment in list(new_refs):
                    if n_fragment.ftype == "$164":
                        new_refs.remove(n_fragment)

            while len(new_refs - old_refs) > 0:
                old_refs = old_refs | new_refs
                new_refs = set(old_refs)
                for ref in old_refs:
                    new_refs |= mandatory_references.get(ref, set())

            deep_references[fragment] = new_refs

        entity_dependencies = []

        for fragment in sorted(deep_references):
            mandatory_dependencies = []
            optional_dependencies = []

            for depends, dependant in [("$260", "$164"), ("$164", "$417")]:
                if fragment.ftype == depends:
                    for ref_fragment in sorted(deep_references[fragment]):
                        if ref_fragment.ftype == dependant:
                            mandatory_dependencies.append(ref_fragment.fid)

                            opt = optional_references.get(ref_fragment, [])
                            for opt_ref_fragment in sorted(opt):
                                if opt_ref_fragment.ftype == dependant:
                                    optional_dependencies.append(opt_ref_fragment.fid)

            if mandatory_dependencies:
                entity_dependencies.append(
                    IonStruct(
                        IS("$155"), fragment.fid, IS("$254"), mandatory_dependencies
                    )
                )

            if optional_dependencies:
                entity_dependencies.append(
                    IonStruct(
                        IS("$155"), fragment.fid, IS("$255"), optional_dependencies
                    )
                )

        return entity_dependencies

    def rebuild_container_entity_map(self, container_id, entity_dependencies=None):
        old_entity_dependencies = None
        new_fragments = YJFragmentList()
        entity_ids = []

        for fragment in self.fragments:
            if fragment.ftype == "$419":
                container_entity_map = fragment.value
                old_entity_dependencies = container_entity_map.get("$253", None)
            else:
                new_fragments.append(fragment)

                if (
                    fragment.ftype not in CONTAINER_FRAGMENT_TYPES
                    and fragment.fid != fragment.ftype
                    and fragment.fid not in entity_ids
                ):
                    entity_ids.append(fragment.fid)

        if entity_dependencies is None:
            entity_dependencies = old_entity_dependencies

        container_contents = IonStruct(IS("$155"), container_id, IS("$181"), entity_ids)

        container_entity_map = IonStruct(IS("$252"), [container_contents])

        if entity_dependencies:
            container_entity_map[IS("$253")] = entity_dependencies

        if entity_ids or entity_dependencies:
            new_fragments.append(YJFragment(ftype="$419", value=container_entity_map))

        else:
            log.error("Omitting container_entity_map due to lack of content")

        self.fragments = new_fragments

    def classify_symbol(self, name):
        if self.symtab.is_shared_symbol(IS(name)):
            return SYM_TYPE.SHARED

        if (
            name
            in [
                APPROXIMATE_PAGE_LIST,
                "crop_bleed",
                DICTIONARY_RULES_SYMBOL,
                "mkfx_id",
                "page_list_entry",
                "srl_created_by_stampler",
            ]
            or re.match(r"^content_[0-9]+$", name)
            or re.match(r"^eidbucket_[0-9]+$", name)
            or re.match(r"^PAGE_LIST_[0-9]{10,}$", name)
            or re.match(UUID_MATCH_RE, name)
            or re.match(r"^yj\.(authoring|conversion|print|semantics)\.", name)
            or name.startswith(KFX_COVER_RESOURCE)
        ):
            return SYM_TYPE.COMMON

        if re.match(r"^G[0-9]+(-spm)?$", name) or re.match(r"^yj\.dictionary\.", name):
            return SYM_TYPE.DICTIONARY

        if (
            re.match(
                r"^V_[0-9]_[0-9](-PARA|-CHAR)?-[0-9]_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}",
                name,
            )
            or re.match(
                r"^(fonts/|images/|resource/)?(res|resource)_[0-9]_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}_",
                name,
            )
            or re.match(
                r"^(anchor-|section-|story-|style-|navContainer|navUnit)[0-9]_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}",
                name,
            )
            or re.match(r"^anchor-[a-z0-9_-]+-[0-9]{17,19}-[0-9]{1,2}$", name)
            or re.match(
                r"^anchor-[a-z0-9_-]+_[0-9]_[0-9a-f]{12,16}_[0-9a-f]{1,5}$", name
            )
            or re.match(r"^(LANDMARKS_|TOC_)[0-9]{10,}$", name)
            or re.match(
                r"^(LazyLoadStoryLineForPage-|TargetSectionForPage-|TargetStoryLineForPage-)[0-9]+$",
                name,
            )
            or re.match(r"^slice_[0-9]+\.pdf$", name)
            or re.match(r"^Target_pg_[0-9]+_g_2$", name)
            or re.match(
                r"^KFXConditionalNavGroupUnit_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                name,
            )
            or name in ["order-1", "TargetReadingOrder", "PageLabels", "toc_entry"]
        ):
            return SYM_TYPE.ORIGINAL

        if re.match(
            r"^(resource/)?[A-Za-z0-9_-]{22}[A-Z0-9]{0,6}"
            r"((-hd|-first-frame|-thumb)?(-resized-[0-9]+-[0-9]+|-hd-tile-[0-9]+-[0-9]+)?|"
            r"-ad|-spm|_thumbnail|-transcoded|(_thumb)?\.jpg|\.ttf|\.otf|\.woff|\.eot|\.dfont|\.bin)?$",
            name,
        ):
            return SYM_TYPE.BASE64

        if re.match(
            r"^(resource/rsrc|resource/e|rsrc|[a-z])[A-Z0-9]{1,6}"
            r"((-hd|-first-frame|-thumb)?(-resized-[0-9]+-[0-9]+|-hd-tile-[0-9]+-[0-9]+)?|"
            r"-ad|-spm|_thumbnail|-transcoded|(_thumb)?\.jpg|\.ttf|\.otf|\.woff|\.eot|\.dfont|\.bin)?$",
            name,
        ):
            return SYM_TYPE.SHORT

        return SYM_TYPE.UNKNOWN

    def create_local_symbol(self, name):
        if self.classify_symbol(name) not in [
            SYM_TYPE.COMMON,
            SYM_TYPE.DICTIONARY,
            SYM_TYPE.BASE64,
            SYM_TYPE.SHORT,
        ]:
            log.error("Invalid local symbol created: %s" % name)

        return self.symtab.create_local_symbol(name)

    def check_symbol_table(self, rebuild=False, ignore_unused=False):
        used_symbols = set()
        original_symbols = set()
        for fragment in self.fragments:
            if fragment.ftype not in CONTAINER_FRAGMENT_TYPES:
                self.find_symbol_references(fragment, used_symbols)

            if fragment.ftype == "$ion_symbol_table":
                original_symbols |= set(fragment.value.get("symbols", []))

        new_symbols = set()
        for symbol in used_symbols:
            if not self.symtab.is_shared_symbol(symbol):
                new_symbols.add(str(symbol))

        missing_symbols = new_symbols - original_symbols

        if rebuild:
            missing_symbols -= set(self.symtab.get_local_symbols())

        if missing_symbols and not (self.is_dictionary or self.is_kpf_prepub):
            log.error(
                "Symbol table is missing symbols: %s"
                % list_truncated(missing_symbols, 20)
            )

        unused_symbols = original_symbols - new_symbols
        if unused_symbols and not ignore_unused:
            expected_unused_symbols = set()
            for symbol in list(unused_symbols):
                if (
                    symbol == "mkfx_id"
                    or re.match(UUID_MATCH_RE, symbol)
                    or symbol.startswith("PAGE_LIST_")
                    or symbol == "page_list_entry"
                    or (self.is_sample and symbol.endswith("-ad"))
                    or (
                        self.is_kpf_prepub
                        and (
                            symbol.startswith("yj.print.")
                            or symbol.startswith("yj.semantics.")
                        )
                    )
                    or symbol in self.reported_missing_fids
                ):
                    unused_symbols.remove(symbol)
                    expected_unused_symbols.add(symbol)

            if unused_symbols:
                log.warning(
                    "Symbol table contains %d unused symbols: %s"
                    % (len(unused_symbols), list_truncated(unused_symbols, 5))
                )

            if expected_unused_symbols:
                self.log_known_error(
                    "Symbol table contains %d expected unused symbols: %s"
                    % (
                        len(expected_unused_symbols),
                        list_truncated(expected_unused_symbols, 5),
                    )
                )

        if rebuild:
            book_symbols = []
            for symbol in used_symbols:
                if self.symtab.get_id(symbol, used=False) >= self.symtab.local_min_id:
                    book_symbols.append(str(symbol))

            self.symtab.replace_local_symbols(
                sorted(book_symbols, key=natural_sort_key)
            )
            self.replace_symbol_table_import()

    def replace_symbol_table_import(self):
        symtab_import = self.symtab.create_import()

        if symtab_import is not None:
            fragment = self.fragments.get("$ion_symbol_table")
            if fragment is not None:
                self.fragments.remove(fragment)

            self.fragments.insert(0, YJFragment(symtab_import))

    def find_symbol_references(self, data, s):
        data_type = ion_type(data)

        if data_type is IonAnnotation:
            for a in data.annotations:
                s.add(a)

            self.find_symbol_references(data.value, s)

        if data_type is IonList or data_type is IonSExp:
            for fc in data:
                self.find_symbol_references(fc, s)

        if data_type is IonStruct:
            for fk, fv in data.items():
                s.add(fk)
                self.find_symbol_references(fv, s)

        if data_type is IonSymbol:
            s.add(data)

    def get_reading_orders(self):
        document_data = self.fragments.get("$538", first=True)

        if document_data is not None:
            return document_data.value.get("$169", [])

        metadata = self.fragments.get("$258", first=True)
        return [] if metadata is None else metadata.value.get("$169", [])

    def reading_order_names(self):
        return [
            reading_order.get("$178", "") for reading_order in self.get_reading_orders()
        ]

    def ordered_section_names(self):
        section_names = []

        for reading_order in self.get_reading_orders():
            section_names.extend(reading_order.get("$170", []))

        return section_names

    def extract_section_story_names(self, section_name):
        story_names = []

        def _extract_story_names(data):
            data_type = ion_type(data)

            if data_type is IonAnnotation:
                _extract_story_names(data.value)

            elif data_type is IonList or data_type is IonSExp:
                for fc in data:
                    _extract_story_names(fc)

            elif data_type is IonStruct:
                for fk, fv in data.items():
                    if fk == "$176":
                        if fv not in story_names:
                            story_names.append(fv)
                    else:
                        _extract_story_names(fv)

        _extract_story_names(
            self.fragments[YJFragmentKey(ftype="$260", fid=section_name)]
        )
        return story_names

    def log_known_error(self, msg):
        if REPORT_KNOWN_PROBLEMS:
            log.error(msg)
        elif REPORT_KNOWN_PROBLEMS is not None:
            log.warning(msg)

    def log_error_once(self, msg):
        if msg not in self.reported_errors:
            log.error(msg)
            self.reported_errors.add(msg)
