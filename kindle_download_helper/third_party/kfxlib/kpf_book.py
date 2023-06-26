from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import decimal
import re
import uuid

from .ion import (
    IS,
    IonAnnotation,
    IonFloat,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    ion_type,
    isstring,
    unannotated,
)
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import font_file_ext
from .yj_container import YJFragment, YJFragmentKey
from .yj_structure import EID_REFERENCES, FORMAT_SYMBOLS, MAX_CONTENT_FRAGMENT_SIZE
from .yj_versions import GENERIC_CREATOR_VERSIONS, is_known_aux_metadata

if IS_PYTHON2:
    from .python_transition import str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


FIX_BOOK = True
CREATE_CONTENT_FRAGMENTS = True
VERIFY_ORIGINAL_POSITION_MAP = False


SHORT_TOOL_NAME = {
    "Kindle Previewer 3": "KPR",
    "Kindle Create": "KC",
}


class KpfBook(object):
    def fix_kpf_prepub_book(self, fix_book, retain_yj_locals):
        self.retain_yj_locals = retain_yj_locals

        if len(self.yj_containers) != 1:
            raise Exception("A KPF book should have only one container")

        self.kpf_container = self.yj_containers[0]

        if not (fix_book and FIX_BOOK):
            return

        for fragment in self.fragments.get_all("$417"):
            orig_fid = fragment.fid
            fixed_fid = fix_resource_location(orig_fid)
            if fixed_fid != orig_fid:
                self.fragments.remove(fragment)
                self.fragments.append(
                    YJFragment(
                        ftype="$417",
                        fid=self.create_local_symbol(fixed_fid),
                        value=fragment.value,
                    )
                )

        for fragment in list(self.fragments):
            if fragment.ftype != "$270":
                self.kpf_fix_fragment(fragment)

        for fragment in self.fragments.get_all("$266"):
            if fragment.value.get("$183", {}).get("$143", None) == 0:
                fragment.value["$183"].pop("$143")

        fragment = self.fragments.get("$550")
        if fragment is not None:
            for lm in fragment.value:
                lm.pop("$178", None)

        fragment = self.fragments.get("$490")
        if fragment is not None:
            for category in ["kindle_audit_metadata", "kindle_title_metadata"]:
                for cm in fragment.value["$491"]:
                    if cm["$495"] == category:
                        break
                else:
                    fragment.value["$491"].append(
                        IonStruct(IS("$495"), category, IS("$258"), [])
                    )

            for cm in fragment.value["$491"]:
                if cm["$495"] == "kindle_audit_metadata":
                    if (
                        (
                            self.get_metadata_value(
                                "file_creator", category="kindle_audit_metadata"
                            ),
                            self.get_metadata_value(
                                "creator_version", category="kindle_audit_metadata"
                            ),
                        )
                        in GENERIC_CREATOR_VERSIONS
                    ) and self.kpf_container.kcb_data:
                        kcb_metadata = self.kpf_container.kcb_data.get("metadata", {})
                        tool_name = kcb_metadata.get("tool_name")
                        tool_version = kcb_metadata.get("tool_version")

                        if (
                            tool_name
                            and tool_version
                            and not tool_version.startswith("unknown")
                        ):
                            for metadata in cm["$258"]:
                                if metadata["$492"] == "file_creator":
                                    metadata["$307"] = SHORT_TOOL_NAME.get(
                                        tool_name, tool_name
                                    )

                                if metadata["$492"] == "creator_version":
                                    metadata["$307"] = tool_version

                elif cm["$495"] == "kindle_title_metadata":
                    if self.get_metadata_value("asset_id") is None:
                        cm["$258"].append(
                            IonStruct(
                                IS("$492"),
                                "asset_id",
                                IS("$307"),
                                self.create_container_id(),
                            )
                        )

                    if self.get_metadata_value("is_sample") is None:
                        cm["$258"].append(
                            IonStruct(IS("$492"), "is_sample", IS("$307"), False)
                        )

                    if (
                        self.get_metadata_value("language", default="")
                        .lower()
                        .startswith("ja-zh")
                    ):
                        for metadata in cm["$258"]:
                            if metadata["$492"] == "language":
                                metadata["$307"] = metadata["$307"][3:].replace(
                                    "=", "-"
                                )

                    if (
                        self.kpf_container.source_epub is not None
                        and len(self.kpf_container.source_epub.authors) > 1
                    ):
                        for i, md in reversed(list(enumerate(cm["$258"]))):
                            if md["$492"] == "author":
                                cm["$258"].pop(i)

                        for author in self.kpf_container.source_epub.authors:
                            cm["$258"].append(
                                IonStruct(IS("$492"), "author", IS("$307"), author)
                            )

                        if (
                            self.kpf_container.source_epub.issue_date
                            and self.get_metadata_value("issue_date") is None
                        ):
                            cm["$258"].append(
                                IonStruct(
                                    IS("$492"),
                                    "issue_date",
                                    IS("$307"),
                                    self.kpf_container.source_epub.issue_date,
                                )
                            )

                    if self.get_metadata_value("override_kindle_font") is None:
                        cm["$258"].append(
                            IonStruct(
                                IS("$492"), "override_kindle_font", IS("$307"), False
                            )
                        )

                    if (
                        self.get_metadata_value("cover_image") is None
                        and self.get_metadata_value(
                            "yj_fixed_layout", category="kindle_capability_metadata"
                        )
                        is not None
                    ):
                        cover_resource = self.locate_cover_image_resource_from_content()
                        if cover_resource is not None:
                            cm["$258"].append(
                                IonStruct(
                                    IS("$492"),
                                    "cover_image",
                                    IS("$307"),
                                    str(cover_resource),
                                )
                            )

        for fragment in self.fragments.get_all("$262"):
            if fragment.fid != "$262":
                self.fragments.remove(fragment)
                self.fragments.append(YJFragment(ftype="$262", value=fragment.value))

            location = fragment.value["$165"]
            font_data_fragment = self.fragments[
                YJFragmentKey(ftype="$417", fid=location)
            ]
            self.fragments.remove(font_data_fragment)
            self.fragments.append(
                YJFragment(
                    ftype="$418",
                    fid=self.create_local_symbol(location),
                    value=font_data_fragment.value,
                )
            )

        for fragment in self.fragments.get_all("$164"):
            fv = fragment.value
            if (
                fv.get("$161") == "$287"
                and "$422" not in fv
                and "$423" not in fv
                and "$167" in fv
            ):
                referred_resources = fv["$167"]
                for frag in self.fragments.get_all("$164"):
                    if (
                        frag.fid in referred_resources
                        and "$422" in frag.value
                        and "$423" in frag.value
                    ):
                        fv[IS("$422")] = frag.value["$422"]
                        fv[IS("$423")] = frag.value["$423"]
                        break

            if fv.get("$162") == "":
                fv.pop("$162")
                log.warning(
                    "Removed empty mime type from external_resource %s" % fv.get("$175")
                )

        cover_image_data = self.get_cover_image_data()
        if cover_image_data is not None:
            new_cover_image_data = self.fix_cover_image_data(cover_image_data)
            if new_cover_image_data != cover_image_data:
                self.set_cover_image_data(new_cover_image_data)

        canonical_format = (2, 0) if self.is_illustrated_layout else (1, 0)

        file_creator = self.get_metadata_value(
            "file_creator", category="kindle_audit_metadata", default=""
        )
        creator_version = self.get_metadata_value(
            "creator_version", category="kindle_audit_metadata", default=""
        )

        if (
            file_creator == "KC"
            or (file_creator == "KTC" and creator_version >= "1.11")
        ) and canonical_format < (2, 0):
            canonical_format = (2, 0)

        content_features = self.fragments.get("$585")
        if content_features is not None:
            content_features.value.pop("$155", None)
            content_features.value.pop("$598", None)
        else:
            content_features = YJFragment(ftype="$585", value=IonStruct(IS("$590"), []))
            self.fragments.append(content_features)

        features = content_features.value["$590"]

        def add_feature(feature, namespace="com.amazon.yjconversion", version=(1, 0)):
            if self.get_feature_value(feature, namespace=namespace) is None:
                features.append(
                    IonStruct(
                        IS("$586"),
                        namespace,
                        IS("$492"),
                        feature,
                        IS("$589"),
                        IonStruct(
                            IS("version"),
                            IonStruct(IS("$587"), version[0], IS("$588"), version[1]),
                        ),
                    )
                )

        def add_feature_from_metadata(
            metadata,
            feature,
            category="kindle_capability_metadata",
            namespace="com.amazon.yjconversion",
            version=(1, 0),
        ):
            if self.get_metadata_value(metadata, category=category) is not None:
                add_feature(feature, namespace, version)

        add_feature("CanonicalFormat", namespace="SDK.Marker", version=canonical_format)

        if self.is_fixed_layout:
            if self.has_pdf_resource:
                add_feature("yj_pdf_support")
                add_feature_from_metadata("yj_fixed_layout", "yj_fixed_layout")
            else:
                add_feature_from_metadata(
                    "yj_fixed_layout", "yj_non_pdf_fixed_layout", version=2
                )

        has_hdv_image = has_tiles = yj_jpg_rst_marker_present = False
        for fragment in self.fragments.get_all("$164"):
            fv = fragment.value
            if fv.get("$422", 0) > 1920 or fv.get("$423", 0) > 1920 or "$636" in fv:
                has_hdv_image = True

            if IS("$797") in fv:
                has_tiles = True

            if (not yj_jpg_rst_marker_present) and fv.get("$161") == "$285":
                location = fv.get("$165", None)
                if location is not None:
                    raw_media = self.fragments.get(
                        ftype="$417", fid=location, first=True
                    )
                    if raw_media is not None:
                        if re.search(b"\xff[\xd0-\xd7]", raw_media.value.tobytes()):
                            yj_jpg_rst_marker_present = True

        if not self.is_fixed_layout:
            if has_tiles:
                add_feature("yj_hdv", (2, 0))
            elif has_hdv_image:
                add_feature("yj_hdv")

        if yj_jpg_rst_marker_present:
            add_feature("yj_jpg_rst_marker_present")

        add_feature_from_metadata("graphical_highlights", "yj_graphical_highlights")
        add_feature_from_metadata("yj_textbook", "yj_textbook")

        if self.fragments.get("$389") is None:
            log.info("Adding book_navigation")

            book_navigation = []
            for reading_order_name in self.reading_order_names():
                book_nav = IonStruct()

                if reading_order_name:
                    book_nav[IS("$178")] = reading_order_name

                book_nav[IS("$392")] = []
                book_navigation.append(book_nav)

            self.fragments.append(YJFragment(ftype="$389", value=book_navigation))

        for book_navigation in self.fragments["$389"].value:
            pages = []
            nav_containers = book_navigation["$392"]
            has_page_list = False

            for nav_container in nav_containers:
                nav_container = unannotated(nav_container)
                nav_type = nav_container.get("$235", None)
                if nav_type == "$236":
                    entries = nav_container.get("$247", [])
                    i = 0
                    while i < len(entries):
                        entry = unannotated(entries[i])
                        label = entry.get("$241", {}).get("$244", "")
                        if label.startswith("page_list_entry:"):
                            seq, sep, text = label.partition(":")[2].partition(":")

                            pages.append(
                                (
                                    int(seq),
                                    IonAnnotation(
                                        [IS("$393")],
                                        IonStruct(
                                            IS("$241"),
                                            IonStruct(IS("$244"), text),
                                            IS("$246"),
                                            entry["$246"],
                                        ),
                                    ),
                                )
                            )

                            entries.pop(i)
                            i -= 1

                        i += 1
                elif nav_type == "$237":
                    log.info("KPF book contains a page list")
                    has_page_list = True

            if pages and not has_page_list:
                log.info(
                    "Transformed %d KFX landmark entries into a page list" % len(pages)
                )

                nav_containers.append(
                    IonAnnotation(
                        [IS("$391")],
                        IonStruct(
                            IS("$235"),
                            IS("$237"),
                            IS("$239"),
                            self.kpf_gen_uuid_symbol(),
                            IS("$247"),
                            [p[1] for p in sorted(pages)],
                        ),
                    )
                )

        if self.is_dictionary:
            self.is_kpf_prepub = False
        else:
            has_text_block = False
            if CREATE_CONTENT_FRAGMENTS:
                content_fragment_data = {}
                for section_name in self.ordered_section_names():
                    for story_name in self.extract_section_story_names(section_name):
                        self.kpf_collect_content_strings(
                            story_name, content_fragment_data
                        )

                for content_name, content_list in content_fragment_data.items():
                    has_text_block = True
                    self.fragments.append(
                        YJFragment(
                            ftype="$145",
                            fid=content_name,
                            value=IonStruct(
                                IS("name"), content_name, IS("$146"), content_list
                            ),
                        )
                    )
            else:
                log.warning("Content fragment creation is disabled")

            map_pos_info = self.collect_position_map_info()

            if VERIFY_ORIGINAL_POSITION_MAP:
                content_pos_info = self.collect_content_position_info()
                self.verify_position_info(content_pos_info, map_pos_info)

            if len(map_pos_info) < 10 and self.is_illustrated_layout:
                log.warning("creating position map (original is missing or incorrect)")
                map_pos_info = self.collect_content_position_info()

            self.is_kpf_prepub = False
            has_spim, has_position_id_offset = self.create_position_map(map_pos_info)

            has_yj_location_pid_map = False
            if self.fragments.get("$550") is None and not (
                self.is_print_replica or self.is_magazine
            ):
                loc_info = self.generate_approximate_locations(map_pos_info)
                has_yj_location_pid_map = self.create_location_map(loc_info)

            if self.fragments.get("$395") is None:
                self.fragments.append(
                    YJFragment(ftype="$395", value=IonStruct(IS("$247"), []))
                )

            for fragment in self.fragments.get_all("$593"):
                self.fragments.remove(fragment)

            fc = []

            if has_spim or has_yj_location_pid_map:
                fc.append(
                    IonStruct(IS("$492"), "kfxgen.positionMaps", IS("version"), 2)
                )

            if has_position_id_offset:
                fc.append(
                    IonStruct(IS("$492"), "kfxgen.pidMapWithOffset", IS("version"), 1)
                )

            if has_text_block:
                fc.append(IonStruct(IS("$492"), "kfxgen.textBlock", IS("version"), 1))

            self.fragments.append(YJFragment(ftype="$593", value=fc))

        for fragment in self.fragments.get_all("$597"):
            for kv in fragment.value.get("$258", []):
                key = kv.get("$492", "")
                value = kv.get("$307", "")
                if not is_known_aux_metadata(key, value):
                    log.warning("Unknown auxiliary_data: %s=%s" % (key, value))

        self.check_fragment_usage(rebuild=True, ignore_extra=True)

        self.check_symbol_table(rebuild=True, ignore_unused=True)

    def kpf_gen_uuid_symbol(self):
        return self.create_local_symbol(str(uuid.uuid4()))

    def kpf_fix_fragment(self, fragment):
        def _fix_ion_data(data, container):
            data_type = ion_type(data)

            if data_type is IonAnnotation:
                if data.is_annotation("$608"):
                    return _fix_ion_data(data.value, container)

                new_annot = [_fix_ion_data(annot, None) for annot in data.annotations]
                return IonAnnotation(new_annot, _fix_ion_data(data.value, container))

            if data_type is IonList:
                new_list = []
                for i, fc in enumerate(data):
                    if container == "$146" and isinstance(fc, IonSymbol):
                        structure = self.fragments.get(
                            YJFragmentKey(ftype="$608", fid=fc)
                        )
                        if structure is not None:
                            fc = copy.deepcopy(structure.value)

                    if (not self.is_dictionary) and (
                        (
                            fragment.ftype == "$609"
                            and container == "contains_list_"
                            and i == 1
                        )
                        or (
                            fragment.ftype == "$538"
                            and container == "yj.semantics.containers_with_semantics"
                        )
                    ):
                        fc = self.symbol_id(fc)

                    if container == "$181":
                        list_container = "contains_list_"
                    elif container == "$141":
                        list_container = "$141"
                    else:
                        list_container = None

                    new_list.append(_fix_ion_data(fc, list_container))

                return new_list

            if data_type is IonSExp:
                new_sexp = IonSExp()
                for fc in data:
                    new_sexp.append(_fix_ion_data(fc, None))

                return new_sexp

            if data_type is IonStruct:
                new_struct = IonStruct()
                for fk, fv in data.items():
                    fv = _fix_ion_data(fv, fk)

                    if not self.is_dictionary:
                        if fk == "$597":
                            continue

                        if fk == "$239":
                            self.create_local_symbol(str(fv))

                        if (
                            fk in EID_REFERENCES
                            and fragment.ftype != "$597"
                            and isinstance(fv, IonSymbol)
                        ):
                            if fk == "$598":
                                fk = IS("$155")

                            if (
                                fragment.ftype != "$610"
                                or self.fragments.get(ftype="$260", fid=fv) is None
                            ):
                                fv = self.symbol_id(fv)

                    if fk == "$161" and isstring(fv):
                        fv = IS(FORMAT_SYMBOLS[fv])

                    if (not self.retain_yj_locals) and (
                        fk.startswith("yj.authoring.")
                        or fk.startswith("yj.conversion.")
                        or fk.startswith("yj.print.")
                        or fk.startswith("yj.semantics.")
                        or fk == "$790"
                    ):
                        continue

                    if (
                        self.is_illustrated_layout
                        and fragment.ftype == "$260"
                        and container == "$141"
                        and fk in ["$67", "$66"]
                    ):
                        continue

                    if fk == "$165":
                        if ion_type(fv) is not IonString:
                            raise Exception("location is not IonString: %s" % fv)

                        fv = fix_resource_location(fv)

                    if fragment.ftype == "$157" and fk == "$173" and fv != fragment.fid:
                        log.info(
                            "Fixing incorrect name %s of style %s" % (fv, fragment.fid)
                        )
                        fv = fragment.fid

                    new_struct[_fix_ion_data(fk, None)] = fv

                return new_struct

            if data_type is IonFloat:
                dec = decimal.Decimal("%g" % data)
                if abs(dec) < 0.001:
                    dec = decimal.Decimal("0")

                return dec

            return data

        fragment.value = _fix_ion_data(fragment.value, None)

    def kpf_collect_content_strings(self, story_name, content_fragment_data):
        def _kpf_collect_content_strings(data):
            data_type = ion_type(data)

            if data_type is IonAnnotation:
                _kpf_collect_content_strings(data.value)

            elif data_type is IonList or data_type is IonSExp:
                for fc in data:
                    _kpf_collect_content_strings(fc)

            elif data_type is IonStruct:
                for fk, fv in data.items():
                    if fk == "$145" and isstring(fv):
                        if (
                            len(content_fragment_data) == 0
                            or self._content_fragment_size >= MAX_CONTENT_FRAGMENT_SIZE
                        ):
                            self._content_fragment_name = self.create_local_symbol(
                                "content_%d" % (len(content_fragment_data) + 1)
                            )
                            content_fragment_data[self._content_fragment_name] = []
                            self._content_fragment_size = 0

                        content_fragment_data[self._content_fragment_name].append(fv)
                        self._content_fragment_size += len(fv.encode("utf8"))

                        data[fk] = IonStruct(
                            IS("name"),
                            self._content_fragment_name,
                            IS("$403"),
                            len(content_fragment_data[self._content_fragment_name]) - 1,
                        )
                    else:
                        _kpf_collect_content_strings(fv)

        _kpf_collect_content_strings(
            self.fragments[YJFragmentKey(ftype="$259", fid=story_name)].value
        )

    def symbol_id(self, symbol):
        if symbol is None or isinstance(symbol, int):
            return symbol

        return self.symtab.get_id(symbol)

    def kpf_add_font_ext(self, filename, raw_font):
        ext = font_file_ext(raw_font)
        if not ext:
            log.warn("font %s has unknown type (possibly obfuscated)" % filename)

        return "%s%s" % (filename, ext)


def section_sort_key(reading_order, s):
    try:
        return (reading_order.index(s), s)
    except ValueError:
        return (len(reading_order), s)


def fix_resource_location(s):
    return s if s.startswith("resource/") else "resource/%s" % s
