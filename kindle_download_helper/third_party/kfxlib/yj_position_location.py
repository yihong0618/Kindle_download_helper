from __future__ import absolute_import, division, print_function, unicode_literals

import collections

from .ion import (
    IS,
    IonAnnotation,
    IonInt,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    ion_type,
    unannotated,
)
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import list_symbols, natural_sort_key, truncate_list, unicode_len
from .yj_container import YJFragment, YJFragmentKey
from .yj_structure import APPROXIMATE_PAGE_LIST

if IS_PYTHON2:
    from .python_transition import repr, str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


REPORT_POSITION_DATA = False
REPORT_LOCATION_DATA = False
MAX_REPORT_ERRORS = 0

KFX_POSITIONS_PER_LOCATION = 110

TYPICAL_POSITIONS_PER_PAGE = 1850
MIN_POSITIONS_PER_PAGE = 1
MAX_POSITIONS_PER_PAGE = 50000
GEN_COVER_PAGE_NUMBER = True
MAX_WHITE_SPACE_ADJUST = 50
DEBUG_PAGES = False


class ContentChunk(object):
    def __init__(
        self,
        pid,
        eid,
        eid_offset,
        length=0,
        section_name=None,
        match_zero_len=False,
        text=None,
        image_resource=None,
    ):
        self.pid = pid
        self.eid = eid
        self.eid_offset = eid_offset
        self.length = length
        self.section_name = section_name
        self.match_zero_len = match_zero_len
        self.text = text
        self.image_resource = image_resource

        if (
            pid < 0
            or (isinstance(eid, int) and eid <= 0)
            or eid_offset < 0
            or length < 0
            or (text is not None and len(text) != length)
        ):
            log.error("bad ContentChunk: %s" % repr(self))

    def __eq__(self, other, compare_pids=True):
        if not isinstance(other.eid, type(self.eid)):
            return False

        if self.pid == other.pid or not compare_pids:
            if (
                self.eid == other.eid
                and self.eid_offset == other.eid_offset
                and self.section_name == other.section_name
            ):
                if (
                    self.length == other.length
                    or (self.match_zero_len and other.length == 0)
                    or (other.match_zero_len and self.length == 0)
                ):
                    return True

        return False

    def __repr__(self):
        return "pid=%s eid=%s%s len=%s%s sect=%s text=%s img=%s" % (
            self.pid,
            self.eid,
            "+" + "%d" % self.eid_offset if self.eid_offset else "",
            self.length,
            "*" if self.match_zero_len else "",
            self.section_name,
            repr(self.text),
            repr(self.image_resource),
        )


class ConditionalTemplate(object):
    def __init__(self, end_eid, end_eid_offset, oper, pos_info):
        self.end_eid = end_eid
        self.end_eid_offset = end_eid_offset
        self.oper = oper
        self.pos_info = pos_info
        self.use_next = False

        if self.oper not in ["$298", "$299"]:
            self.start_eid = end_eid
            self.start_eid_offset = end_eid_offset
        else:
            self.start_eid = self.start_eid_offset = None

    def __repr__(self):
        if self.oper not in ["$298", "$299"]:
            return "%s%s+%s (%s)" % (
                self.oper,
                self.end_eid,
                self.end_eid_offset,
                " ".join([str(x.eid) for x in self.pos_info]),
            )

        return "%s+%s%s%s+%s(%s)" % (
            self.start_eid,
            self.start_eid_offset,
            self.oper,
            self.end_eid,
            self.end_eid_offset,
            " ".join([str(x.eid) for x in self.pos_info]),
        )


class MatchReport(object):
    def __init__(self, no_limit=False):
        self.count = 0
        self.limit = 0 if no_limit else MAX_REPORT_ERRORS

    def report(self, msg):
        if (not self.limit) or self.count < self.limit:
            log.warning(msg)

        self.count += 1

    def final(self):
        if self.limit and self.count > self.limit:
            self.logger("Mismatch report limit exceeded, %d total errors" % self.count)


