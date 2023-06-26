from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import re

from lxml import etree

from .epub_output import (
    HTML,
    IDX_ENTRY,
    IDX_IFORM,
    IDX_INFL,
    IDX_ORTH,
    MATH,
    MATHML_NS_URI,
    SVG,
    SVG_NAMESPACES,
    SVG_NS_URI,
    add_meta_name_content,
    namespace,
    qname,
    set_nsmap,
)
from .ion import IS, IonList, IonSExp, IonString, IonStruct, IonSymbol, ion_type
from .ion_text import escape_string
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    OD,
    json_serialize_compact,
    type_name,
    unicode_len,
    unicode_slice,
    urlrelpath,
)
from .yj_to_epub_properties import REVERSE_HERITABLE_PROPERTIES, value_str

if IS_PYTHON2:
    from .python_transition import repr, str, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


FIX_WIDE_UNICODE_OFFSETS = False

CONSOLIDATE_HTML = True

CHECK_UNEXPECTED_CHARS = True

USE_CSS_RESET_ON_FULL_PAGE_IMAGES = False

RESTORE_MATHML_FROM_ANNOTATION = False

INCLUDE_HERO_IMAGE_PROPERTIES = False

SKIP_FIT_WIDTH_FOR_IMAGES = True

LIST_STYLE_TYPES = {
    "$346": "ol",
    "$347": "ol",
    "$342": "ul",
    "$340": "ul",
    "$271": "ul",
    "$349": "ul",
    "$343": "ol",
    "$344": "ol",
    "$345": "ol",
    "$341": "ul",
}

CLASSIFICATION_EPUB_TYPE = {
    "$618": "footnote",
    "$619": "endnote",
    "$281": "footnote",
}

BLOCK_ALIGNED_CONTAINER_PROPERTIES = {
    "-kfx-attrib-colspan",
    "-kfx-attrib-rowspan",
    "-kfx-box-align",
    "-kfx-heading-level",
    "-kfx-layout-hints",
    "-kfx-table-vertical-align",
    "box-sizing",
    "float",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "overflow",
    "page-break-after",
    "page-break-before",
    "page-break-inside",
    "text-indent",
    "transform",
    "transform-origin",
}

BLOCK_CONTAINER_PROPERTIES = (
    REVERSE_HERITABLE_PROPERTIES
    | BLOCK_ALIGNED_CONTAINER_PROPERTIES
    | {
        "display",
    }
)

LINK_CONTAINER_PROPERTIES = REVERSE_HERITABLE_PROPERTIES | {
    "-kfx-attrib-colspan",
    "-kfx-attrib-rowspan",
    "-kfx-table-vertical-align",
    "-kfx-box-align",
    "-kfx-heading-level",
    "-kfx-layout-hints",
    "-kfx-link-color",
    "-kfx-visited-color",
}


UNEXPECTED_CHARACTERS = {
    0x0000,
    0x0001,
    0x0002,
    0x0003,
    0x0004,
    0x0005,
    0x0006,
    0x0007,
    0x0008,
    0x000B,
    0x000C,
    0x000E,
    0x000F,
    0x0010,
    0x0011,
    0x0012,
    0x0013,
    0x0014,
    0x0015,
    0x0016,
    0x0017,
    0x0018,
    0x0019,
    0x001A,
    0x001B,
    0x001C,
    0x001D,
    0x001E,
    0x001F,
    0x0080,
    0x0081,
    0x0082,
    0x0083,
    0x0084,
    0x0085,
    0x0086,
    0x0087,
    0x0088,
    0x0089,
    0x008A,
    0x008B,
    0x008C,
    0x008D,
    0x008E,
    0x008F,
    0x0090,
    0x0091,
    0x0092,
    0x0093,
    0x0094,
    0x0095,
    0x0096,
    0x0097,
    0x0098,
    0x0099,
    0x009A,
    0x009B,
    0x009C,
    0x009D,
    0x009E,
    0x009F,
    0x061C,
    0x2063,
    0xFFF9,
    0xFFFA,
    0xFFFB,
    0xFFFE,
    0xFFFF,
}


NBSP = "\u00a0"


if FIX_WIDE_UNICODE_OFFSETS:
    unicode_len_ = len

    def unicode_slice_(s, start, stop):
        return s[start:stop]

else:
    unicode_len_ = unicode_len
    unicode_slice_ = unicode_slice


