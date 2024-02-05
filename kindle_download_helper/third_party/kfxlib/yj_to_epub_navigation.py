from __future__ import absolute_import, division, print_function, unicode_literals

from .epub_output import TocEntry
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import make_unique_name, urlrelpath
from .yj_position_location import DEBUG_PAGES
from .yj_structure import APPROXIMATE_PAGE_LIST

if IS_PYTHON2:
    from .python_transition import str, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


KEEP_APPROX_PG_NUMS = False

REPORT_DUPLICATE_PAGES = False
PREVENT_DUPLICATE_PAGE_LABELS = False
PREVENT_DUPLICATE_PAGE_TARGETS = False

GUIDE_TYPE_OF_LANDMARK_TYPE = {
    "$233": "cover",
    "$396": "text",
    "$269": "text",
    "$212": "toc",
}


PERIODICAL_NCX_CLASSES = {
    0: "section",
    1: "article",
}


class KFX_EPUB_Navigation(object):
    def process_navigation(self):
        for section_nav in self.book_data.pop("$390", []):
            section_name = section_nav.pop("$174")
            for nav_container in section_nav.pop("$392", []):
                self.nav_container_section[nav_container] = section_name

            self.check_empty(section_nav, "section_navigation")

        book_navigations = self.book_data.pop("$389", [])

        for reading_order in self.reading_orders:
            reading_order_name = reading_order.get("$178", "")

            for i, book_navigation in enumerate(book_navigations):
                if book_navigation.get("$178", "") == reading_order_name:
                    book_navigations.pop(i)
                    book_navigation.pop("$178", None)

                    for nav_container_ in book_navigation.pop("$392"):
                        nav_container = self.get_fragment(
                            ftype="$391", fid=nav_container_
                        )
                        self.process_nav_container(
                            nav_container, nav_container_, reading_order_name
                        )
                        self.check_empty(book_navigation, "book_navigation")

                    break
            else:
                log.warning(
                    'Failed to locate navigation for reading order "%s"'
                    % reading_order_name
                )

        self.check_empty(book_navigations, "book_navigation")

        nav_container = self.book_data.pop("$391", {})
        if not self.book.is_kpf_prepub:
            self.check_empty(nav_container, "nav_container")

        self.check_empty(self.book_data.pop("$394", {}), "conditional_nav_group_unit")

    def process_nav_container(
        self, nav_container, nav_container_name, reading_order_name
    ):
        nav_container.pop("mkfx_id", None)
        nav_container_name = nav_container.pop("$239", nav_container_name)
        section_name = self.nav_container_section.get(nav_container_name)
        nav_type = nav_container.pop("$235")
        if nav_type not in {"$212", "$236", "$237", "$213", "$214"}:
            log.error(
                "nav_container %s has unknown type: %s" % (nav_container_name, nav_type)
            )

        if "imports" in nav_container:
            for import_name in nav_container.pop("imports"):
                self.process_nav_container(
                    self.book_data["$391"].pop(import_name),
                    nav_container_name,
                    reading_order_name,
                )
        else:
            for nav_unit_ in nav_container.pop("$247"):
                nav_unit = self.get_fragment(ftype="$393", fid=nav_unit_)
                nav_unit.pop("mkfx_id", None)

                if nav_type in {"$212", "$214", "$213"}:
                    self.process_nav_unit(
                        nav_type,
                        nav_unit,
                        self.epub.ncx_toc,
                        nav_container_name,
                        section_name,
                    )

                elif nav_type == "$236":
                    label = self.get_representation(nav_unit)[0]
                    nav_unit_name = nav_unit.pop("$240", label)
                    target_position = self.get_position(nav_unit.pop("$246"))
                    landmark_type = nav_unit.pop("$238", None)

                    if landmark_type:
                        guide_type = GUIDE_TYPE_OF_LANDMARK_TYPE.get(landmark_type)
                        if guide_type is None:
                            log.warning("Unexpected landmark_type: %s" % landmark_type)
                            guide_type = landmark_type

                        if label == "cover-nav-unit":
                            label = ""

                        anchor_name = self.unique_anchor_name(
                            str(nav_unit_name) or guide_type
                        )
                        self.register_anchor(anchor_name, target_position)
                        self.epub.add_guide_entry(guide_type, label, anchor=anchor_name)

                elif nav_type == "$237":
                    label = self.get_representation(nav_unit)[0]
                    nav_unit_name = nav_unit.pop("$240", "page_list_entry")
                    target_position = self.get_position(nav_unit.pop("$246"))

                    if nav_unit_name != "page_list_entry":
                        log.warning(
                            "Unexpected page_list nav_unit_name: %s" % nav_unit_name
                        )

                    if label and (
                        KEEP_APPROX_PG_NUMS
                        or DEBUG_PAGES
                        or nav_container_name != APPROXIMATE_PAGE_LIST
                    ):
                        anchor_name = "page_%s" % label
                        if len(self.reading_orders) > 1:
                            anchor_name = "%s_%s" % (reading_order_name, anchor_name)

                        anchor_name = self.unique_anchor_name(anchor_name)
                        anchor_id = self.register_anchor(anchor_name, target_position)

                        if (
                            PREVENT_DUPLICATE_PAGE_TARGETS
                            and anchor_id in self.page_anchor_id_label
                        ):
                            log.warning(
                                "Page %s is at the same position as page %s"
                                % (label, self.page_anchor_id_label[anchor_id])
                            )
                        else:
                            self.page_anchor_id_label[anchor_id] = label

                            if self.page_label_anchor_id.get(label) == anchor_id:
                                if (
                                    REPORT_DUPLICATE_PAGES
                                    and label not in self.reported_duplicate_page_label
                                ):
                                    log.warning(
                                        "Page %s occurs multiple times with same position"
                                        % label
                                    )
                                    self.reported_duplicate_page_label.add(label)
                            elif (
                                PREVENT_DUPLICATE_PAGE_LABELS
                                and len(self.reading_orders) == 1
                            ):
                                log.warning(
                                    "Page %s occurs multiple times with different positions"
                                    % label
                                )
                            else:
                                self.page_label_anchor_id[label] = anchor_id
                                self.epub.add_pagemap_entry(label, anchor=anchor_name)

                self.check_empty(
                    nav_unit, "nav_container %s nav_unit" % nav_container_name
                )

        self.check_empty(nav_container, "nav_container %s" % nav_container_name)

    def process_nav_unit(
        self, nav_type, nav_unit, ncx_toc, nav_container_name, section_name
    ):
        label, icon = self.get_representation(nav_unit)
        if label:
            label = label.strip()

        description = nav_unit.pop("$154", None)
        if description:
            description = description.strip()

        nav_unit_name = nav_unit.pop("$240", label)
        nav_unit.pop("mkfx_id", None)

        nested_toc = []

        for entry in nav_unit.pop("$247", []):
            nested_nav_unit = self.get_fragment(ftype="$393", fid=entry)
            self.process_nav_unit(
                nav_type, nested_nav_unit, nested_toc, nav_container_name, section_name
            )

        for entry_set in nav_unit.pop("$248", []):
            for entry in entry_set.pop("$247", []):
                nested_nav_unit = self.get_fragment(ftype="$393", fid=entry)
                self.process_nav_unit(
                    nav_type,
                    nested_nav_unit,
                    nested_toc,
                    nav_container_name,
                    section_name,
                )

            orientation = entry_set.pop("$215")
            if orientation == "$386":
                if self.epub.orientation_lock != "landscape":
                    nested_toc = []
            elif orientation == "$385":
                if self.epub.orientation_lock == "landscape":
                    nested_toc = []
            else:
                log.error("Unknown entry set orientation: %s" % orientation)

            if section_name and nav_type == "$214":
                for i, entry in enumerate(nested_toc):
                    self.navto_anchor[(section_name, float(i))] = entry.anchor

            self.check_empty(
                entry_set,
                "nav_container %s %s entry_set" % (nav_container_name, nav_type),
            )

        if "$246" in nav_unit:
            anchor_name = "toc%d_%s" % (self.toc_entry_count, nav_unit_name)
            self.toc_entry_count += 1

            target_position = self.get_position(nav_unit.pop("$246"))
            self.register_anchor(anchor_name, target_position)
        else:
            anchor_name = None

        if (not label) and (not anchor_name):
            ncx_toc.extend(nested_toc)
        else:
            ncx_toc.append(
                TocEntry(
                    label,
                    anchor=anchor_name,
                    children=nested_toc,
                    description=description,
                    icon=(
                        self.process_external_resource(icon).filename if icon else None
                    ),
                )
            )

        self.check_empty(
            nav_unit, "nav_container %s %s nav_unit" % (nav_container_name, nav_type)
        )

    def unique_anchor_name(self, anchor_name):
        if anchor_name and anchor_name not in self.anchor_positions:
            return anchor_name

        count = 0
        while True:
            new_anchor_name = "%s:%d" % (anchor_name, count)

            if new_anchor_name not in self.anchor_positions:
                return new_anchor_name

            count += 1

    def process_anchors(self):
        anchors = self.book_data.pop("$266", {})
        for anchor_name, anchor in anchors.items():
            self.check_fragment_name(anchor, "$266", anchor_name)

            if "$186" in anchor:
                self.anchor_uri[str(anchor_name)] = anchor.pop("$186")
            elif "$183" in anchor:
                self.register_anchor(
                    str(anchor_name), self.get_position(anchor.pop("$183"))
                )

            anchor.pop("$597", None)

            self.check_empty(anchor, "anchor %s" % anchor_name)

    def get_position(self, position):
        id = self.get_location_id(position)
        offset = position.pop("$143", 0)
        self.check_empty(position, "position")
        return (id, offset)

    def get_representation(self, entry):
        label = ""
        icon = None

        if "$241" in entry:
            representation = entry.pop("$241")

            if "$245" in representation:
                icon = representation.pop("$245")
                self.process_external_resource(icon)
                label = str(icon)

            if "$244" in representation:
                label = representation.pop("$244")

            self.check_empty(representation, "nav_container representation")

        return (label, icon)

    def position_str(self, position):
        return "%s.%d" % position

    def register_anchor(self, anchor_name, position):
        if self.DEBUG:
            log.debug(
                "register_anchor %s = %s" % (anchor_name, self.position_str(position))
            )

        if not anchor_name:
            raise Exception(
                "register_anchor: anchor name is missing for position %s"
                % self.position_str(position)
            )

        if anchor_name not in self.anchor_positions:
            self.anchor_positions[anchor_name] = set()

        self.anchor_positions[anchor_name].add(position)

        eid, offset = position
        if eid not in self.position_anchors:
            self.position_anchors[eid] = {}

        if offset not in self.position_anchors[eid]:
            self.position_anchors[eid][offset] = []

        if anchor_name not in self.position_anchors[eid][offset]:
            self.position_anchors[eid][offset].append(anchor_name)

        return self.get_anchor_id(self.position_anchors[eid][offset][0])

    def register_link_id(self, eid, kind):
        return self.register_anchor("%s_%s" % (kind, eid), (eid, 0))

    def get_anchor_id(self, anchor_name):
        if anchor_name not in self.anchor_id:
            self.anchor_id[anchor_name] = new_id = make_unique_name(
                self.fix_html_id(anchor_name), self.anchor_ids
            )
            self.anchor_ids.add(new_id)

        return self.anchor_id[anchor_name]

    def process_position(self, eid, offset, elem):
        if self.DEBUG:
            log.debug("process position %s" % self.position_str((eid, offset)))

        if eid in self.position_anchors:
            if offset in self.position_anchors[eid]:
                if self.DEBUG:
                    log.debug("at registered position")

                if not elem.get("id", ""):
                    elem_id = self.get_anchor_id(self.position_anchors[eid][offset][0])
                    elem.set("id", elem_id)
                    if self.DEBUG:
                        log.debug(
                            "set element id %s for position %s"
                            % (elem_id, self.position_str((eid, offset)))
                        )

                anchor_names = self.position_anchors[eid].pop(offset)
                for anchor_name in anchor_names:
                    self.anchor_elem[anchor_name] = elem

                if len(self.position_anchors[eid]) == 0:
                    self.position_anchors.pop(eid)

                return anchor_names

        return []

    def move_anchor(self, old_elem, new_elem):
        for anchor_name, elem in self.anchor_elem.items():
            if elem is old_elem:
                self.anchor_elem[anchor_name] = new_elem

        if "id" in old_elem.attrib:
            new_elem.set("id", old_elem.attrib.pop("id"))

    def move_anchors(self, old_root, target_elem):
        for anchor_name, elem in self.anchor_elem.items():
            if root_element(elem) is old_root:
                self.anchor_elem[anchor_name] = target_elem

        if "id" in old_root.attrib and "id" not in target_elem.attrib:
            target_elem.set("id", old_root.get("id"))

    def get_anchor_uri(self, anchor_name):
        self.used_anchors.add(anchor_name)

        if anchor_name in self.anchor_uri:
            return self.anchor_uri[anchor_name]

        positions = self.anchor_positions.get(anchor_name, [])
        log.error(
            "Failed to locate uri for anchor: %s (position: %s)"
            % (
                anchor_name,
                ", ".join([self.position_str(p) for p in sorted(positions)]),
            )
        )
        return "/MISSING_ANCHOR#" + anchor_name

    def report_duplicate_anchors(self):
        for anchor_name, positions in self.anchor_positions.items():
            if (anchor_name in self.used_anchors) and (len(positions) > 1):
                log.error(
                    "Anchor %s has multiple positions: %s"
                    % (
                        anchor_name,
                        ", ".join([self.position_str(p) for p in sorted(positions)]),
                    )
                )

    def anchor_as_uri(self, anchor):
        return "anchor:" + anchor

    def anchor_from_uri(self, uri):
        return uri[7:]

    def id_of_anchor(self, anchor, filename):
        url = self.get_anchor_uri(anchor)
        purl = urllib.parse.urlparse(url)

        if purl.path != filename or not purl.fragment:
            log.error("anchor %s in file %s links to %s" % (anchor, filename, url))

        return purl.fragment

    def fixup_anchors_and_hrefs(self):
        for anchor_name, elem in self.anchor_elem.items():
            root = root_element(elem)

            for book_part in self.epub.book_parts:
                if book_part.html is root:
                    elem_id = elem.get("id", "")
                    if not elem_id:
                        elem_id = self.get_anchor_id(str(anchor_name))
                        elem.set("id", elem_id)

                    self.anchor_uri[anchor_name] = "%s#%s" % (
                        urllib.parse.quote(book_part.filename),
                        elem_id,
                    )
                    break
            else:
                log.error(
                    "Failed to locate element within book parts for anchor %s"
                    % anchor_name
                )

        self.anchor_elem = None

        for book_part in self.epub.book_parts:
            body = book_part.body()
            for e in body.iter("*"):
                if "id" in e.attrib and not visible_elements_before(e):
                    uri = book_part.filename + "#" + e.get("id")
                    if self.DEBUG:
                        log.debug("no visible element before %s" % uri)

                    for anchor, a_uri in self.anchor_uri.items():
                        if (a_uri == uri) and (anchor not in self.immovable_anchors):
                            self.anchor_uri[anchor] = urllib.parse.quote(
                                book_part.filename
                            )
                            if self.DEBUG:
                                log.debug("   moved anchor %s" % anchor)

        for book_part in self.epub.book_parts:
            body = book_part.body()
            for e in body.iter("*"):
                if e.tag == "a" and e.get("href", "").startswith("anchor:"):
                    e.set(
                        "href",
                        urlrelpath(
                            self.get_anchor_uri(
                                self.anchor_from_uri(e.attrib.pop("href"))
                            ),
                            ref_from=book_part.filename,
                        ),
                    )

        for g in self.epub.guide:
            g.target = self.get_anchor_uri(g.anchor)

        for p in self.epub.pagemap:
            p.target = self.get_anchor_uri(p.anchor)

        def resolve_toc_target(ncx_toc):
            for toc_entry in ncx_toc:
                if toc_entry.anchor:
                    toc_entry.target = self.get_anchor_uri(toc_entry.anchor)

                if toc_entry.children:
                    resolve_toc_target(toc_entry.children)

        resolve_toc_target(self.epub.ncx_toc)


def root_element(elem):
    while elem.getparent() is not None:
        elem = elem.getparent()

    return elem


def visible_elements_before(elem, root=None):
    if root is None:
        root = elem
        while root.tag != "body":
            root = root.getparent()

    if elem is root:
        return False

    for e in root.iterfind(".//*"):
        if e is elem:
            break

        if e.tag in ["img", "br", "hr", "li", "ol", "ul"] or e.text or e.tail:
            return True

    return False