class BookPosLoc(object):
    def check_position_and_location_maps(self):
        content_pos_info = self.collect_content_position_info()
        map_pos_info = self.collect_position_map_info()

        if not self.is_kfx_v1:
            self.verify_position_info(content_pos_info, map_pos_info)

        self.collect_location_map_info(map_pos_info)

        section_lengths = collections.defaultdict(int)
        for chunk in map_pos_info:
            section_lengths[chunk.section_name] += chunk.length

        if section_lengths and not self.is_sample:
            max_section_pid_count = max(section_lengths.values())
            reflow_section_size_calculated = (
                min(((max_section_pid_count - 65536) // (16 * 1024)) + 2, 256)
                if max_section_pid_count > 65536
                else 1
            )
            reflow_section_size = self.get_feature_value(
                "reflow-section-size", default=1
            )

            if abs(reflow_section_size - reflow_section_size_calculated) > 1 + (
                reflow_section_size_calculated // 50
            ):
                if not (
                    self.get_metadata_value(
                        "file_creator", category="kindle_audit_metadata"
                    )
                    == "KC"
                    and reflow_section_size > reflow_section_size_calculated
                ):
                    log.warning(
                        "Feature/content mismatch: reflow-section-size is %s, expected %s for max section pid count %d"
                        % (
                            reflow_section_size,
                            reflow_section_size_calculated,
                            max_section_pid_count,
                        )
                    )

    def collect_content_position_info(self):
        eid_section = {}
        eid_start_pos = {}
        pos_info = []
        section_pos_info = []
        eid_cond_info = []
        processed_story_names = set()
        self.cpi_pid_ = self.cpi_pid_for_offset_ = 0
        self.cpi_processing_story_ = False
        is_kpr3_21 = self.get_metadata_value(
            "file_creator", category="kindle_audit_metadata", default=""
        ) == "KPR" and natural_sort_key(
            self.get_metadata_value(
                "creator_version", category="kindle_audit_metadata", default=""
            )
        ) >= natural_sort_key(
            "3.21.0"
        )
        section_stories = collections.defaultdict(set)
        story_sections = collections.defaultdict(set)
        section_names = self.ordered_section_names()

        def collect_section_position_info(section_name):
            pending_story_names = []

            def extract_position_data(
                data, current_eid, content_key, list_index, list_max, advance
            ):
                def have_content(
                    eid,
                    length,
                    advance_,
                    allow_zero=True,
                    match_zero_len=False,
                    text=None,
                    image_resource=None,
                ):
                    if eid is None:
                        return

                    if eid not in eid_start_pos:
                        eid_start_pos[eid] = self.cpi_pid_for_offset_

                    eid_offset = self.cpi_pid_for_offset_ - eid_start_pos[eid]

                    if advance_:
                        self.cpi_pid_for_offset_ += length

                    if section_pos_info and section_pos_info[-1].eid == eid:
                        last_chunk = section_pos_info.pop(-1)

                        self.cpi_pid_ += length
                        eid_offset += length
                        length += last_chunk.length

                        if last_chunk.text is not None or text is not None:
                            text = (last_chunk.text or "") + (text or "")

                        section_pos_info.append(
                            ContentChunk(
                                last_chunk.pid,
                                last_chunk.eid,
                                last_chunk.eid_offset,
                                length,
                                last_chunk.section_name,
                                match_zero_len=last_chunk.match_zero_len,
                                text=last_chunk.text,
                                image_resource=last_chunk.image_resource,
                            )
                        )

                        if length == 0 or not allow_zero:
                            return

                        length = 0
                        text = None

                    section_pos_info.append(
                        ContentChunk(
                            self.cpi_pid_,
                            eid,
                            eid_offset,
                            length,
                            eid_section[eid],
                            match_zero_len=match_zero_len,
                            text=text,
                            image_resource=image_resource,
                        )
                    )
                    self.cpi_pid_ += length

                data_type = ion_type(data)

                if data_type is IonAnnotation:
                    extract_position_data(
                        data.value,
                        current_eid,
                        content_key,
                        list_index,
                        list_max,
                        advance,
                    )

                elif data_type is IonList:
                    for i, fc in enumerate(data):
                        if content_key in {"$146", "$274"} and self.is_kpf_prepub:
                            if ion_type(fc) is IonSymbol:
                                fc = self.fragments.get(
                                    YJFragmentKey(ftype="$608", fid=fc)
                                )

                        if fc is not None:
                            extract_position_data(
                                fc, current_eid, content_key, i, len(data) - 1, advance
                            )

                elif data_type is IonSExp:
                    for fc in data:
                        extract_position_data(
                            fc, current_eid, content_key, None, None, advance
                        )

                elif data_type is IonStruct:
                    if content_key != "$259":
                        eid = data.get("$155") or data.get("$598")
                        if eid is not None:
                            parent_eid = current_eid
                            current_eid = eid
                            if current_eid in eid_section:
                                if eid_section[current_eid] == section_name:
                                    log.error(
                                        "duplicate eid %s in section %s"
                                        % (current_eid, section_name)
                                    )
                                else:
                                    log.error(
                                        "duplicate eid %s in sections %s and %s"
                                        % (
                                            current_eid,
                                            eid_section[current_eid],
                                            section_name,
                                        )
                                    )

                            eid_section[current_eid] = section_name
                        else:
                            parent_eid = None

                    annot_type = data.get("$687")
                    typ = data.get("$159")

                    if (
                        typ in ["$270", "$271", "$269"]
                        and (
                            parent_eid is not None
                            and content_key == "$146"
                            and data.get("$601") == "$283"
                        )
                        and list_index is not None
                    ):
                        have_content(parent_eid, -1 if list_index == 0 else 0, advance)

                    save_cpi_pid_for_offset = self.cpi_pid_for_offset_

                    if typ in ["$596", "$271", "$272", "$274"]:
                        have_content(
                            current_eid,
                            1,
                            advance,
                            image_resource=data.get("$175") if typ == "$271" else None,
                        )
                    elif typ in ["$270", "$277", "$269", "$151"]:
                        for ct in ["$145", "$146", "$176"]:
                            if ct in data:
                                break
                        else:
                            have_content(
                                current_eid,
                                1,
                                advance,
                                match_zero_len=is_kpr3_21 and typ == "$269",
                            )

                    if "$141" in data:
                        if True:
                            for pt in data["$141"]:
                                extract_position_data(
                                    pt, current_eid, "$141", None, None, advance
                                )

                    if "$146" in data and typ not in ["$274", "$272"]:
                        have_content(
                            current_eid,
                            1,
                            advance and data.get("$615") not in ["$688", "$689"],
                        )

                    if "$145" in data and annot_type not in ["$584", "$690"]:
                        fv = data["$145"]
                        if ion_type(fv) is IonStruct:
                            content = self.fragments[
                                YJFragmentKey(ftype="$145", fid=fv["name"])
                            ].value["$146"][fv["$403"]]
                            have_content(
                                current_eid, unicode_len(content), advance, text=content
                            )

                    if "$683" in data:
                        extract_position_data(
                            data["$683"], current_eid, "$683", None, None, advance
                        )

                    if "$749" in data:
                        extract_position_data(
                            self.fragments[
                                YJFragmentKey(ftype="$259", fid=data["$749"])
                            ],
                            None,
                            "$259",
                            None,
                            None,
                            advance,
                        )

                    if "$146" in data:
                        if typ == "$274":
                            extract_position_data(
                                data["$146"], current_eid, typ, None, None, advance
                            )
                        elif typ == "$272":
                            extract_position_data(
                                data["$146"], None, "$146", None, None, False
                            )
                        else:
                            extract_position_data(
                                data["$146"], current_eid, "$146", None, None, advance
                            )

                    if "$145" in data and annot_type not in ["$584", "$690"]:
                        fv = data["$145"]
                        if ion_type(fv) is not IonStruct:
                            extract_position_data(
                                fv, current_eid, "$145", None, None, advance
                            )

                    if "$176" in data and content_key != "$259":
                        have_content(current_eid, 1, advance)

                        fv = data["$176"]
                        section_stories[section_name].add(fv)
                        story_sections[fv].add(section_name)

                        if self.is_conditional_structure:
                            if fv not in pending_story_names:
                                pending_story_names.append(fv)
                        else:
                            if fv not in processed_story_names:
                                extract_position_data(
                                    self.fragments[YJFragmentKey(ftype="$259", fid=fv)],
                                    None,
                                    "$259",
                                    None,
                                    None,
                                    advance,
                                )
                                processed_story_names.add(fv)

                    for fk, fv in data.items():
                        if ion_type(fv) != IonString and fk not in {
                            "$749",
                            "$584",
                            "$683",
                            "$145",
                            "$146",
                            "$141",
                            "$702",
                            "$250",
                            "$176",
                            "yj.dictionary.term",
                            "yj.dictionary.unnormalized_term",
                        }:
                            extract_position_data(
                                fv, current_eid, fk, None, None, advance
                            )

                    if (
                        typ != "$271"
                        and data.get("$601") == "$283"
                        and self.cpi_pid_for_offset_ > save_cpi_pid_for_offset + 1
                    ):
                        self.cpi_pid_for_offset_ = save_cpi_pid_for_offset + 1

                elif data_type is IonString:
                    length = unicode_len(data)
                    if content_key == "$146" and list_index == 0:
                        length -= 1

                    have_content(
                        current_eid,
                        length,
                        advance,
                        allow_zero=list_index is not None and list_index < list_max,
                        text=data,
                    )

            extract_position_data(
                self.fragments[YJFragmentKey(ftype="$260", fid=section_name)],
                None,
                "$260",
                None,
                None,
                True,
            )

            for story_name in pending_story_names:
                if story_name not in processed_story_names:
                    self.cpi_processing_story_ = True
                    self.cpi_fixed_ = False
                    extract_position_data(
                        self.fragments[YJFragmentKey(ftype="$259", fid=story_name)],
                        None,
                        "$259",
                        None,
                        None,
                        True,
                    )
                    self.cpi_processing_story_ = False
                    processed_story_names.add(story_name)
                else:
                    log.error("story %s appears in multiple sections" % story_name)

            for ci in eid_cond_info:
                if ci.pos_info:
                    log.error("left over conditional template info: %s" % ci)

            del eid_cond_info[:]

            pos_info.extend(section_pos_info)
            del section_pos_info[:]

        for section_name in section_names:
            collect_section_position_info(section_name)

        for section_name, stories in section_stories.items():
            if not (len(stories) == 1 or (len(stories) == 2 and self.is_print_replica)):
                log.error(
                    "section %s has stories %s" % (section_name, list_symbols(stories))
                )

        for story, section_names in story_sections.items():
            if len(section_names) != 1:
                log.error(
                    "story %s is in sections %s" % (story, list_symbols(section_names))
                )

        return pos_info

    def anchor_eid_offset(self, anchor):
        fragment = self.fragments.get(ftype="$266", fid=anchor)
        if fragment is not None and "$183" in fragment.value:
            position = fragment.value["$183"]
            return (position["$155"], position.get("$143", 0))

        log.error("Failed to locate position for anchor: %s" % anchor)
        return None

    def has_non_image_render_inline(self):
        if not hasattr(self, "_cached_has_non_image_render_inline"):

            def walk(data):
                data_type = ion_type(data)

                if data_type is IonAnnotation:
                    if walk(data.value):
                        return True

                elif data_type is IonList or data_type is IonSExp:
                    for val in data:
                        if walk(val):
                            return True

                elif data_type is IonStruct:
                    if data.get("$159") != "$271" and data.get("$601") == "$283":
                        return True

                    for val in data.values():
                        if walk(val):
                            return True

                return False

            for fragment in self.fragments:
                if fragment.ftype in ["$259", "$608"]:
                    if walk(fragment.value):
                        self._cached_has_non_image_render_inline = True
                        break
            else:
                self._cached_has_non_image_render_inline = False

        return self._cached_has_non_image_render_inline

    def collect_position_map_info(self):
        pos_info = []
        eid_start_pos = {}
        prev_eid_offset = {}
        eid_section = {}
        has_mathml = self.get_feature_value("yj_mathml") is not None
        self._has_eid_offset = False
        section_names = self.ordered_section_names()

        def process_spim(
            contains,
            section_start_pid,
            section_name=None,
            add_section_length=None,
            verify_section_length=None,
            pid_is_really_len=False,
            one_based_pid=False,
            int_eid=True,
        ):
            if add_section_length is not None:
                contains = IonList(contains)
                contains.append([add_section_length + 1, 0])

            pid = eid = eid_offset = 0
            for i, pi in enumerate(contains):
                pi_type = ion_type(pi)
                if pi_type is IonList:
                    if len(pi) < 2 or len(pi) > 3:
                        log.error(
                            "Bad section_position_id_map list at %d: %s"
                            % (i, repr(fragment))
                        )
                        break

                    next_pid = pi[0]
                    next_eid = pi[1]
                    next_offset = pi[2] if len(pi) > 2 else 0
                elif pi_type is IonInt:
                    next_pid = pi
                    next_eid += 1
                    next_offset = 0
                elif pi_type is IonStruct:
                    extra_keys = set(pi.keys()) - {"$184", "$185", "$143"}
                    if extra_keys:
                        log.error(
                            "Bad section_position_id_map list keys %s at %d: %s"
                            % (list_symbols(extra_keys), i, repr(fragment))
                        )
                        break

                    next_pid = pi["$184"]
                    next_eid = pi["$185"]
                    next_offset = pi.get("$143", 0)
                else:
                    log.error(
                        "Bad section_position_id_map entry type at %d: %s"
                        % (i, repr(fragment))
                    )
                    break

                if pid_is_really_len:
                    next_pid += pid

                if one_based_pid:
                    next_pid -= 1

                if i > 0:
                    if section_name is not None:
                        if eid in eid_section and eid_section[eid] != section_name:
                            log.error(
                                "section_position_id_map eid %s expected in section %s found in %s"
                                % (eid, eid_section[eid], section_name)
                            )
                        eid_section[eid] = section_name

                    if eid_offset:
                        self._has_eid_offset = True

                    if eid not in eid_start_pos:
                        eid_start_pos[eid] = pid

                    if eid_offset != pid - eid_start_pos[eid]:
                        if (
                            self.is_conditional_structure
                            or has_mathml
                            or self.has_non_image_render_inline()
                        ):
                            if eid_offset <= prev_eid_offset.get(eid, -1):
                                log.error(
                                    "position_id_map eid %s offset is %d, expected > %d"
                                    % (eid, eid_offset, prev_eid_offset.get[eid])
                                )
                        else:
                            log.warning(
                                "position map eid %s offset is %d, expected %d"
                                % (eid, eid_offset, pid - eid_start_pos[eid])
                            )

                    pos_info.append(
                        ContentChunk(
                            pid + section_start_pid,
                            eid,
                            eid_offset,
                            next_pid - pid,
                            eid_section[eid] if section_name is None else section_name,
                        )
                    )
                    prev_eid_offset[eid] = eid_offset

                pid, eid, eid_offset = (
                    next_pid,
                    self.symbol_id(next_eid) if int_eid else next_eid,
                    next_offset,
                )

            if eid != 0 or eid_offset != 0:
                log.error(
                    "section_position_id_map last eid is %d+%d (should be zero)"
                    % (eid, eid_offset)
                )

            if verify_section_length is not None and pid != verify_section_length:
                log.error(
                    "section_position_id_map section %s length %d, expected %d"
                    % (section_name, pid, verify_section_length)
                )

        if self.is_dictionary or self.is_kpf_prepub:
            fragment = self.fragments.get("$611", first=True)
            if fragment is not None:
                section_pid_count = {}
                for sect_map in fragment.value["$181"]:
                    section_name = sect_map["$174"]
                    section_pid_count[section_name] = sect_map["$144"]

                section_start_pid = 0
                for section_name in section_names:
                    spim_fragment = self.fragments[
                        YJFragmentKey(ftype="$609", fid=str(section_name) + "-spm")
                    ]
                    if spim_fragment is None:
                        log.error(
                            "section_position_id_map missing for section %s"
                            % section_name
                        )
                        continue

                    spim = spim_fragment.value
                    spim_section_name = spim["$174"]
                    if spim_section_name != section_name:
                        log.error(
                            "section_position_id_map for section %s has section %s"
                            % (section_name, spim_section_name)
                        )

                    process_spim(
                        spim["$181"],
                        section_start_pid,
                        section_name,
                        add_section_length=section_pid_count[section_name],
                        one_based_pid=True,
                        int_eid=False,
                    )
                    section_start_pid += section_pid_count[section_name]

            esm_eids = set()
            for fragment in self.fragments.get_all("$610"):
                for esm in fragment.value["$181"]:
                    eid = esm["$185"]
                    section_name = esm["$174"]
                    if section_name in section_names and (
                        isinstance(eid, int) or eid != section_name
                    ):
                        esm_eids.add((eid, section_name))

            if esm_eids:
                spim_eids = set(eid_section.items())

                esm_missing = spim_eids - esm_eids
                if esm_missing:
                    log.warning(
                        "yj.eidhash_eid_section_map has %d eids, %d missing: %s"
                        % (
                            len(esm_eids),
                            len(esm_missing),
                            ", ".join(
                                truncate_list(
                                    ["%s/%s" % xx for xx in sorted(list(esm_missing))]
                                )
                            ),
                        )
                    )

                spim_missing = esm_eids - spim_eids
                if spim_missing:
                    log.warning(
                        "section_position_id_map has %d eids, %d missing: %s"
                        % (
                            len(spim_eids),
                            len(spim_missing),
                            ", ".join(
                                truncate_list(
                                    ["%s/%s" % xx for xx in sorted(list(spim_missing))]
                                )
                            ),
                        )
                    )

            for ftype in ["$264", "$265"]:
                if self.fragments.get(ftype, first=True):
                    log.error("Excess mapping fragment: %s" % ftype)
        else:
            fragment = self.fragments.get("$264", first=True)
            if fragment is not None:
                extra_sections = set()
                missing_sections = set(section_names)
                for pm in fragment.value:
                    section_name = pm["$174"]
                    if section_name not in missing_sections:
                        extra_sections.add(section_name)

                    missing_sections.discard(section_name)

                    for eid in pm["$181"]:
                        if ion_type(eid) is IonList:
                            for i in range(eid[1]):
                                eid_section[eid[0] + i] = section_name
                        else:
                            eid_section[eid] = section_name

                if extra_sections:
                    log.error(
                        "position_map has extra sections: %s"
                        % list_symbols(extra_sections)
                    )

                if missing_sections:
                    log.error(
                        "position_map has missing sections: %s"
                        % list_symbols(missing_sections)
                    )

            has_spim = False
            fragment = self.fragments.get("$265", first=True)
            if fragment is not None:
                if ion_type(fragment.value) is IonList:
                    process_spim(fragment.value, 0)
                else:
                    has_spim = True
                    book_pid = 0
                    for sect_map in fragment.value["$181"]:
                        section_name = sect_map["$174"]
                        section_start_pid = sect_map["$184"]

                        if section_start_pid != book_pid:
                            log.error(
                                "section %s start pid %d, expected %d"
                                % (section_name, section_start_pid, book_pid)
                            )

                        spim_fragment = self.fragments.get(
                            YJFragmentKey(ftype="$609", fid=section_name)
                        )
                        if spim_fragment is None:
                            log.error(
                                "section_position_id_map missing for section %s"
                                % section_name
                            )
                            continue

                        spim = spim_fragment.value
                        spim_section_name = spim["$174"]

                        if spim_section_name != section_name:
                            log.error(
                                "section_position_id_map for section %s has section %s"
                                % (section_name, spim_section_name)
                            )

                        section_length = sect_map["$144"]
                        process_spim(
                            spim["$181"],
                            section_start_pid,
                            section_name,
                            verify_section_length=section_length,
                            pid_is_really_len=True,
                        )
                        book_pid += section_length

                position_map_eids = set(eid_section.keys())
                position_id_map_eids = set(prev_eid_offset.keys())

                extra_eids = position_map_eids - position_id_map_eids
                if extra_eids:
                    log.error(
                        "position_map has extra eids: %s" % list_symbols(extra_eids)
                    )

                missing_eids = position_id_map_eids - position_map_eids
                if missing_eids:
                    log.error(
                        "position_map has missing eids: %s" % list_symbols(missing_eids)
                    )

            positionMaps_fc = self.get_feature_value(
                "kfxgen.positionMaps", namespace="format_capabilities"
            )
            if (positionMaps_fc == 2) is not has_spim:
                log.error(
                    "FC kfxgen.positionMaps=%s with section_position_id_map=%s"
                    % (positionMaps_fc, has_spim)
                )

            pidMapWithOffset_fc = self.get_feature_value(
                "kfxgen.pidMapWithOffset", namespace="format_capabilities"
            )
            if (pidMapWithOffset_fc == 1) is not self._has_eid_offset:
                log.error(
                    "FC kfxgen.pidMapWithOffset=%s with eid offset present=%s"
                    % (pidMapWithOffset_fc, self._has_eid_offset)
                )

            for ftype in ["$611", "$610"]:
                if self.fragments.get(ftype, first=True):
                    log.error("Excess mapping fragment: %s" % ftype)

        return pos_info

    def verify_position_info(self, content_pos_info, map_pos_info):
        class PosData(object):
            def __init__(self, pos_info, name):
                self.pos_info = pos_info
                self.name = name
                self.index = self.next_pid = 0

            def advance(self, extra=False):
                chunk = self.pos_info[self.index]

                if chunk.pid != self.next_pid:
                    if self.has_non_image_render_inline():
                        if chunk.pid > self.next_pid:
                            report.report(
                                "position_id %s expected pid %d <= idx=%d, chunk: %s"
                                % (self.name, self.next_pid, self.index, repr(chunk))
                            )
                    else:
                        report.report(
                            "position_id %s expected pid %d at idx=%d, chunk: %s"
                            % (self.name, self.next_pid, self.index, repr(chunk))
                        )

                if extra:
                    report.report(
                        "position_id %s extra at idx=%d, chunk: %s"
                        % (self.name, self.index, repr(chunk))
                    )

                self.next_pid = chunk.pid + chunk.length
                self.index += 1

            def chunk(self, add=0):
                return self.pos_info[self.index + add]

            def at_end(self, add=0):
                return self.index + add >= len(self.pos_info)

        content = PosData(content_pos_info, "content")
        map = PosData(map_pos_info, "map")
        report = MatchReport(REPORT_POSITION_DATA)
        compare_pids = True

        while not (map.at_end() and content.at_end()):
            if map.at_end():
                content.advance(True)
                continue

            if content.at_end():
                map.advance(True)
                continue

            if map.chunk().__eq__(content.chunk(), compare_pids=compare_pids):
                if REPORT_POSITION_DATA:
                    log.info(
                        "position_id at %sidx=%d %s%s"
                        % (
                            (
                                ("cidx=%d " % content.index)
                                if content.index != map.index
                                else ""
                            ),
                            map.index,
                            (
                                ("cpid=%d " % content.chunk().pid)
                                if content.chunk().pid != map.chunk().pid
                                else ""
                            ),
                            repr(map.chunk()),
                        )
                    )

                map.advance()
                content.advance()
                continue

            for n in range(1, 10):
                if (not map.at_end(n)) and map.chunk(n) == content.chunk():
                    for nn in range(n):
                        map.advance(True)
                    break

                if (not content.at_end(n)) and map.chunk() == content.chunk(n):
                    for nn in range(n):
                        content.advance(True)
                    break
            else:
                map.advance(True)
                content.advance(True)

        report.final()

    def create_position_map(self, pos_info):
        if self.is_dictionary or self.is_kpf_prepub:
            log.warning("Position map creation for KPF or dictionary not supported")

            for fragment in list(self.fragments):
                if fragment.ftype in ["$264", "$265", "$610"]:
                    self.fragments.remove(fragment)

            return (False, False)

        for ftype in ["$264", "$265", "$609", "$610", "$611"]:
            for fragment in self.fragments.get_all(ftype):
                self.fragments.remove(fragment)

        section_eids = collections.defaultdict(set)
        for chunk in pos_info:
            section_eids[chunk.section_name].add(chunk.eid)

        position_map = []

        for section_name in self.ordered_section_names():
            position_map.append(
                IonStruct(
                    IS("$181"),
                    IonList(section_eids[section_name]),
                    IS("$174"),
                    section_name,
                )
            )

        self.fragments.append(YJFragment(ftype="$264", value=position_map))

        position_id_map = []
        has_spim = False
        has_position_id_offset = False
        pid = 0

        for chunk in pos_info:
            position_id = IonStruct()
            position_id[IS("$184")] = pid
            position_id[IS("$185")] = self.symbol_id(chunk.eid)

            if chunk.eid_offset:
                position_id[IS("$143")] = chunk.eid_offset
                has_position_id_offset = True

            position_id_map.append(position_id)
            pid += chunk.length

        position_id_map.append(IonStruct(IS("$184"), pid, IS("$185"), 0))

        self.fragments.append(YJFragment(ftype="$265", value=position_id_map))

        return (has_spim, has_position_id_offset)

    def pid_for_eid(self, eid, eid_offset, pos_info):
        if not hasattr(self, "last_pii_"):
            self.last_pii_ = 0

        if len(pos_info) > 0:
            if self.last_pii_ >= len(pos_info):
                self.last_pii_ = 0

            start_pii = self.last_pii_

            while True:
                pi = pos_info[self.last_pii_]
                if (
                    pi.eid == eid
                    and eid_offset >= pi.eid_offset
                    and eid_offset <= pi.eid_offset + pi.length
                ):
                    return pi.pid + eid_offset - pi.eid_offset

                self.last_pii_ += 1
                if self.last_pii_ >= len(pos_info):
                    self.last_pii_ = 0

                if self.last_pii_ == start_pii:
                    break

        return None

    def eid_for_pid(self, pid, pos_info):
        low = 0
        high = len(pos_info) - 1

        while low <= high:
            mid = ((high - low) // 2) + low
            pi = pos_info[mid]

            if pid < pi.pid:
                high = mid - 1
            elif pid > pi.pid + pi.length:
                low = mid + 1
            else:
                return (pi.eid, pi.eid_offset + pid - pi.pid)

        return (None, None)

    def collect_location_map_info(self, pos_info):
        loc_info = []
        self.prev_loc_ = None
        report = MatchReport(REPORT_LOCATION_DATA)

        def add_loc(pid, eid, eid_offset):
            loc = ContentChunk(pid, eid, eid_offset)
            loc_info.append(loc)

            if REPORT_LOCATION_DATA:
                log.info("location %d %s" % (i + 1, loc))

            if self.prev_loc_:
                self.prev_loc_.length = pid - self.prev_loc_.pid

            self.prev_loc_ = loc

        def end_add_loc():
            if self.prev_loc_ and pos_info:
                self.prev_loc_.length = (
                    pos_info[-1].pid + pos_info[-1].length - self.prev_loc_.pid
                )

        fragment = self.fragments.get("$550", first=True)
        if fragment is not None:
            if (
                ion_type(fragment.value) is IonList
                and len(fragment.value) == 1
                and ion_type(fragment.value[0]) is IonStruct
                and len(set(fragment.value[0].keys()) - {"$182", "$178"}) == 0
            ):
                for i, lm in enumerate(fragment.value[0]["$182"]):
                    extra_keys = set(lm.keys()) - {"$155", "$143"}
                    if extra_keys:
                        log.error(
                            "Bad location_map list keys %s at %d: %s"
                            % (list_symbols(extra_keys), i, repr(fragment))
                        )
                        break

                    eid = lm["$155"]
                    eid_offset = lm.get("$143", 0)

                    pid = self.pid_for_eid(eid, eid_offset, pos_info)
                    if pid is None:
                        log.error(
                            "location_map %d failed to locate eid %s offset %d"
                            % (i + 1, eid, eid_offset)
                        )
                    else:
                        add_loc(pid, eid, eid_offset)

                end_add_loc()
            else:
                log.error("Bad location_map: %s" % repr(fragment))

        fragment = self.fragments.get("$621", first=True)
        has_yj_location_pid_map = fragment is not None
        if has_yj_location_pid_map:
            if (
                ion_type(fragment.value) is IonList
                and len(fragment.value) == 1
                and ion_type(fragment.value[0]) is IonStruct
                and len(set(fragment.value[0].keys()) - {"$182", "$178"}) == 0
            ):
                location_pids = fragment.value[0]["$182"]

                if loc_info:
                    for i, (loc, lpm_pid) in enumerate(zip(loc_info, location_pids)):
                        if loc.pid != lpm_pid:
                            report.report(
                                "location_map pid %d != yj.location_pid_map pid %d for location %d eid %s offset %d"
                                % (loc.pid, lpm_pid, i + 1, loc.eid, loc.eid_offset)
                            )

                    if len(loc_info) != len(location_pids):
                        log.error(
                            "location_map has %d locations but yj.location_pid_map has %d"
                            % (len(loc_info), len(location_pids))
                        )
                else:
                    for i, pid in enumerate(location_pids):
                        eid, eid_offset = self.eid_for_pid(pid, pos_info)
                        if eid is None:
                            log.error(
                                "yj.location_pid_map %d failed to locate eid for pid %d"
                                % (i + 1, pid)
                            )
                        else:
                            add_loc(pid, eid, eid_offset)

                    end_add_loc()
            else:
                log.error("Bad yj.location_pid_map: %s" % repr(fragment))

        report.final()

        if not (self.is_dictionary or self.is_kpf_prepub):
            positionMaps_fc = self.get_feature_value(
                "kfxgen.positionMaps", namespace="format_capabilities"
            )
            if has_yj_location_pid_map and (
                positionMaps_fc != 2 or self.is_print_replica
            ):
                log.error(
                    "yj.location_pid_map with FC kfxgen.positionMaps=%s print_replica=%s"
                    % (positionMaps_fc, self.is_print_replica)
                )

        return loc_info

    def generate_approximate_locations(self, pos_info):
        pid = 0
        next_loc_position = 0
        current_section_name = None
        loc_info = []

        for chunk in pos_info:
            eid_loc_offset = 0
            loc_pid = pid

            if chunk.section_name != current_section_name:
                next_loc_position = loc_pid
                current_section_name = chunk.section_name

            while True:
                if loc_pid == next_loc_position:
                    loc_info.append(
                        ContentChunk(
                            loc_pid, chunk.eid, chunk.eid_offset + eid_loc_offset
                        )
                    )
                    next_loc_position += KFX_POSITIONS_PER_LOCATION

                eid_remaining = chunk.length - eid_loc_offset
                loc_remaining = next_loc_position - loc_pid

                if eid_remaining <= loc_remaining:
                    break

                eid_loc_offset += loc_remaining
                loc_pid = next_loc_position

            pid += chunk.length

        log.info("Built approximate location_map with %d locations" % len(loc_info))
        return loc_info

    def create_location_map(self, loc_info):
        has_yj_location_pid_map = False

        for ftype in ["$550", "$621"]:
            for fragment in self.fragments.get_all(ftype):
                self.fragments.remove(fragment)

        locations = []
        for loc in loc_info:
            locations.append(IonStruct(IS("$155"), loc.eid, IS("$143"), loc.eid_offset))

        location_map = [IonStruct(IS("$182"), locations)]
        self.fragments.append(YJFragment(ftype="$550", value=location_map))

        return has_yj_location_pid_map

    def create_approximate_page_list(self, desired_num_pages):
        if self.cde_type not in [None, "EBOK", "EBSP", "PDOC"]:
            log.error("Cannot create page numbers for KFX %s" % self.cde_type)
            return

        if self.is_dictionary:
            log.error("Cannot create page numbers for KFX dictionary")
            return

        if self.is_fixed_layout and self.get_metadata_value(
            "yj_double_page_spread", "kindle_capability_metadata"
        ):
            log.error(
                "Cannot create page numbers for fixed layout books with page spreads"
            )
            return

        reading_order_names = self.reading_order_names()
        if len(reading_order_names) != 1:
            log.error(
                "Cannot create page numbers - Failed to locate single default reading order"
            )
            return

        reading_order_name = reading_order_names[0]

        book_navigation = self.fragments.get("$389", first=True)
        add_pages = inline_nav_containers = True

        if book_navigation is not None:
            for book_navigation in book_navigation.value:
                if book_navigation["$178"] == reading_order_name:
                    nav_containers = book_navigation["$392"]

                    for i, nav_container in enumerate(nav_containers):
                        if isinstance(nav_container, IonSymbol):
                            nav_container = self.fragments[
                                YJFragmentKey(ftype="$391", fid=nav_container)
                            ].value
                            inline_nav_containers = False

                        nav_container = unannotated(nav_container)
                        if nav_container.get("$235", None) == "$237":
                            nav_container_name = str(nav_container.get("$239"))
                            real_num_pages = len(nav_container["$247"])
                            log.info(
                                "A list of %d %s pages is already present with %s pages desired"
                                % (
                                    real_num_pages,
                                    (
                                        "approximate"
                                        if nav_container_name == APPROXIMATE_PAGE_LIST
                                        else "real"
                                    ),
                                    (
                                        str(desired_num_pages)
                                        if desired_num_pages
                                        else "auto"
                                    ),
                                )
                            )

                            if (
                                desired_num_pages == 0
                                or real_num_pages == desired_num_pages
                                or nav_container_name != APPROXIMATE_PAGE_LIST
                            ) and not DEBUG_PAGES:
                                return
                            else:
                                nav_containers.pop(i)

                            break
                    break
            else:
                log.error(
                    "Cannot create page numbers - Failed to locate book_navigation for reading order %s"
                    % reading_order_name
                )
                return

        section_names = self.ordered_section_names()
        pos_info = self.collect_content_position_info()

        page_template_eids = set()
        for section_name in section_names:
            fragment = self.fragments.get(ftype="$260", fid=section_name)
            if fragment is not None:
                self.walk_fragment(fragment, set(), set(), page_template_eids, set())

        if not (section_names or pos_info):
            log.error(
                "Cannot produce approximate page numbers - No content found for reading order %s"
                % reading_order_name
            )
            return

        if self.is_fixed_layout:
            pages, new_section_page_count = self.determine_approximate_pages(
                pos_info, page_template_eids, section_names[0], 999999, True
            )
            log.info("Created %d fixed layout page numbers" % len(pages))

        elif desired_num_pages == 0:
            pages, new_section_page_count = self.determine_approximate_pages(
                pos_info,
                page_template_eids,
                section_names[0],
                TYPICAL_POSITIONS_PER_PAGE,
            )
            log.info(
                "Created %d approximate page numbers (%d for chapters)"
                % (len(pages), new_section_page_count)
            )

        else:
            min_ppp = MIN_POSITIONS_PER_PAGE
            max_ppp = MAX_POSITIONS_PER_PAGE

            while min_ppp <= max_ppp:
                positions_per_page = (min_ppp + max_ppp) // 2
                pages, new_section_page_count = self.determine_approximate_pages(
                    pos_info, page_template_eids, section_names[0], positions_per_page
                )

                if len(pages) == desired_num_pages:
                    break
                elif len(pages) > desired_num_pages:
                    min_ppp = positions_per_page + 1
                else:
                    max_ppp = positions_per_page - 1

            log.info(
                "Created %d approximate page numbers (%d for chapters) using %d characters per page for %d desired pages"
                % (
                    len(pages),
                    new_section_page_count,
                    positions_per_page,
                    desired_num_pages,
                )
            )

        if pages and add_pages:
            if book_navigation is None:
                log.info("Adding book_navigation")
                book_nav = IonStruct()

                if reading_order_name is not None:
                    book_nav[IS("$178")] = reading_order_name

                book_nav[IS("$392")] = nav_containers = []
                self.fragments.append(YJFragment(ftype="$389", value=[book_nav]))

            if inline_nav_containers:
                pages = [IonAnnotation([IS("$393")], page) for page in pages]

            nav_container_name = self.create_local_symbol(APPROXIMATE_PAGE_LIST)
            nav_container_data = IonStruct(
                IS("$235"),
                IS("$237"),
                IS("$239"),
                nav_container_name,
                IS("$247"),
                pages,
            )

            if inline_nav_containers:
                nav_containers.append(IonAnnotation([IS("$391")], nav_container_data))
            else:
                self.fragments.append(
                    YJFragment(
                        ftype="$391", fid=nav_container_name, value=nav_container_data
                    )
                )
                nav_containers.append(nav_container_name)

    def determine_approximate_pages(
        self,
        pos_info,
        page_template_eids,
        first_section_name,
        positions_per_page,
        fixed_layout=False,
    ):
        pages = []
        new_section_page_count = 0
        next_page_pid = prev_section_name = None

        if DEBUG_PAGES:
            log.info(
                "determine_approximate_pages: first_section_name=%s, positions_per_page=%d"
                % (first_section_name, positions_per_page)
            )

        for chunk in pos_info:
            if chunk.eid in page_template_eids:
                continue

            if chunk.section_name == first_section_name and not GEN_COVER_PAGE_NUMBER:
                continue

            new_section = chunk.section_name != prev_section_name
            prev_section_name = chunk.section_name

            if fixed_layout:
                if new_section:
                    new_section_page_count += 1
                    pages.append(
                        IonStruct(
                            IS("$241"),
                            IonStruct(IS("$244"), "%d" % (len(pages) + 1)),
                            IS("$246"),
                            IonStruct(
                                IS("$155"), chunk.eid, IS("$143"), chunk.eid_offset
                            ),
                        )
                    )
            else:
                if new_section:
                    next_page_pid = chunk.pid
                    new_section_page_count += 1

                min_chunk_offset = 0
                while True:
                    chunk_offset = max(next_page_pid - chunk.pid, 0)
                    if chunk_offset >= chunk.length:
                        break

                    if chunk.text and not chunk.text[chunk_offset].isspace():
                        init_chunk_offset = chunk_offset
                        while True:
                            if chunk_offset == 0:
                                break

                            if chunk_offset <= min_chunk_offset:
                                chunk_offset = init_chunk_offset
                                break

                            if chunk.text[chunk_offset - 1].isspace():
                                break

                            chunk_offset -= 1

                    pages.append(
                        IonStruct(
                            IS("$241"),
                            IonStruct(IS("$244"), "%d" % (len(pages) + 1)),
                            IS("$246"),
                            IonStruct(
                                IS("$155"),
                                chunk.eid,
                                IS("$143"),
                                chunk.eid_offset + chunk_offset,
                            ),
                        )
                    )

                    next_page_pid += positions_per_page
                    min_chunk_offset = chunk_offset + max(
                        positions_per_page - MAX_WHITE_SPACE_ADJUST, 1
                    )

        if DEBUG_PAGES:
            log.info("determine_approximate_pages: produced_pages=%d" % (len(pages)))

        return (pages, new_section_page_count)