class KFX_EPUB_Content(object):
    def process_reading_order(self):
        for reading_order in self.reading_orders:
            for section_ in reading_order["$170"]:
                self.process_section(self.get_fragment(ftype="$260", fid=section_))

    def process_section(self, section):
        section_name = section.pop("$174")
        if self.DEBUG:
            log.debug("Processing section %s" % section_name)

        self.push_context("section %s" % section_name)

        section.pop("$702", None)

        section.pop("yj.conversion.html_name", None)

        section.pop("yj.semantics.book_anatomy_type", None)
        section.pop("yj.semantics.page_type", None)
        section.pop("yj.authoring.auto_panel_settings_auto_mask_color_flag", None)
        section.pop("yj.authoring.auto_panel_settings_mask_color", None)
        section.pop("yj.authoring.auto_panel_settings_opacity", None)
        section.pop("yj.authoring.auto_panel_settings_padding_bottom", None)
        section.pop("yj.authoring.auto_panel_settings_padding_left", None)
        section.pop("yj.authoring.auto_panel_settings_padding_right", None)
        section.pop("yj.authoring.auto_panel_settings_padding_top", None)

        page_templates = section.pop("$141")

        has_conditional_template = False
        for page_template in page_templates:
            if "$171" in page_template:
                has_conditional_template = True
                break

        if self.epub.is_comic:
            if len(page_templates) != 1:
                log.error(
                    "Comic %s has %d page templates"
                    % (self.content_context, len(page_templates))
                )

            self.process_page_spread_page_template(
                self.get_fragment(ftype="$608", fid=page_templates[0]), section_name
            )

        elif (
            self.epub.is_magazine or self.epub.is_print_replica
        ) and has_conditional_template:
            templates_processed = 0

            for i, page_template in enumerate(page_templates):
                if "$171" not in page_template or self.evaluate_binary_condition(
                    page_template.pop("$171")
                ):
                    if page_template["$159"] != "$270":
                        log.error(
                            "%s unexpected page_template type %s"
                            % (self.content_context, page_template["$159"])
                        )

                    layout = page_template["$156"]

                    if layout in ["$325", "$323"]:
                        page_template.pop("$159")
                        page_template.pop("$156")

                        book_part = self.epub.new_book_part()
                        self.link_css_file(book_part, self.epub.STYLES_CSS_FILEPATH)
                        self.add_content(
                            page_template,
                            book_part.html,
                            book_part,
                            self.epub.writing_mode,
                            layout,
                        )
                        self.process_position(
                            self.get_location_id(page_template), 0, book_part.body()
                        )

                        self.check_empty(
                            page_template,
                            "%s conditional page_template %d"
                            % (self.content_context, i),
                        )

                    elif layout == "$437":
                        self.process_page_spread_page_template(
                            page_template, section_name
                        )

                    else:
                        log.error(
                            "%s unexpected page_template layout %s"
                            % (self.content_context, layout)
                        )

                    templates_processed += 1

            if templates_processed != 1:
                log.error(
                    "%s has %d active conditional page templates"
                    % (self.content_context, templates_processed)
                )

        else:
            book_part = self.epub.new_book_part()
            self.process_content(
                page_templates[-1], book_part.html, book_part, self.epub.writing_mode
            )
            self.link_css_file(book_part, self.epub.STYLES_CSS_FILEPATH)
            self.check_empty(
                page_templates[-1], "%s main page_template" % self.content_context
            )

            if len(page_templates) > 1:
                body = book_part.body()

                for i, page_template in enumerate(page_templates[:-1]):
                    if "$171" not in page_template:
                        log.error(
                            "Missing condition in conditional page_template %d for %s"
                            % (i, self.content_context)
                        )

                    self.process_content(
                        page_template, body, book_part, self.epub.writing_mode
                    )
                    self.check_empty(
                        page_template,
                        "%s conditional page_template %d" % (self.content_context, i),
                    )

        self.pop_context()
        self.check_empty(section, self.content_context)

    def process_page_spread_page_template(
        self, page_template, section_name, page_spread="", parent_template_id=None
    ):
        if ion_type(page_template) is IonSymbol:
            page_template = self.get_fragment(ftype="$608", fid=page_template)

        if page_template["$159"] == "$270" and page_template["$156"] in [
            "$437",
            "$438",
        ]:
            page_template.pop("$159")
            layout = page_template.pop("$156")

            virtual_panel = page_template.pop("$434", None)
            if virtual_panel is None:
                if self.epub.is_comic and not self.epub.region_magnification:
                    log.error(
                        "Section %s has missing virtual panel in comic without region magnification"
                        % section_name
                    )
            elif virtual_panel == "$441":
                self.epub.virtual_panels = True
            else:
                log.error("Unexpected virtual_panel: %s" % virtual_panel)

            page_template.pop("$192", None)
            page_template.pop("$67", None)
            page_template.pop("$66", None)
            page_template.pop("$140", None)
            page_template.pop("$560", None)

            parent_template_id = page_template.pop("$155", None) or page_template.pop(
                "$598"
            )
            story = self.get_named_fragment(page_template, ftype="$259")
            story_name = story.pop("$176")
            if self.DEBUG:
                log.debug("Processing %s story %s" % (layout, story_name))

            self.push_context("story %s" % story_name)

            LAYOUTS = {
                "$437": "page-spread",
                "$438": "facing-page",
            }

            base_property = LAYOUTS[layout]
            left_property = base_property + "-left"
            right_property = base_property + "-right"
            page_property = (
                left_property
                if self.epub.page_progression_direction == "ltr"
                else right_property
            )

            for page_template_ in story.pop("$146", []):
                self.process_page_spread_page_template(
                    page_template_, section_name, page_property, parent_template_id
                )
                page_property = (
                    left_property if page_property == right_property else right_property
                )
                parent_template_id = None

            self.pop_context()
            self.check_empty(story, "story %s" % story_name)

        elif (
            page_template["$159"] == "$270"
            and page_template["$156"] == "$323"
            and page_template.get("$656", False)
        ):
            page_template.pop("$159")
            page_template.pop("$156")
            page_template.pop("$656")

            connected_pagination = page_template.pop("$655", 0)
            if connected_pagination != 2:
                log.error("Unexpected connected_pagination: %d" % connected_pagination)

            parent_template_id = page_template.pop("$155", None) or page_template.pop(
                "$598"
            )
            story = self.get_named_fragment(page_template, ftype="$259")
            story_name = story.pop("$176")
            if self.DEBUG:
                log.debug("Processing page_spread story %s" % story_name)

            self.push_context("story %s" % story_name)

            for page_template_ in story.pop("$146", []):
                self.process_page_spread_page_template(
                    page_template_,
                    section_name,
                    "rendition:page-spread-center",
                    parent_template_id,
                )
                parent_template_id = None

            self.pop_context()
            self.check_empty(story, "story %s" % story_name)

        else:
            book_part = self.epub.new_book_part(opf_properties=set(page_spread.split()))
            self.process_content(
                page_template, book_part.html, book_part, self.epub.writing_mode
            )
            self.link_css_file(book_part, self.epub.STYLES_CSS_FILEPATH)

            if parent_template_id is not None:
                self.process_position(str(parent_template_id), 0, book_part.body())

        self.check_empty(page_template, "Section %s page_template" % section_name)

    def process_story(self, story, parent, book_part, writing_mode):
        story_name = story.pop("$176")
        if self.DEBUG:
            log.debug("Processing story %s" % story_name)

        self.push_context("story %s" % story_name)

        location_id = self.get_location_id(story)
        if location_id:
            self.process_position(location_id, 0, parent)

        self.process_content_list(
            story.pop("$146", []), parent, book_part, writing_mode
        )

        self.pop_context()
        self.check_empty(story, self.content_context)

    def add_content(
        self,
        content,
        parent,
        book_part,
        writing_mode,
        content_layout=None,
        fixed_height=None,
        fixed_width=None,
    ):
        if "$145" in content:
            text_elem = etree.SubElement(parent, "span")
            text = self.content_text(content.pop("$145"))
            try:
                text_elem.text = text
            except Exception:
                if not self.epub.is_print_replica:
                    log.error(
                        "%s has invalid text content: %s"
                        % (self.content_context, escape_string(text))
                    )

                text_elem.text = self.clean_text_for_lxml(text)

        elif "$146" in content:
            self.process_content_list(
                content.pop("$146", []),
                parent,
                book_part,
                writing_mode,
                content_layout,
                fixed_height,
                fixed_width,
            )

        elif "$176" in content:
            story_content = self.get_named_fragment(content, ftype="$259")
            self.process_story(story_content, parent, book_part, writing_mode)

    def process_content_list(
        self,
        content_list,
        parent,
        book_part,
        writing_mode,
        content_layout=None,
        fixed_height=None,
        fixed_width=None,
    ):
        if ion_type(content_list) is not IonList:
            raise Exception(
                "%s has unknown content_list data type: %s"
                % (self.content_context, type_name(content_list))
            )

        for content in content_list:
            self.process_content(
                content,
                parent,
                book_part,
                writing_mode,
                content_layout,
                fixed_height,
                fixed_width,
            )

    def process_content(
        self,
        content,
        parent,
        book_part,
        writing_mode,
        content_layout=None,
        fixed_height=None,
        fixed_width=None,
    ):
        if self.DEBUG:
            log.debug("process content: %s\n" % repr(content))

        data_type = ion_type(content)

        if data_type is IonString:
            content_elem = etree.SubElement(parent, "span")
            content_elem.text = content
            return

        if data_type is IonSymbol:
            self.process_content(
                self.get_fragment(ftype="$608", fid=content),
                parent,
                book_part,
                writing_mode,
                content_layout,
                fixed_height,
                fixed_width,
            )
            return

        if data_type is not IonStruct:
            log.info("content: %s" % repr(content))
            raise Exception(
                "%s has unknown content data type: %s"
                % (self.content_context, type_name(content))
            )

        content_type = content.pop("$159", None)
        location_id = self.get_location_id(content)
        self.push_context("%s %s" % (content_type, location_id))

        content_elem = etree.Element("unknown")
        top_level = parent.tag == HTML
        discard = log_result = False

        self.add_kfx_style(content, str(content.pop("$157", "")))

        if "$560" in content:
            writing_mode = self.property_value("$560", copy.deepcopy(content["$560"]))
        elif writing_mode is None:
            writing_mode = self.epub.writing_mode

        content.pop("yj.semantics.page_entity", None)

        if content_type == "$269":
            content_elem.tag = "div"

            content.pop("$597", None)

            content.pop("yj.semantics.type", None)
            content.pop("yj.semantics.toc_creator", None)
            content.pop("yj.semantics.toc_info_type", None)
            content.pop("yj.authoring.metrics_detection_type", None)
            content.pop("yj.authoring.metrics_detection_mode", None)

            if "$605" in content:
                word_iteration_type = content.pop("$605")
                if word_iteration_type != "$604":
                    log.warning(
                        "%s has text word_iteration_type=%s"
                        % (self.content_context, word_iteration_type)
                    )

                self.add_style(content_elem, {"white-space": "nowrap"})

            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$271":
            content_elem.tag = "img"
            img_resource = self.process_external_resource(
                self.get_fragment_name(content, "$164")
            )
            content_elem.set(
                "src", urlrelpath(img_resource.filename, ref_from=book_part.filename)
            )
            content_elem.set("alt", content.pop("$584", ""))

            if self.epub.is_print_replica:
                self.add_style(
                    content_elem,
                    {
                        "height": value_str(img_resource.height, "px"),
                        "width": value_str(img_resource.width, "px"),
                    },
                )

                for dim in ["$57", "$56"]:
                    val = content.pop(dim, None)
                    if val is not None:
                        v = self.property_value(dim, val)
                        if v != "100%":
                            log.error(
                                "Unexpected print replica image %s value: %s" % (dim, v)
                            )

            content.pop("yj.semantics.image_type", None)

        elif content_type == "$274":
            resource_name = content.pop("$175")
            alt_text = content.pop("$584", "")
            content.pop("$597", None)

            self.add_content(content, content_elem, book_part, writing_mode)
            self.process_plugin(resource_name, alt_text, content_elem, book_part)

        elif content_type == "$439":
            content_elem.tag = "div"

            layout = content.pop("$156", None)
            if layout not in ["$323", None]:
                log.error(
                    "%s has unknown %s layout: %s"
                    % (self.content_context, content_type, layout)
                )

            self.add_content(content, content_elem, book_part, writing_mode, layout)

            self.add_style(content_elem, {"display": "none"})

        elif content_type == "$270":
            content_elem.tag = "div"

            layout = content.pop("$156", None)

            is_scale_fit_layout = layout == "$326"

            if top_level and (
                (is_scale_fit_layout and self.epub.fixed_layout) or layout == "$325"
            ):
                book_part.is_fxl = True

            if is_scale_fit_layout and "$67" in content and "$66" in content:
                fixed_height = self.pixel_value(content.pop("$67"))
                fixed_width = self.pixel_value(content.pop("$66"))
            else:
                fixed_height = fixed_width = None

            self.add_content(
                content,
                content_elem,
                book_part,
                writing_mode,
                layout,
                fixed_height,
                fixed_width,
            )

            if layout is None:
                pass

            elif layout == ("$323" if writing_mode != "vertical-rl" else "$322"):
                pass

            elif layout == ("$322" if writing_mode != "vertical-rl" else "$323"):
                if book_part.is_fxl:
                    self.horizontal_fxl_block_images(content_elem, book_part)
                else:
                    self.add_svg_wrapper_to_block_image(content_elem, book_part)

            elif is_scale_fit_layout:
                if "$434" in content:
                    virtual_panel = content.pop("$434")
                    if self.epub.is_comic and virtual_panel == "$441":
                        self.epub.virtual_panels = True
                    else:
                        log.warning(
                            "Unexpected %s container virtual_panel: %s"
                            % (self.epub.book_type, virtual_panel)
                        )

                if "$140" in content:
                    scale_fit_float = content.pop("$140")
                    if scale_fit_float not in ["$320", "$68"]:
                        log.warning(
                            "Unexpected scale_fit container float: %s" % scale_fit_float
                        )

                if "$432" in content:
                    blank = content.pop("$432")
                    if blank is True:
                        pass
                    else:
                        log.error(
                            "%s has scale_fit container blank=%s"
                            % (self.content_context, repr(blank))
                        )

                if book_part.is_fxl and top_level:
                    meta = book_part.head().find("meta")
                    if meta is None or meta.get("name") != "viewport":
                        add_meta_name_content(
                            book_part.head(),
                            "viewport",
                            "width=%d, height=%d" % (fixed_width, fixed_height),
                        )
                        self.link_css_file(book_part, self.epub.RESET_CSS_FILEPATH)
                    else:
                        log.error("Fixed layout html already has viewport when adding")

                    if self.epub.is_comic and book_part.part_index == 0:
                        if len(content_elem) == 1:
                            child = content_elem[0]
                            if (
                                child.tag == "div"
                                and "style" not in child.attrib
                                and len(child) == 1
                            ):
                                gchild = child[0]
                                if gchild.tag == "img" and "style" not in gchild.attrib:
                                    self.add_style(
                                        gchild, {"height": "100%", "width": "100%"}
                                    )
                    elif self.epub.is_print_replica:
                        for child in content_elem:
                            self.add_style(
                                content_elem,
                                {
                                    "height": value_str(fixed_height, "px"),
                                    "width": value_str(fixed_width, "px"),
                                },
                            )
                            new_child = self.replace_element_with_container(
                                child, "div"
                            )
                            self.add_style(
                                new_child,
                                {
                                    "position": "absolute",
                                    "left": "0",
                                    "top": "0",
                                    "height": value_str(fixed_height, "px"),
                                    "width": value_str(fixed_width, "px"),
                                },
                            )

                            child_sty = self.get_style(child)
                            if "z-index" in child_sty:
                                self.add_style(
                                    new_child, {"z-index": child_sty.pop("z-index")}
                                )
                                self.set_style(child, child_sty)
                else:
                    self.add_svg_wrapper_to_block_image(
                        content_elem, book_part, fixed_height, fixed_width
                    )

                    if top_level and USE_CSS_RESET_ON_FULL_PAGE_IMAGES:
                        self.link_css_file(book_part, self.epub.RESET_CSS_FILEPATH)

            elif layout == "$324":
                if "$69" in content:
                    ignore = content.pop("$69")
                    if ignore is True:
                        self.add_style(content_elem, {"z-index": "1"})

                        if not self.epub.is_print_replica:
                            log.error("ignore:true for non-print replica")
                    else:
                        log.error(
                            "%s has fixed container ignore=%s"
                            % (self.content_context, ignore)
                        )

            elif layout == "$325":
                if not self.epub.is_magazine:
                    log.error(
                        "%s container for non-magazine in %s"
                        % (layout, self.content_context)
                    )

                if not top_level:
                    log.error(
                        "%s container is not at top level in %s"
                        % (layout, self.content_context)
                    )

                def px_value(prop_name, expect_zero=False):
                    int_val = 0
                    m = False
                    if prop_name in content:
                        val = self.property_value(prop_name, content.pop(prop_name))
                        m = re.match("^([0-9]+)(px)?$", val)
                        if m:
                            int_val = int(m.group(1))

                    if (not m) or (int_val == 0) is not expect_zero:
                        log.warning(
                            "%s %s container has unexpected value %s for %s"
                            % (self.content_context, layout, val, prop_name)
                        )

                    return int_val

                px_value("$58", expect_zero=True)
                px_value("$59", expect_zero=True)

                fixed_width = px_value("$66")
                fixed_height = px_value("$67")

                meta = book_part.head().find("meta")
                if meta is not None and meta.get("name") == "viewport":
                    log.error("Fixed layout html already has viewport when adding")

                add_meta_name_content(
                    book_part.head(),
                    "viewport",
                    "width=%d, height=%d" % (fixed_width, fixed_height),
                )

                self.link_css_file(book_part, self.epub.RESET_CSS_FILEPATH)

            else:
                log.error(
                    "%s has unknown %s layout: %s"
                    % (self.content_context, content_type, layout)
                )

            if "$475" in content:
                fit_text = content.pop("$475")
                if fit_text == "$472":
                    pass
                else:
                    log.error(
                        "%s has %s container fit_text=%s"
                        % (self.content_context, layout, fit_text)
                    )

            pan_zoom_viewer = content.pop("$684", None)
            if pan_zoom_viewer not in [None, "$441"]:
                log.error(
                    "%s has container pan_zoom_viewer=%s"
                    % (self.content_context, pan_zoom_viewer)
                )

            if "$426" in content:
                if not self.epub.region_magnification:
                    log.error("activate found without region magnification")
                    self.epub.region_magnification = True

                ordinal = content.pop("$427")

                for activate in content.pop("$426"):
                    action = activate.pop("$428")
                    if action == "$468":
                        activate_elem = etree.SubElement(content_elem, "a")
                        activate_elem.set("class", "app-amzn-magnify")

                        activate_elem.set(
                            "data-app-amzn-magnify",
                            json_serialize_compact(
                                OD(
                                    "targetId",
                                    self.register_link_id(
                                        str(activate.pop("$163")), "magnify_target"
                                    ),
                                    "sourceId",
                                    self.register_link_id(
                                        str(activate.pop("$474")), "magnify_source"
                                    ),
                                    "ordinal",
                                    ordinal,
                                )
                            ),
                        )

                        self.check_empty(activate, "%s activate" % self.content_context)
                    else:
                        log.error(
                            "%s has unknown %s action: %s"
                            % (self.content_context, content_type, action)
                        )

            if "$429" in content:
                bd_style_name = content.pop("$429")
                bd_style_content = {}
                self.add_kfx_style(bd_style_content, bd_style_name)
                bd_style_content.pop("$173")
                bd_style_content.pop("$70")
                bd_style_content.pop("$72")
                self.check_empty(bd_style_content, "backdrop style %s" % bd_style_name)

        elif content_type == "$276":
            content_elem.tag = LIST_STYLE_TYPES.get(content.get("$100"), "ul")

            if "$104" in content:
                content_elem.set("start", str(content.pop("$104")))

            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$277":
            if parent.tag not in {"ol", "ul"}:
                log.info(
                    "%s has list item inside %s element"
                    % (self.content_context, parent.tag)
                )

            content_elem.tag = "li"

            if "$104" in content:
                content_elem.set("value", str(content.pop("$104")))

            if "$102" in content:
                list_indent_style = self.convert_yj_properties(
                    {"$53": content.pop("$102")}
                )
                if list_indent_style != self.Style({"padding-left": "0"}):
                    try:
                        self.add_style(parent, list_indent_style, replace=Exception)
                    except Exception:
                        try:
                            self.add_style(
                                content_elem, list_indent_style, replace=Exception
                            )
                            log.info("added list_indent to content_elem")
                        except Exception:
                            log.error(
                                "Could not add list_indent since parent and listitem both already have padding-left"
                            )

            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$278":
            content_elem.tag = "table"

            if "$152" in content:
                colgroup_elem = etree.SubElement(content_elem, "colgroup")

                for col_fmt in content.pop("$152"):
                    col_elem = etree.SubElement(colgroup_elem, "col")
                    if "$118" in col_fmt:
                        col_elem.set("span", str(col_fmt.pop("$118")))

                    col_fmt.pop("$698", False)
                    col_fmt.pop("yj.conversion.source_attr_width", None)
                    col_fmt.pop("yj.conversion.source_style_width", None)

                    self.add_style(col_elem, self.convert_yj_properties(col_fmt))

            if "$700" in content:
                for row, col in content.pop("$700", []):
                    pass

            if "$630" in content:
                table_selection_mode = content.pop("$630")
                if table_selection_mode != "$632":
                    log.error(
                        "%s table has unexpected table_selection_mode: %s"
                        % (self.content_context, table_selection_mode)
                    )

            if "$629" in content:
                for table_feature in content.pop("$629"):
                    if table_feature not in {
                        "$581",
                        "$326",
                        "$657",
                    }:
                        log.error(
                            "%s table has unexpected table_feature: %s"
                            % (self.content_context, table_feature)
                        )

            if "$821" in content:
                for table_metadata_name, table_metadata_value in content.pop(
                    "$821"
                ).items():
                    if table_metadata_name not in {"$824", "$825", "$823", "$822"}:
                        log.error(
                            "%s table has unexpected table_metadata: %s=%s"
                            % (
                                self.content_context,
                                table_metadata_name,
                                repr(table_metadata_value),
                            )
                        )

            if "$755" in content:
                for side in content.pop("$755", []):
                    if side not in {"$58", "$60", "$59", "$61"}:
                        log.error(
                            "%s table has unexpected truncated_bounds side: %s"
                            % (self.content_context, side)
                        )

            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$454":
            content_elem.tag = "tbody"
            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$151":
            content_elem.tag = "thead"
            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$455":
            content_elem.tag = "tfoot"
            self.add_content(content, content_elem, book_part, writing_mode)

        elif content_type == "$279":
            content_elem.tag = "tr"
            self.add_content(content, content_elem, book_part, writing_mode)

            for idx, child_elem in enumerate(list(content_elem)):
                if child_elem.tag == "div":
                    child_elem.tag = "td"
                elif child_elem.tag != "td":
                    if child_elem.tag not in ["table", "ol", "ul"]:
                        log.error(
                            "%s unexpected %s found in table_row"
                            % (self.content_context, child_elem.tag)
                        )

                    td_elem = etree.Element("td")
                    content_elem.remove(child_elem)
                    td_elem.append(child_elem)
                    content_elem.insert(idx, td_elem)

                    child_style = self.get_style(child_elem)
                    td_style = child_style.partition(
                        property_names={"-kfx-attrib-colspan", "-kfx-attrib-rowspan"}
                    )
                    if len(td_style):
                        self.set_style(td_elem, td_style)
                        self.set_style(child_elem, child_style)

        elif content_type == "$596":
            content_elem.tag = "hr"

        elif content_type == "$272":
            content_elem.tag = "svg"
            content_elem = set_nsmap(content_elem, SVG_NAMESPACES)

            content_elem.set("version", "1.1")
            content_elem.set("preserveAspectRatio", "xMidYMid meet")

            if "$66" in content:
                fixed_height = self.pixel_value(content.pop("$67"))
                fixed_width = self.pixel_value(content.pop("$66"))

            if fixed_height is not None and fixed_width is not None:
                content_elem.set("viewBox", "0 0 %d %d" % (fixed_width, fixed_height))
            else:
                log.error("SVG is missing viewBox")

            if "$686" in content:
                kvg_content_type = content.pop("$686", "")
                if kvg_content_type != "$269":
                    log.error(
                        "%s has unknown kvg_content_type: %s"
                        % (self.content_context, kvg_content_type)
                    )

            content_list = content.pop("$146", [])

            for shape in content.pop("$250", []):
                self.process_kvg_shape(
                    content_elem, shape, content_list, book_part, writing_mode
                )

            self.check_empty(content_list, "KVG content_list")

        else:
            log.error(
                "%s has unknown content type: %s" % (self.content_context, content_type)
            )
            content_elem.tag = "div"
            self.add_content(content, content_elem, book_part, writing_mode)

        if "$754" in content:
            self.register_link_id(str(content.pop("$754")), "main_content")

        if "$683" in content:
            for annotation in content.pop("$683"):
                annotation_type = annotation.pop("$687")

                if annotation_type == "$690" and content_type == "$270":
                    annotation_text = self.content_text(annotation.pop("$145"))
                    svg = content_elem.find(".//%s" % SVG)
                    if svg is not None:
                        if RESTORE_MATHML_FROM_ANNOTATION:
                            mathml = etree.fromstring(
                                annotation_text,
                                parser=etree.XMLParser(encoding="utf-8", recover=True),
                            )
                            for elem in mathml.iter("*"):
                                elem.attrib.pop("amzn-src-id", None)
                                elem.attrib.pop("class", None)

                            if "alttext" not in mathml.attrib:
                                mathml.set("alttext", "")

                            svg_parent = svg.getparent()
                            svg_index = svg_parent.index(svg)
                            svg_parent.remove(svg)
                            svg_parent.insert(svg_index, mathml)
                            self.move_anchors(svg, mathml)
                        else:
                            desc = etree.Element(qname(SVG_NS_URI, "desc"))
                            desc.text = annotation_text
                            svg.insert(0 if svg[0].tag != "title" else 1, desc)

                        if "$56" in content and self.property_value(
                            "$56", copy.deepcopy(content["$56"])
                        ) == self.get_style(svg).get("width"):
                            content.pop("$56")
                    else:
                        log.error(
                            "Missing svg for mathml annotation in: %s"
                            % etree.tostring(content_elem)
                        )

                elif annotation_type == "$584" and content_type == "$270":
                    annotation_text = self.content_text(annotation.pop("$145"))
                    if (
                        annotation_text
                        and annotation_text != "no accessible name found."
                    ):
                        content_elem.set("aria-label", annotation_text)

                elif annotation_type == "$749" and content_type == "$278":
                    alt_content_story = self.get_named_fragment(
                        annotation, ftype="$259", name_symbol="$749"
                    )

                    include_condition = annotation.pop("$592")

                    if (
                        include_condition
                        != IonSExp(
                            [
                                "$292",
                                IonSExp(["$293", IonSExp(["$659", "$751"])]),
                                IonSExp(["$750", "$752"]),
                            ]
                        )
                    ) and (
                        include_condition
                        != IonSExp(
                            [
                                "$292",
                                IonSExp(["$293", IonSExp(["$659", "$751"])]),
                                IonSExp(["$750", "$753"]),
                            ]
                        )
                    ):
                        log.warning(
                            "%s alt_content contains unexpected include condition: %s"
                            % (self.content_context, repr(include_condition))
                        )

                    if self.evaluate_condition(include_condition):
                        alt_content_elem = etree.Element("div")
                        self.process_story(
                            alt_content_story, alt_content_elem, book_part, writing_mode
                        )
                        content_elem = alt_content_elem[0]
                        log.warning(
                            "%s table alt_content was included", self.content_context
                        )
                    else:
                        orig_save_resources = self.save_resources
                        self.save_resources = False
                        self.process_story(
                            alt_content_story,
                            etree.Element("div"),
                            book_part,
                            writing_mode,
                        )
                        self.save_resources = orig_save_resources
                else:
                    log.warning(
                        "%s content has unknown %s annotation type: %s"
                        % (self.content_context, content_type, annotation_type)
                    )

                self.check_empty(annotation, "%s annotation" % self.content_context)

        word_boundary_list = content.pop("$696", None)
        if word_boundary_list is not None:
            if len(word_boundary_list) % 2 == 0:
                SEP_RE = r"^[ \n\u25a0]*$"
                txt = self.combined_text(content_elem)
                txt_len = unicode_len(txt)
                offset = 0

                for i in range(0, len(word_boundary_list), 2):
                    sep_len = word_boundary_list[i]
                    if sep_len < 0 or txt_len - offset < sep_len:
                        log.warning(
                            "Unexpected word_boundary_list separator len %d: %s (%d), '%s' (%d)"
                            % (sep_len, str(word_boundary_list), i, txt, offset)
                        )
                        break

                    sep = unicode_slice(txt, offset, offset + sep_len)
                    if not re.match(SEP_RE, sep):
                        log.warning(
                            "Unexpected word_boundary_list separator '%s': %s (%d), '%s' (%d)"
                            % (sep, str(word_boundary_list), i, txt, offset)
                        )
                        log.info("HTML: %s" % etree.tostring(content_elem))

                    offset += sep_len

                    word_len = word_boundary_list[i + 1]
                    if word_len <= 0 or txt_len - offset < word_len:
                        log.warning(
                            "Unexpected word_boundary_list word len %d: %s (%d), '%s' (%d)"
                            % (word_len, str(word_boundary_list), i, txt, offset)
                        )
                        break

                    offset += word_len

                if offset < txt_len:
                    sep = unicode_slice(txt, offset)
                    if not re.match(SEP_RE, sep):
                        log.warning(
                            "Unexpected word_boundary_list final separator '%s': %s (%d), '%s' (%d)"
                            % (sep, str(word_boundary_list), i, txt, offset)
                        )

            else:
                log.warning(
                    "Unexpected word_boundary_list length: %s" % str(word_boundary_list)
                )

        if "$663" in content:

            def check_crop_bleed_condition(condition):
                self.evaluate_binary_condition(condition)

                if (
                    ion_type(condition) is IonSExp
                    and len(condition) == 4
                    and condition[0] == "$659"
                    and condition[1] == "$664"
                    and condition[2] == "crop_bleed"
                    and condition[3] == 1
                ):
                    return True

                log.error(
                    "Unexpected condition for yj.conditional_properties: %s"
                    % repr(condition)
                )
                return False

            for conditional_properties in content.pop("$663"):
                if "$592" in conditional_properties:
                    if check_crop_bleed_condition(conditional_properties.pop("$592")):
                        conditional_properties.pop("$647", None)
                        conditional_properties.pop("$648", None)

                        if INCLUDE_HERO_IMAGE_PROPERTIES:
                            self.add_style(
                                content_elem,
                                self.process_content_properties(conditional_properties),
                            )
                        else:
                            conditional_properties.pop("$644", None)
                            conditional_properties.pop("$643", None)
                            conditional_properties.pop("$645", None)
                            conditional_properties.pop("$641", None)
                            conditional_properties.pop("$642", None)
                            conditional_properties.pop("$639", None)

                    self.check_empty(
                        conditional_properties, "yj.conditional_properties include"
                    )

                elif "$591" in conditional_properties:
                    if check_crop_bleed_condition(conditional_properties.pop("$591")):
                        if not INCLUDE_HERO_IMAGE_PROPERTIES:
                            self.add_style(
                                content_elem,
                                self.process_content_properties(conditional_properties),
                            )
                        else:
                            conditional_properties.pop("$580", None)

                    self.check_empty(
                        conditional_properties, "yj.conditional_properties exclude"
                    )

                else:
                    log.error(
                        "yj.conditional_properties without include or exclude: %s"
                        % repr(conditional_properties)
                    )

        if "$436" in content:
            selection = content.pop("$436")
            if selection not in ["$442", "$441"]:
                log.error("Unexpected selection: %s" % selection)

        if "$622" in content:
            first_line_style = content.pop("$622")
            self.add_kfx_style(first_line_style, first_line_style.pop("$173", None))
            first_line_style.pop("$173", None)

            first_line_style_type = first_line_style.pop("$625", {})
            if (
                len(first_line_style_type) != 1
                or first_line_style_type.get("$623") != 1
            ):
                log.error(
                    "%s has unknown first_line_style_type: %s"
                    % (self.content_context, repr(first_line_style_type))
                )

            self.add_style(
                content_elem,
                self.process_content_properties(first_line_style).partition(
                    name_prefix="-kfx-firstline", add_prefix=True
                ),
            )

            self.check_empty(
                first_line_style, "%s first_line_style" % self.content_context
            )

        if content_layout in ["$324", "$325"]:
            self.add_style(content_elem, {"position": "fixed"})

        if "$615" in content:
            classification = content.pop("$615")

            if classification in CLASSIFICATION_EPUB_TYPE:
                if content_elem.tag == "div" and not self.epub.generate_epub2:
                    content_elem.tag = "aside"
                    self.add_style(
                        content_elem,
                        {
                            "-kfx-attrib-epub-type": CLASSIFICATION_EPUB_TYPE[
                                classification
                            ]
                        },
                    )

            elif classification == "$688":
                if not self.epub.generate_epub2:
                    content_elem.set("role", "math")

            elif classification == "$689":
                pass

            elif classification == "$453":
                if content_elem.tag == "div" and parent.tag == "table":
                    content_elem.tag = "caption"

            else:
                log.warning(
                    "%s content has classification: %s"
                    % (self.content_context, classification)
                )

        if location_id:
            self.process_position(location_id, 0, content_elem)

            if location_id in self.position_anchors:
                for anchor_offset in sorted(self.position_anchors[location_id].keys()):
                    elem = self.locate_offset(
                        content_elem, anchor_offset, split_after=False, zero_len=True
                    )
                    if elem is not None:
                        self.process_position(location_id, anchor_offset, elem)

        content.pop("yj.conversion.offset_map", None)

        content.pop("yj.conversion.modified_content_info", None)

        content.pop("yj.conversion.html_name_index", None)
        content.pop("yj.conversion.source_attr_width", None)
        content.pop("yj.conversion.source_attr_height", None)
        content.pop("yj.conversion.source_style_height", None)
        content.pop("yj.conversion.source_style_width", None)

        style_events = list(content.pop("$142", []))
        if style_events:
            if content_type not in ["$269", "$277"]:
                log.error(
                    "%s id %s has unexpected style events in %s"
                    % (self.content_context, location_id, content_type)
                )

        dropcap_chars = content.pop("$126", 0)
        dropcap_lines = content.pop("$125", 0)

        if (
            (dropcap_lines and not dropcap_chars)
            or dropcap_chars < 0
            or dropcap_lines < 0
        ):
            log.error(
                "%s has dropcap_chars %d with dropcap_lines %d"
                % (self.content_context, dropcap_chars, dropcap_lines)
            )
        elif dropcap_chars and dropcap_lines:
            if content_type not in ["$269", "$277", "$270"]:
                log.error(
                    "%s id %s has unexpected dropcap in %s"
                    % (self.content_context, location_id, content_type)
                )

            dropcap_style_event = {
                IS("$143"): 0,
                IS("$144"): dropcap_chars,
                IS("$125"): dropcap_lines,
            }

            if "$173" in content:
                dropcap_style_event[IS("$173")] = content["$173"]

            style_events.append(dropcap_style_event)

        for style_event in style_events:
            event_offset = style_event.pop("$143")
            event_length = style_event.pop("$144")

            event_elem = self.find_or_create_style_event_element(
                content_elem, event_offset, event_length
            )
            if event_elem is None:
                break

            self.add_kfx_style(style_event, style_event.pop("$157", None))

            if "$757" in style_event:
                ruby_name = style_event.pop("$757")
                event_elem = self.replace_element_with_container(event_elem, "ruby")
                next_ruby_offset = 0

                if "$758" in style_event:
                    ruby_id_list = [
                        {
                            "$758": style_event.pop("$758"),
                            "$143": 0,
                            "$144": event_length,
                        }
                    ]
                else:
                    ruby_id_list = style_event.pop("$759")

                for ruby_id_entry in ruby_id_list:
                    ruby_offset = ruby_id_entry.pop("$143")
                    ruby_length = ruby_id_entry.pop("$144")

                    if ruby_offset != next_ruby_offset:
                        log.error(
                            "Unexpected ruby offset %d, expected %d"
                            % (ruby_offset, next_ruby_offset)
                        )

                    if ruby_offset == 0 and ruby_length == event_length and False:
                        rb_elem = event_elem[0]
                    else:
                        rb_elem = self.find_or_create_style_event_element(
                            event_elem, ruby_offset, ruby_length
                        )
                        if rb_elem is None:
                            break

                        while rb_elem.getparent() is not event_elem:
                            if len(rb_elem.getparent()) != 1:
                                rb_elem.tag = "rb-bad"
                                raise Exception(
                                    "rb element not a child of ruby element: %s"
                                    % etree.tostring(event_elem)
                                )

                            rb_elem = rb_elem.getparent()

                    rb_elem = self.replace_element_with_container(rb_elem, "rb")

                    ruby_id = ruby_id_entry.pop("$758")
                    ruby_content = self.get_ruby_content(ruby_name, ruby_id)

                    if ruby_content.pop("$159") == "$269":
                        rt_elem = etree.Element("rt")
                        event_elem.insert(event_elem.index(rb_elem) + 1, rt_elem)

                        rt_span = etree.SubElement(rt_elem, "span")
                        rt_span.text = ruby_content.pop("$145", "")

                        self.add_kfx_style(ruby_content, ruby_content.pop("$157", None))

                        rt_style = self.process_content_properties(ruby_content)
                        if rt_style.get("font-size") == "0.5em":
                            rt_style.pop("font-size")

                        self.add_style(rt_elem, rt_style)
                    else:
                        log.error(
                            "Unexpected ruby_content type: %s" % ruby_content["$159"]
                        )

                    ruby_content.pop("$758")
                    ruby_content.pop("$155", None)
                    ruby_content.pop("$598", None)
                    ruby_content.pop("yj.conversion.offset_map", None)
                    self.check_empty(
                        ruby_content, "ruby_content %s %d" % (ruby_name, ruby_id)
                    )

                    self.check_empty(ruby_id_entry, "ruby_id_entry")
                    next_ruby_offset += ruby_length

                if next_ruby_offset != event_length:
                    log.error(
                        "Unexpected ruby combined length %d, unannotated text length %d"
                        % (next_ruby_offset, event_length)
                    )

            if (
                "$616" in style_event
                or "class" in event_elem.attrib
                or "style" in event_elem.attrib
            ):
                event_elem = self.replace_element_with_container(
                    event_elem, "div" if event_elem.tag == "div" else "span"
                )

            if "$604" in style_event:
                model = style_event.pop("$604")
                if model != "$606":
                    log.warning(
                        "%s has style_event model=%s" % (self.content_context, model)
                    )

            if "$125" in style_event:
                self.add_style(
                    event_elem,
                    {
                        "float": "left",
                        "font-size": value_str(style_event.pop("$125"), "em"),
                        "line-height": "100%",
                        "margin-top": "0",
                        "margin-right": "0.1em",
                        "margin-bottom": "0",
                    },
                )

            if "$179" in style_event:
                if event_elem.tag == "span" and not event_elem.text:
                    event_elem.tag = "a"
                else:
                    event_elem = self.replace_element_with_container(event_elem, "a")

                event_elem.set("href", self.anchor_as_uri(style_event.pop("$179")))

            self.add_style(
                event_elem, self.process_content_properties(style_event), replace=True
            )
            event_elem_style = self.get_style(event_elem)

            self.fix_vertical_align_properties(
                event_elem, event_elem_style, set_style_if_changed=True
            )

            if (
                book_part.is_fxl
                and event_elem_style.get("position", "static") == "static"
            ):
                for positioning in ["top", "bottom", "left", "right"]:
                    if positioning in event_elem_style:
                        event_elem_style["position"] = "absolute"
                        self.set_style(event_elem, event_elem_style)
                        break

            if (
                event_elem.tag == "a"
                and event_elem_style.get("visibility", "") == "hidden"
            ):
                event_elem_style.pop("visibility")

                if (
                    book_part.is_fxl
                    and "width" in event_elem_style
                    and "height" not in event_elem_style
                ):
                    event_elem_style["height"] = "100%"

                self.set_style(event_elem, event_elem_style)

                for i in range(len(event_elem)):
                    self.add_style(
                        event_elem[i], {"visibility": "hidden"}, replace=True
                    )

            self.check_empty(style_event, "%s style_event" % self.content_context)

        min_aspect_ratio = content.pop("$647", None)
        if min_aspect_ratio is not None and (
            self.epub.min_aspect_ratio is None
            or min_aspect_ratio < self.epub.min_aspect_ratio
        ):
            self.epub.min_aspect_ratio = min_aspect_ratio

        max_aspect_ratio = content.pop("$648", None)
        if max_aspect_ratio is not None and (
            self.epub.max_aspect_ratio is None
            or max_aspect_ratio > self.epub.max_aspect_ratio
        ):
            self.epub.max_aspect_ratio = max_aspect_ratio

        fit_tight = content.pop("$784", False)
        fit_width = content.pop("$478", False)
        link_to = content.pop("$179", None)
        render = content.pop("$601", None)
        content.pop("$597", None)

        content_style = self.get_style(content_elem, remove=True)
        content_style.update(self.process_content_properties(content), replace=True)
        self.check_empty(
            content, "%s content type %s" % (self.content_context, content_type)
        )

        if fit_tight:
            if "width" in content_style:
                if content_style.get("width") != "100%":
                    log.error(
                        "Unexpected width for fit_tight: %s"
                        % content_style.get("width")
                    )
                else:
                    content_style.pop("width")

        if book_part.is_fxl and content_style.get("position", "static") == "static":
            for positioning in ["top", "bottom", "left", "right"]:
                if positioning in content_style:
                    content_style["position"] = "absolute"
                    break

        if link_to is not None:
            container_elem, container_style = self.create_container(
                content_elem, content_style, "a", LINK_CONTAINER_PROPERTIES
            )

            container_elem.set("href", self.anchor_as_uri(link_to))
            self.fix_vertical_align_properties(content_elem, content_style)
            self.set_style(content_elem, content_style)
            content_elem = container_elem
            content_style = container_style

        if render == "$283":
            content_style["-kfx-render"] = "inline"

            if content_elem.tag in {"a", "audio", "img", SVG, "video"}:
                if content_style.get("text-indent") == "0":
                    content_style.pop("text-indent")

            elif content_elem.tag in {"div", "table"}:
                if content_elem.tag == "div":
                    content_elem.tag = "span"
                    if self.is_inline_only(content_elem):
                        if (
                            len(content_elem) == 1
                            and content_elem[0].tag == "span"
                            and len(content_elem[0]) == 0
                            and len(content_elem[0].attrib) == 0
                        ):
                            e = content_elem[0]
                            content_elem.text = (
                                (content_elem.text or "")
                                + (e.text or "")
                                + (e.tail or "")
                            )
                            content_elem.remove(e)
                    else:
                        content_elem.tag = "div"
                        fit_width = True
                else:
                    fit_width = True

            else:
                log.error("Unexpected render:inline for %s element" % content_elem.tag)

        else:
            if render is not None:
                log.error("%s has unknown render: %s" % (self.content_context, render))

            if (
                content_elem.tag in ["a", "audio", "img", SVG, "video"]
                and content_style.get("position") != "fixed"
            ):
                if SKIP_FIT_WIDTH_FOR_IMAGES:
                    fit_width = False

                container_elem, container_style = self.create_container(
                    content_elem, content_style, "div", BLOCK_CONTAINER_PROPERTIES
                )

                if "-kfx-box-align" in container_style and not fit_width:
                    container_style["text-align"] = container_style.pop(
                        "-kfx-box-align"
                    )

                self.fix_vertical_align_properties(content_elem, content_style)
                self.set_style(content_elem, content_style)
                content_elem = container_elem
                content_style = container_style

        if fit_width:
            if "float" in content_style:
                pass
            elif content_elem.tag in ["div", "ol", "ul"]:
                content_style["display"] = "inline-block"
            elif content_elem.tag == "table":
                content_style["display"] = "inline-table"
            else:
                log.warning(
                    "Unexpected fit_width found for %s element at %s"
                    % (content_elem.tag, self.content_context)
                )

            if "width" not in content_style:
                width_elem = None
                child_elem = content_elem

                while True:
                    if "width" in self.get_style(child_elem):
                        if width_elem is not None:
                            width_elem = None
                            break
                        else:
                            width_elem = child_elem

                    if len(child_elem) > 1:
                        width_elem = None
                        break

                    if len(child_elem) == 0 or child_elem.tag in [
                        "audio",
                        SVG,
                        "video",
                    ]:
                        break

                    child_elem = child_elem[0]

                if width_elem is not None and width_elem.tag in [
                    "audio",
                    "img",
                    SVG,
                    "video",
                ]:
                    child_style = self.get_style(width_elem)
                    if child_style["width"].endswith("%"):
                        content_style["width"] = child_style.pop("width")
                        child_style["width"] = "100%"
                        self.set_style(width_elem, child_style)

            if "-kfx-box-align" in content_style:
                if "float" in content_style:
                    log.error(
                        "box-align %s with float %s in %s"
                        % (
                            content_style["-kfx-box-align"],
                            content_style["float"],
                            book_part.filename,
                        )
                    )
                    content_style.pop("-kfx-box-align")
                else:
                    container_elem, container_style = self.create_container(
                        content_elem,
                        content_style,
                        "div",
                        BLOCK_ALIGNED_CONTAINER_PROPERTIES,
                    )
                    container_style["text-align"] = container_style.pop(
                        "-kfx-box-align"
                    )
                    self.fix_vertical_align_properties(content_elem, content_style)
                    self.set_style(content_elem, content_style)
                    content_elem = container_elem
                    content_style = container_style

        if "-kfx-box-align" in content_style:
            if content_elem.tag not in ["div", "hr", "img", "ol", "table", "ul"]:
                log.warning(
                    "Unexpected box-align found in %s element: %s"
                    % (content_elem.tag, content_style.tostring())
                )

            box_align = content_style.pop("-kfx-box-align")
            if box_align in ["left", "right", "center"]:
                if "width" in content_style or content_elem.tag == "table":
                    if box_align != "left":
                        content_style["margin-left"] = "auto"

                    if box_align != "right":
                        content_style["margin-right"] = "auto"
            else:
                log.error("Unexpected box-align value: %s" % box_align)

        self.fix_vertical_align_properties(content_elem, content_style)
        self.set_style(content_elem, content_style)

        if not discard:
            if top_level:
                if content_elem.tag not in ["aside", "div", "figure"]:
                    log.error(
                        "Top level element in html file for %s is '%s'"
                        % (self.content_context, content_elem.tag)
                    )
                    container_elem = etree.Element(content_elem.tag)
                    container_elem.append(content_elem)
                    content_elem = container_elem

                content_elem.tag = "body"

            if log_result:
                log.info("content_elem: %s" % etree.tostring(content_elem))

            parent.append(content_elem)

        self.pop_context()

    def create_container(self, content_elem, content_style, tag, container_properties):
        container_elem = etree.Element(tag)
        container_elem.append(content_elem)

        container_style = content_style.partition(property_names=container_properties)

        if "id" in content_elem.attrib and not self.epub.illustrated_layout:
            self.move_anchor(content_elem, container_elem)

        if "-kfx-style-name" in content_style:
            container_style["-kfx-style-name"] = content_style["-kfx-style-name"]

        return (container_elem, container_style)

    def create_span_subcontainer(self, content_elem, content_style):
        if content_elem.tag not in [
            "a",
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
            "ruby",
            "span",
            "td",
        ]:
            log.warning("Creating span subcontainer inside of %s" % content_elem.tag)

        subcontainer_elem = etree.Element("span")
        subcontainer_elem.text = content_elem.text
        content_elem.text = ""

        while len(content_elem) > 0:
            e = content_elem[0]
            content_elem.remove(e)
            subcontainer_elem.append(e)

        if "-kfx-style-name" in content_style:
            self.add_style(
                subcontainer_elem, {"-kfx-style-name": content_style["-kfx-style-name"]}
            )

        content_elem.append(subcontainer_elem)
        return subcontainer_elem

    def fix_vertical_align_properties(
        self, content_elem, content_style, set_style_if_changed=False
    ):
        style_changed = False

        for prop in [
            "-kfx-baseline-shift",
            "-kfx-baseline-style",
            "-kfx-table-vertical-align",
        ]:
            if prop in content_style:
                outer_vertical_align = content_style.pop(prop)
                style_changed = True

                if "vertical-align" not in content_style:
                    content_style["vertical-align"] = outer_vertical_align

                elif content_style["vertical-align"] != outer_vertical_align:
                    subcontainer_elem = self.create_span_subcontainer(
                        content_elem, content_style
                    )
                    self.add_style(
                        subcontainer_elem,
                        {"vertical-align": content_style.pop("vertical-align")},
                    )
                    content_style["vertical-align"] = outer_vertical_align

        if set_style_if_changed and style_changed:
            self.set_style(content_elem, content_style)

    def content_text(self, content):
        t = ion_type(content)
        if t is IonString:
            return content

        if t is IonStruct:
            content_name = content.pop("name")
            content_index = content.pop("$403")
            self.check_empty(content, "content")

            if (
                "$145" not in self.book_data
                or content_name not in self.book_data["$145"]
            ):
                log.error("Missing book content: %s" % content_name)
                return ""

            return self.book_data["$145"][content_name]["$146"][content_index]

        raise Exception("Unexpected content type: %s" % type_name(content))

    def combined_text(self, elem):
        if elem.tag in {"img", SVG, MATH}:
            return " "

        if (
            self.text_combine_in_use
            and self.get_style(elem).get("text-combine-upright") == "all"
        ):
            return " "

        texts = []

        if elem.text:
            texts.append(elem.text)

        for e in elem.iterfind("*"):
            texts.append(self.combined_text(e))

        if elem.tail:
            texts.append(elem.tail)

        return "".join(texts)

    def locate_offset(self, root, offset_query, split_after=False, zero_len=False):
        if self.DEBUG:
            log.debug("locating offset %d in %s" % (offset_query, etree.tostring(root)))

        result = self.locate_offset_in(root, offset_query, split_after, zero_len)

        if not isinstance(result, int):
            return result

        if result == 0 and not split_after:
            return etree.SubElement(root, "span")

        log.error(
            "locate_offset failed to find offset %d (remaining=%d, split_after=%s) in %s"
            % (offset_query, result, str(split_after), etree.tostring(root))
        )

        return None

    def locate_offset_in(self, elem, offset_query, split_after, zero_len):
        if offset_query < 0:
            return offset_query

        if elem.tail:
            log.error("locate_offset found tail in %s element" % elem.tag)

        if elem.tag == "span":
            text_len = unicode_len_(elem.text or "")

            if text_len > 1 and self.text_combine_in_use:
                e = elem
                while e is not None:
                    if self.get_style(e).get("text-combine-upright") == "all":
                        text_len = 1
                        break

                    e = e.getparent()

            if text_len > 0:
                if not split_after:
                    if offset_query == 0:
                        return elem

                    elif offset_query < text_len:
                        new_span = self.split_span(elem, offset_query)

                        if zero_len:
                            self.split_span(new_span, 0)

                        return new_span
                else:
                    if offset_query == text_len - 1:
                        return elem

                    elif offset_query < text_len:
                        self.split_span(elem, offset_query + 1)
                        return elem

                offset_query -= text_len

            scan_children = True

        else:
            if elem.text:
                log.error("locate_offset found text in %s element" % elem.tag)

            if (
                elem.tag in {"img", SVG, MATH}
                or self.get_style(elem).get("-kfx-render") == "inline"
            ):
                if offset_query == 0:
                    return elem

                offset_query -= 1
                scan_children = False

            elif elem.tag in {
                "a",
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
                "ruby",
                "rb",
            }:
                scan_children = True

            elif elem.tag in {"rt"}:
                scan_children = False

            else:
                log.error("locate_offset found unexpected element %s" % elem.tag)
                scan_children = False

        if scan_children:
            for e in elem.iterfind("*"):
                result = self.locate_offset_in(e, offset_query, split_after, zero_len)

                if not isinstance(result, int):
                    return result

                offset_query = result

        return offset_query

    def split_span(self, old_span, first_text_len):
        new_span = etree.Element("span")
        text = old_span.text or ""

        old_span.text = unicode_slice_(text, None, first_text_len) or None
        new_span.text = unicode_slice_(text, first_text_len, None) or None

        self.set_style(new_span, self.get_style(old_span))

        parent = old_span.getparent()
        parent.insert(parent.index(old_span) + 1, new_span)

        return new_span

    def link_css_file(self, book_part, css_file, css_type="text/css"):
        self.css_files.add(css_file)
        link = etree.SubElement(book_part.head(), "link")
        link.set("rel", "stylesheet")
        link.set("type", css_type)
        link.set(
            "href",
            urllib.parse.quote(urlrelpath(css_file, ref_from=book_part.filename)),
        )

    def reset_preformat(self):
        self.ps_first_in_block = True
        self.ps_previous_char = ""
        self.ps_previous_replaced = False
        self.ps_prior_is_tail = False
        self.ps_prior_elem = None

    def preformat_spaces(self, elem):
        if elem.tag in {"audio", "iframe", "img", "object", SVG, "video"}:
            self.ps_first_in_block = False
            self.ps_previous_char = "?"
            self.ps_previous_replaced = False
            self.ps_prior_elem = None

        elif elem.tag in {
            "a",
            "b",
            "bdi",
            "bdo",
            "em",
            "i",
            "path",
            "rb",
            "rt",
            "ruby",
            "span",
            "strong",
            "sub",
            "sup",
            "u",
            IDX_ORTH,
            IDX_INFL,
            IDX_IFORM,
            MATH,
        } or namespace(elem.tag) in {MATHML_NS_URI, SVG_NS_URI}:
            pass

        else:
            if elem.tag not in {
                "body",
                "nav",
                "aside",
                "div",
                "figure",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "ul",
                "ol",
                "li",
                "table",
                "tbody",
                "thead",
                "tr",
                "td",
                "caption",
                "br",
                "colgroup",
                "col",
                "hr",
                IDX_ENTRY,
                "text",
                "title",
                "desc",
            }:
                log.warning(
                    "Unexpected block start tag in preformat_spaces: %s" % elem.tag
                )

            self.reset_preformat()

        if elem.tag not in {SVG, MATH}:
            self.preformat_text(elem)

            for child in elem:
                self.preformat_spaces(child)

        self.preformat_text(elem, do_tail=True)

    def preformat_text(self, elem, do_tail=False):
        text = elem.tail if do_tail else elem.text

        if not text:
            return

        for i, ch in enumerate(text):
            did_replace = False

            if ch == " " and (self.ps_first_in_block or self.ps_previous_char == " "):
                if self.ps_previous_char == " " and not self.ps_previous_replaced:
                    if i > 0:
                        text = text[: i - 1] + NBSP + text[i:]
                    else:
                        if self.ps_prior_is_tail:
                            self.ps_prior_elem.tail = (
                                self.ps_prior_elem.tail[:-1] + NBSP
                            )
                        else:
                            self.ps_prior_elem.text = (
                                self.ps_prior_elem.text[:-1] + NBSP
                            )

                text = text[:i] + NBSP + text[i + 1 :]
                did_replace = True

            self.ps_first_in_block = False
            self.ps_previous_char = ch
            self.ps_previous_replaced = did_replace

        if do_tail:
            elem.tail = text
        else:
            elem.text = text

        self.ps_prior_is_tail = do_tail
        self.ps_prior_elem = elem

    def replace_eol_with_br(self, body):
        EOL_CHARS = [
            "\n",
            "\r",
            "\u2028",
            "\u2029",
        ]

        changed = True
        while changed:
            changed = False
            for e in body.iterfind(".//*"):
                if e.text:
                    for eol in EOL_CHARS:
                        if eol in e.text:
                            e.text, x, post = e.text.partition(eol)
                            br = etree.Element("br")
                            e.insert(0, br)

                            if post:
                                br.tail = post

                            changed = True

                if e.tail:
                    for eol in EOL_CHARS:
                        if eol in e.tail:
                            e.tail, x, post = e.tail.partition(eol)
                            br = etree.Element("br")
                            parent = e.getparent()
                            parent.insert(parent.index(e) + 1, br)

                            if post:
                                br.tail = post

                            changed = True

                if changed:
                    break

    def prepare_book_parts(self):
        for book_part in self.epub.book_parts:
            if self.DEBUG:
                log.debug(
                    "%s: %s" % (book_part.filename, etree.tostring(book_part.html))
                )

            body = book_part.body()

            self.replace_eol_with_br(body)
            self.reset_preformat()
            self.preformat_spaces(body)

    def add_kfx_style(self, content, kfx_style_name):
        if kfx_style_name:
            kfx_styles = self.book_data.get("$157", {})
            if kfx_style_name in kfx_styles:
                self.used_kfx_styles.add(kfx_style_name)

                for k, v in kfx_styles[kfx_style_name].items():
                    if k not in content:
                        content[k] = (
                            copy.deepcopy(v)
                            if ion_type(v) in {IonList, IonStruct}
                            else v
                        )

            elif kfx_style_name not in self.missing_kfx_styles:
                log.error(
                    "%s No definition found for KFX style: %s"
                    % (self.content_context, kfx_style_name)
                )
                self.missing_kfx_styles.add(kfx_style_name)

    def clean_text_for_lxml(self, text):
        s = ""

        for c in text:
            if ord(c) in UNEXPECTED_CHARACTERS:
                c = "?"
            s += c

        return s

    def replace_element_with_container(self, elem, tag):
        parent = elem.getparent()
        elem_index = parent.index(elem)
        parent.remove(elem)
        new_elem = etree.Element(tag)
        new_elem.append(elem)
        parent.insert(elem_index, new_elem)

        return new_elem

    def create_element_content_container(self, elem, tag):
        new_elem = etree.Element(tag)
        new_elem.text = elem.text
        elem.text = ""

        while len(elem):
            e = elem[0]
            elem.remove(e)
            new_elem.append(e)

        elem.append(new_elem)
        return new_elem

    def find_or_create_style_event_element(
        self, content_elem, event_offset, event_length
    ):
        if event_length <= 0:
            raise Exception(
                "%s style event has length: %s" % (self.content_context, event_length)
            )

        first = self.locate_offset(content_elem, event_offset, split_after=False)
        if first is None:
            return None

        last = self.locate_offset(
            content_elem, event_offset + event_length - 1, split_after=True
        )

        if last is None or first is last:
            return first

        first_parent = first.getparent()
        last_parent = last.getparent()
        if first_parent != last_parent:
            try_first = first
            firsts = [try_first]
            while (
                first_parent is not None
                and len(first_parent.text or "") == 0
                and first_parent.index(try_first) == 0
            ):
                try_first = first_parent
                first_parent = try_first.getparent()

                if first_parent is not None:
                    firsts.append(try_first)

            try_last = last
            lasts = [try_last]
            while (
                last_parent is not None
                and len(last.tail or "") == 0
                and last_parent.index(try_last) == len(last_parent) - 1
            ):
                try_last = last_parent
                last_parent = try_last.getparent()

                if last_parent is not None:
                    lasts.append(try_last)

            found = False
            for try_first in firsts:
                for try_last in lasts:
                    if try_first.getparent() == try_last.getparent():
                        first = try_first
                        last = try_last
                        found = True
                        break

                if found:
                    break

            else:
                log.info("first: %s" % etree.tostring(first))
                log.info("last: %s" % etree.tostring(last))
                log.error(
                    "%s style event first and last have different parents: offset %d len %d: %s"
                    % (
                        self.content_context,
                        event_offset,
                        event_length,
                        etree.tostring(content_elem),
                    )
                )
                return None

        event_elem = etree.Element("span")

        se_parent = first.getparent()
        first_index = se_parent.index(first)

        for i in range(first_index, se_parent.index(last) + 1):
            e = se_parent[first_index]
            se_parent.remove(e)
            event_elem.append(e)

        se_parent.insert(first_index, event_elem)

        return event_elem

    def get_ruby_content(self, ruby_name, ruby_id):
        if "$756" not in self.book_data or ruby_name not in self.book_data["$756"]:
            raise Exception("Missing ruby_content: %s" % ruby_name)

        for ruby_content in self.book_data["$756"][ruby_name]["$146"]:
            if ion_type(ruby_content) is IonSymbol:
                ruby_content = self.get_fragment(
                    ftype="$608", fid=ruby_content, delete=False
                )

            if ruby_content["$758"] == ruby_id:
                return ruby_content.copy()

        raise Exception("Missing ruby_id %d in ruby_content: %s" % (ruby_id, ruby_name))

    def is_inline_only(self, elem):
        if elem.tag == SVG:
            return True

        if elem.tag not in {
            "a",
            "audio",
            "img",
            "rb",
            "rt",
            "ruby",
            "span",
            SVG,
            "video",
        }:
            return False

        for e in elem:
            if not self.is_inline_only(e):
                return False

        return True

    @property
    def content_context(self):
        return ", ".join(self.context_)

    def push_context(self, context):
        self.context_.append(context)

    def pop_context(self):
        self.context_.pop()
