from __future__ import absolute_import, division, print_function, unicode_literals

import operator
import re

from lxml import etree

from .epub_output import SVG, SVG_NAMESPACES, SVG_NS_URI, XLINK_NS_URI, qname
from .ion import IonSExp, IonStruct, IonSymbol, ion_type
from .ion_symbol_table import LocalSymbolTable
from .ion_text import IonText
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import get_url_filename, type_name, urlabspath, urlrelpath
from .yj_to_epub_properties import value_str
from .yj_versions import KNOWN_SUPPORTED_FEATURES

if IS_PYTHON2:
    from .python_transition import repr, str, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEVICE_SCREEN_NARROW_PX = 1200
DEVICE_SCREEN_WIDE_PX = 1920

RENDER_HTML_PLUGIN_AS = "iframe"


class KFX_EPUB_Misc(object):
    def set_condition_operators(self):
        if self.epub.orientation_lock == "landscape":
            screen_width = DEVICE_SCREEN_WIDE_PX
            screen_height = DEVICE_SCREEN_NARROW_PX
        else:
            screen_width = DEVICE_SCREEN_NARROW_PX
            screen_height = DEVICE_SCREEN_WIDE_PX

        self.condition_operators = {
            "$305": (0, screen_height),
            "$304": (0, screen_width),
            "$300": (0, True),
            "$301": (0, True),
            "$183": (0, 0),
            "$302": (0, screen_width),
            "$303": (0, screen_height),
            "$525": (0, (screen_width > screen_height)),
            "$526": (0, (screen_width < screen_height)),
            "$660": (0, True),
            "$293": (1, operator.not_),
            "$266": (1, None),
            "$750": (1, None),
            "$659": (None, None),
            "$292": (2, operator.and_),
            "$291": (2, operator.or_),
            "$294": (2, operator.eq),
            "$295": (2, operator.ne),
            "$296": (2, operator.gt),
            "$297": (2, operator.ge),
            "$298": (2, operator.lt),
            "$299": (2, operator.le),
            "$516": (2, operator.add),
            "$517": (2, operator.sub),
            "$518": (2, operator.mul),
            "$519": (2, operator.truediv),
        }

    def evaluate_binary_condition(self, condition):
        value = self.evaluate_condition(condition)
        if value not in {True, False}:
            log.error(
                "Condition has non-binary result (%s): %s"
                % (str(value), str(condition))
            )
            return False

        return value

    def evaluate_condition(self, condition):
        if ion_type(condition) is IonSExp:
            op = condition[0]
            num = len(condition) - 1
        else:
            op = condition
            num = 0

        if (ion_type(op) is not IonSymbol) or (op not in self.condition_operators):
            log.error("Condition operator is unknown: %s" % str(condition))
            return False

        nargs, func = self.condition_operators[op]

        if nargs is None:
            if op == "$659":
                if tuple(condition[1:]) in KNOWN_SUPPORTED_FEATURES:
                    return True

                log.error("yj.supports feature unknown: %s" % repr(condition))
                return False

        if nargs != num:
            log.error(
                "Condition operator has wrong number of arguments: %s" % str(condition)
            )
            return False

        if nargs == 0:
            return func

        if nargs == 1:
            if op == "$266":
                return 0

            if op == "$750":
                if condition[1] == "$752":
                    return True

                if condition[1] == "$753":
                    return False

                log.error("yj.layout_type unknown: %s" % condition[1])
                return False

            return func(self.evaluate_condition(condition[1]))

        return func(
            self.evaluate_condition(condition[1]), self.evaluate_condition(condition[2])
        )

    def add_svg_wrapper_to_block_image(
        self, content_elem, book_part, fixed_height=0, fixed_width=0
    ):
        if len(content_elem) != 1:
            log.error(
                "Incorrect div content for SVG wrapper: %s"
                % etree.tostring(content_elem)
            )

        for image_div in content_elem.findall("*"):
            if (
                image_div.tag == "div"
                and len(image_div) == 1
                and image_div[0].tag == "img"
            ):
                div_style = self.get_style(image_div)
                div_style.pop("-kfx-style-name", "")
                div_style.pop("font-size", "")
                div_style.pop("line-height", "")

                img = image_div[0]
                img_style = self.get_style(img)
                img_style.pop("-kfx-style-name", "")
                img_style.pop("font-size", "")
                img_style.pop("line-height", "")
                iheight = img_style.pop("height", "")
                iwidth = img_style.pop("width", "")
                try:
                    img_file = self.epub.oebps_files[
                        get_url_filename(
                            urlabspath(img.get("src"), ref_from=book_part.filename)
                        )
                    ]

                    img_height = img_file.height
                    img_width = img_file.width
                except Exception as e:
                    print(f"Error {str(e)}")
                    return

                orig_int_height = int_height = px_to_int(iheight)
                orig_int_width = int_width = px_to_int(iwidth)

                if (int_height and fixed_height and int_height != fixed_height) or (
                    int_width and fixed_width and int_width != fixed_width
                ):
                    log.error(
                        "Unexpected image style for SVG wrapper (fixed h=%d, w=%d): %s"
                        % (fixed_height, fixed_width, etree.tostring(image_div))
                    )

                if int_height and int_width:
                    img_aspect = float(int_height) / float(int_width)
                    svg_aspect = float(img_height) / float(img_width)
                    if abs(img_aspect - svg_aspect) > 0.01:
                        log.error(
                            "Image (h=%d, w=%d) aspect ratio %f does not match SVG wrapper (h=%d, w=%d) %f"
                            % (
                                img_height,
                                img_width,
                                img_aspect,
                                int_height,
                                int_width,
                                svg_aspect,
                            )
                        )
                else:
                    int_height = img_height
                    int_width = img_width

                if not (
                    div_style.pop("text-align", "center") == "center"
                    and div_style.pop("text-indent", "0") == "0"
                    and img_style.pop("position", "absolute") == "absolute"
                    and img_style.pop("top", "0") == "0"
                    and img_style.pop("left", "0") == "0"
                    and (iheight == "" or orig_int_height)
                    and (
                        iwidth == ""
                        or orig_int_width
                        or re.match(r"^(100|9[5-9].*)%$", iwidth)
                    )
                    and len(img_style) == 0
                    and len(div_style) == 0
                ):
                    log.error(
                        "Unexpected image style for SVG wrapper (img h=%d, w=%d): %s"
                        % (img_height, img_width, etree.tostring(image_div))
                    )

                image_div.remove(img)

                svg = etree.SubElement(
                    image_div,
                    SVG,
                    nsmap=SVG_NAMESPACES,
                    attrib={
                        "version": "1.1",
                        "preserveAspectRatio": "xMidYMid meet",
                        "viewBox": "0 0 %d %d" % (int_width, int_height),
                        "height": "100%",
                        "width": "100%",
                    },
                )

                self.move_anchors(img, svg)

                etree.SubElement(
                    svg,
                    qname(SVG_NS_URI, "image"),
                    attrib={
                        qname(XLINK_NS_URI, "href"): img.get("src"),
                        "height": "%d" % int_height,
                        "width": "%d" % int_width,
                    },
                )

            else:
                log.error(
                    "Incorrect image content for SVG wrapper: %s"
                    % etree.tostring(image_div)
                )

    def horizontal_fxl_block_images(self, content_elem, book_part):
        left = 0
        for image_div in content_elem.findall("*"):
            if (
                image_div.tag == "div"
                and len(image_div) == 1
                and image_div[0].tag == "img"
            ):
                img = image_div[0]
                img_file = self.epub.oebps_files[
                    get_url_filename(
                        urlabspath(img.get("src"), ref_from=book_part.filename)
                    )
                ]
                img_style = self.get_style(img)

                if (
                    "position" in img_style
                    or "top" in img_style
                    or "left" in img_style
                    or "height" in img_style
                    or "width" in img_style
                ):
                    log.error(
                        "Unexpected image style for horizontal fxl: %s"
                        % etree.tostring(image_div)
                    )

                img_style["position"] = "absolute"
                img_style["top"] = value_str(0, "px")
                img_style["left"] = value_str(left, "px")
                img_style["height"] = value_str(img_file.height, "px")
                img_style["width"] = value_str(img_file.width, "px")
                self.set_style(img, img_style)

                left += img_file.width

            else:
                log.error(
                    "Incorrect image content for horizontal fxl: %s"
                    % etree.tostring(image_div)
                )

    def process_kvg_shape(self, parent, shape, content_list, book_part, writing_mode):
        shape_type = shape.pop("$159")
        if shape_type == "$273":
            elem = etree.SubElement(
                parent,
                qname(SVG_NS_URI, "path"),
                attrib={"d": self.process_path(shape.pop("$249"))},
            )

        elif shape_type == "$270":
            source = shape.pop("$474")

            for i, content in enumerate(content_list):
                if ion_type(content) is IonSymbol:
                    content = self.get_fragment(ftype="$608", fid=content)

                if content.get("$155") == source or content.get("$598") == source:
                    break
            else:
                log.error("Missing KVG container content ID: %s" % source)
                return

            content_list.pop(i)
            self.process_content(content, parent, book_part, writing_mode)
            elem = parent[-1]

            if elem.tag != "div":
                log.error("Unexpected non-text content in KVG container: %s" % elem.tag)
                return

            elem.tag = qname(SVG_NS_URI, "text")

        else:
            log.error("Unexpected shape type: %s" % shape_type)
            return

        for yj_property_name, svg_attrib in [
            ("$70", "fill"),
            ("$72", "fill-opacity"),
            ("$75", "stroke"),
            ("$77", "stroke-linecap"),
            ("$529", "stroke-linejoin"),
            ("$530", "stroke-miterlimit"),
            ("$76", "stroke-width"),
            ("$98", "transform"),
        ]:
            if yj_property_name in shape:
                elem.set(
                    svg_attrib,
                    self.property_value(
                        yj_property_name, shape.pop(yj_property_name), svg=True
                    ),
                )

        if "stroke" in elem.attrib and "fill" not in elem.attrib:
            elem.set("fill", "none")

        self.check_empty(shape, "shape")

    def process_path(self, path):
        if ion_type(path) is IonStruct:
            path_bundle_name = path.pop("name")
            path_index = path.pop("$403")
            self.check_empty(path, "path")

            if (
                "$692" not in self.book_data
                or path_bundle_name not in self.book_data["$692"]
            ):
                log.error("Missing book path_bundle: %s" % path_bundle_name)
                return ""

            return self.process_path(
                self.book_data["$692"][path_bundle_name]["$693"][path_index]
            )

        p = list(path)
        d = []

        def process_instruction(inst, n_args, pixels=True):
            d.append(inst)

            for j in range(n_args):
                if len(p) == 0:
                    log.error("Incomplete path instruction in %s" % str(path))
                    return

                v = p.pop(0)
                if pixels:
                    v = self.adjust_pixel_value(v)

                d.append(value_str(v))

        while len(p) > 0:
            inst = p.pop(0)
            if inst == 0:
                process_instruction("M", 2)

            elif inst == 1:
                process_instruction("L", 2)

            elif inst == 2:
                process_instruction("Q", 4)

            elif inst == 3:
                process_instruction("C", 6)

            elif inst == 4:
                process_instruction("Z", 0)

            else:
                log.error(
                    "Unexpected path instruction %s in %s" % (str(inst), str(path))
                )
                break

        return " ".join(d)

    def process_polygon(self, path):
        def percent_value_str(v):
            return value_str(v * 100, "%", emit_zero_unit=True)

        d = []

        i = 0
        ln = len(path)
        while i < ln:
            inst = path[i]
            if inst == 0 or inst == 1:
                if i + 3 > ln:
                    log.error("Bad path instruction in %s" % str(path))
                    break

                d.append(
                    "%s %s"
                    % (percent_value_str(path[i + 1]), percent_value_str(path[i + 2]))
                )
                i += 3

            elif inst == 4:
                i += 1

            else:
                log.error(
                    "Unexpected path instruction %s in %s" % (str(inst), str(path))
                )
                break

        return "polygon(%s)" % (", ".join(d))

    def process_transform(self, vals, svg):
        if svg:
            px = ""
            sep = " "
        else:
            px = "px"
            sep = ","

        if len(vals) == 6:
            vals[4] = self.adjust_pixel_value(vals[4])
            vals[5] = self.adjust_pixel_value(vals[5])

            if vals[4:6] == [0.0, 0.0]:
                translate = ""
            else:
                translate = "translate(%s%s%s) " % (
                    value_str(vals[4], px),
                    sep,
                    value_str(vals[5], px),
                )

            if vals[0:4] == [1.0, 0.0, 0.0, 1.0] and translate:
                return translate.strip()

            if vals[1:3] == [0.0, 0.0]:
                if vals[0] == vals[3]:
                    return translate + ("scale(%s)" % value_str(vals[0]))

                return translate + (
                    "scale(%s%s%s)" % (value_str(vals[0]), sep, value_str(vals[3]))
                )

            if vals[0:4] == [0.0, 1.0, -1.0, 0.0]:
                return translate + "rotate(-90deg)"

            if vals[0:4] == [0.0, -1.0, 1.0, 0.0]:
                return translate + "rotate(90deg)"

            if vals[0:4] == [-1.0, 0.0, 0.0, -1.0]:
                return translate + "rotate(180deg)"

            log.error("Unexpected transform matrix: %s" % str(vals))
            return "matrix(%s)" % (sep.join([value_str(v) for v in vals]))

        log.error("Unexpected transform: %s" % str(vals))
        return "?"

    def process_plugin(
        self, resource_name, alt_text, content_elem, book_part, is_html=False
    ):
        res = self.process_external_resource(resource_name, save=False, is_plugin=True)

        if is_html or res.mime == "plugin/kfx-html-article":
            src = urlrelpath(
                self.process_external_resource(
                    resource_name, is_plugin=True, save_referred=True
                ).filename,
                ref_from=book_part.filename,
            )

            if RENDER_HTML_PLUGIN_AS == "iframe":
                content_elem.tag = "iframe"
                content_elem.set("src", src)
                self.add_style(
                    content_elem,
                    {
                        "height": "100%",
                        "width": "100%",
                        "border-bottom-style": "none",
                        "border-left-style": "none",
                        "border-right-style": "none",
                        "border-top-style": "none",
                    },
                )
            elif RENDER_HTML_PLUGIN_AS == "object":
                content_elem.tag = "object"
                content_elem.set("data", src)
                content_elem.set("type", "text/html")
                self.add_style(
                    content_elem,
                    {
                        "height": "100%",
                        "width": "100%",
                        "border-bottom-style": "none",
                        "border-left-style": "none",
                        "border-right-style": "none",
                        "border-top-style": "none",
                    },
                )
            else:
                content_elem.tag = "a"
                content_elem.set("href", src)
                content_elem.text = "[click here to read the content]"

        elif res.format == "$284":
            content_elem.tag = "img"
            content_elem.set(
                "src",
                urlrelpath(
                    self.process_external_resource(resource_name).filename,
                    ref_from=book_part.filename,
                ),
            )
            content_elem.set("alt", alt_text)

        else:
            manifest_raw_media = res.raw_media.decode("utf-8")

            manifest_symtab = LocalSymbolTable(
                context="plugin %s" % resource_name, ignore_undef=True
            )

            try:
                manifest_ = IonText(symtab=manifest_symtab).deserialize_annotated_value(
                    manifest_raw_media, import_symbols=None
                )
            except Exception:
                log.error("Exception processing plugin %s" % resource_name)
                raise

            manifest_symtab.report()
            plugin_type = manifest_.get_annotation()
            manifest = manifest_.value

            if plugin_type == "audio":
                self.process_external_resource(
                    resource_name, save=False, is_plugin=True, process_referred=True
                )

                content_elem.tag = "audio"
                content_elem.set("controls", "")
                src = self.uri_reference(
                    manifest["facets"]["media"]["uri"], manifest_external_refs=True
                )
                content_elem.set("src", urlrelpath(src, ref_from=book_part.filename))

                player = manifest["facets"]["player"]
                for image_refs in ["play_images", "pause_images"]:
                    for uri in player.get(image_refs, []):
                        self.uri_reference(uri, save=False)

            elif plugin_type == "button":
                RENDER_BUTTON_PLUGIN = True
                content_elem.tag = "div"

                for image in manifest["facets"]["images"]:
                    if image["role"] != "upstate":
                        log.warning(
                            "Unknown button image role %s in %s"
                            % (image["role"], resource_name)
                        )

                    if RENDER_BUTTON_PLUGIN:
                        img = etree.SubElement(content_elem, "img")
                        img.set(
                            "src",
                            urlrelpath(
                                self.uri_reference(image["uri"]),
                                ref_from=book_part.filename,
                            ),
                        )
                        img.set("alt", alt_text)
                        self.add_style(img, {"max-width": "100%"})
                    else:
                        self.uri_reference(image["uri"], save=False)

                clicks = manifest["events"]["click"]

                for click in clicks if isinstance(clicks, list) else [clicks]:
                    if click["name"] != "change_state":
                        log.warning(
                            "Unknown button event click name %s in %s"
                            % (click["name"], resource_name)
                        )

                self.process_external_resource(
                    resource_name, is_plugin=True, save=False, process_referred=True
                )

            elif plugin_type == "hyperlink":
                content_elem.tag = "a"
                self.add_style(content_elem, {"height": "100%", "width": "100%"})

                uri = manifest["facets"]["uri"]
                if uri:
                    content_elem.set(
                        "href",
                        urlrelpath(
                            self.uri_reference(uri), ref_from=book_part.filename
                        ),
                    )

            elif plugin_type == "image_sequence":
                content_elem.tag = "div"

                for image in manifest["facets"]["images"]:
                    img = etree.SubElement(content_elem, "img")
                    img.set(
                        "src",
                        urlrelpath(
                            self.uri_reference(image["uri"]),
                            ref_from=book_part.filename,
                        ),
                    )
                    img.set("alt", alt_text)

            elif plugin_type in ["scrollable", "slideshow"]:
                content_elem.tag = "div"

                if manifest["properties"].get("initial_visibility") == "hide":
                    self.add_style(content_elem, {"visibility": "hidden"})

                if "alt_text" in manifest["properties"]:
                    alt_text = manifest["properties"]["alt_text"]

                for child in manifest["facets"]["children"]:
                    self.process_plugin_uri(
                        child["uri"], child["bounds"], content_elem, book_part
                    )

                if plugin_type == "scrollable":
                    self.process_external_resource(
                        resource_name, is_plugin=True, save=False, process_referred=True
                    )

            elif plugin_type == "video":
                content_elem.tag = "video"

                if manifest["properties"].get("user_interaction") == "enabled":
                    content_elem.set("controls", "")

                if (
                    manifest.get("events", {}).get("enter_view", {}).get("name")
                    == "start"
                ):
                    content_elem.set("autoplay", "")

                if (
                    manifest["properties"].get("play_context", {}).get("loop_count", 0)
                    < 0
                ):
                    content_elem.set("loop", "")

                if "poster" in manifest["facets"]:
                    content_elem.set(
                        "poster",
                        urlrelpath(
                            self.uri_reference(manifest["facets"]["poster"]["uri"]),
                            ref_from=book_part.filename,
                        ),
                    )

                if "first_frame" in manifest["facets"]:
                    self.uri_reference(
                        manifest["facets"]["first_frame"]["uri"], save=False
                    )

                alt_text = alt_text or "Cannot display %s content" % plugin_type

                src = self.uri_reference(
                    manifest["facets"]["media"]["uri"], manifest_external_refs=True
                )

                content_elem.set("src", urlrelpath(src, ref_from=book_part.filename))

                dummy_elem = etree.Element("dummy")
                while len(content_elem) > 0:
                    e = content_elem[0]
                    content_elem.remove(e)
                    dummy_elem.append(e)

                self.move_anchors(dummy_elem, content_elem)

            elif plugin_type == "webview":
                self.process_external_resource(
                    resource_name, is_plugin=True, save=False, save_referred=True
                )
                purl = urllib.parse.urlparse(manifest["facets"]["uri"])

                if purl.scheme == "kfx":
                    self.process_plugin(
                        urllib.parse.unquote(purl.netloc + purl.path),
                        alt_text,
                        content_elem,
                        book_part,
                        is_html=True,
                    )
                else:
                    log.error("Unexpected webview plugin URI scheme: %s" % uri)

            elif plugin_type == "zoomable":
                content_elem.tag = "img"
                content_elem.set(
                    "src",
                    urlrelpath(
                        self.uri_reference(manifest["facets"]["media"]["uri"]),
                        ref_from=book_part.filename,
                    ),
                )
                content_elem.set("alt", alt_text)

            else:
                log.error(
                    "Unknown plugin type %s in resource %s"
                    % (plugin_type, resource_name)
                )

                content_elem.tag = "object"
                src = self.process_external_resource(
                    resource_name, is_plugin=True, save_referred=True
                ).filename
                content_elem.set("data", urlrelpath(src, ref_from=book_part.filename))
                content_elem.set("type", self.epub.oebps_files[src].mimetype)

                if len(content_elem) == 0:
                    content_elem.text = (
                        alt_text or "Cannot display %s content" % plugin_type
                    )

    def process_plugin_uri(self, uri, bounds, content_elem, book_part):
        purl = urllib.parse.urlparse(uri)

        if purl.scheme == "kfx":
            child_elem = etree.SubElement(content_elem, "plugin-temp")
            self.process_plugin(
                urllib.parse.unquote(purl.netloc + purl.path), "", child_elem, book_part
            )
            self.process_bounds(child_elem, bounds)
        else:
            log.error("Unexpected plugin URI scheme: %s" % uri)

    def process_bounds(self, elem, bounds):
        for bound, property_name in [
            ("x", "left"),
            ("y", "top"),
            ("h", "height"),
            ("w", "width"),
        ]:
            if bound in bounds:
                bound_value = bounds[bound]
                if ion_type(bound_value) is IonStruct:
                    unit = bound_value.pop("unit")
                    value = value_str(
                        bound_value.pop("value"), "%" if unit == "percent" else unit
                    )
                    self.check_empty(bound_value, "Bound %s value" % property_name)

                    self.add_style(elem, {property_name: value}, replace=True)

                    if bound in ["x", "y"]:
                        self.add_style(elem, {"position": "absolute"})
                else:
                    log.error(
                        "Unexpected bound data type %s: %s"
                        % (type_name(bound), repr(bound))
                    )


def px_to_int(s):
    m = re.match(r"^([0-9]+)(px)?$", s)
    return int(m.group(1)) if m else 0
