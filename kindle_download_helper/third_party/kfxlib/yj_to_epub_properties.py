#!/usr/bin/python
# -*- coding: utf8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import decimal
import functools
import re

from lxml import etree

from .epub_output import EPUB_NS_URI, EPUB_TYPE, MATH, SVG, XML_LANG, XML_NS_URI, qname
from .ion import (
    IonBool,
    IonDecimal,
    IonFloat,
    IonInt,
    IonList,
    IonString,
    IonStruct,
    IonSymbol,
    ion_type,
    isstring,
)
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    get_url_filename,
    list_symbols,
    natural_sort_key,
    remove_duplicates,
    type_name,
    urlabspath,
    urlrelpath,
)

if IS_PYTHON2:
    from .python_transition import repr, str, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


STYLE_TEST = False
KEEP_STYLES_INLINE = False
EMIT_OEB_PAGE_PROPS = False
DETECT_LAYOUT_ENHANCER = False
FIX_PT_TO_PX = True
FIX_PRINT_REPLICA_PIXEL_VALUES = True

REVERSE_INHERITANCE = True
REVERSE_INHERITANCE_FRACTION = 0.90

FIX_NONSTANDARD_FONT_WEIGHT = False

SUPER_SUB_MULT_FACTOR = decimal.Decimal("2.0")

USE_NORMAL_LINE_HEIGHT = True

LINE_HEIGHT_SCALE_FACTOR = decimal.Decimal("1.2")
NORMAL_LINE_HEIGHT_EM = "%sem" % LINE_HEIGHT_SCALE_FACTOR

MINIMUM_LINE_HEIGHT = decimal.Decimal("1.0")

CVT_DIRECTION_PROPERTY_TO_MARKUP = False

DEFAULT_DOCUMENT_FONT_FAMILY = "serif"
DEFAULT_DOCUMENT_LINE_HEIGHT = (
    "normal" if USE_NORMAL_LINE_HEIGHT else NORMAL_LINE_HEIGHT_EM
)
DEFAULT_DOCUMENT_FONT_SIZE = "1em"

DEFAULT_KC_COMIC_FONT_SIZE = "16px"

DEFAULT_CLASS_NAME_PREFIX = "class"

ALPHA_MASK = 0xFF000000


class Prop(object):
    def __init__(self, name, values=None):
        self.name = name
        self.values = values


COLLISIONS = {
    "$352": "always",
    "$652": "queue",
}


BORDER_STYLES = {
    "$349": "none",
    "$328": "solid",
    "$331": "dotted",
    "$330": "dashed",
    "$329": "double",
    "$335": "ridge",
    "$334": "groove",
    "$336": "inset",
    "$337": "outset",
}


LAYOUT_HINT_CLASS_NAMES = {
    "$453": "caption",
    "$282": "figure",
    "$760": "heading",
}


YJ_PROPERTY_INFO = {
    "$479": Prop("background-image"),
    "$480": Prop("-kfx-background-positionx"),
    "$481": Prop("-kfx-background-positiony"),
    "$547": Prop(
        "background-origin",
        {
            "$378": "border-box",
            "$377": "content-box",
            "$379": "padding-box",
        },
    ),
    "$484": Prop(
        "background-repeat",
        {
            "$487": "no-repeat",
            "$485": "repeat-x",
            "$486": "repeat-y",
        },
    ),
    "$482": Prop("-kfx-background-sizex"),
    "$483": Prop("-kfx-background-sizey"),
    "$31": Prop("-kfx-baseline-shift"),
    "$44": Prop(
        "-kfx-baseline-style",
        {
            "$60": "bottom",
            "$320": "middle",
            "$350": "baseline",
            "$371": "sub",
            "$370": "super",
            "$449": "text-bottom",
            "$447": "text-top",
            "$58": "top",
        },
    ),
    "$682": Prop(
        "direction",
        {
            "$376": "ltr",
            "$375": "rtl",
        },
    ),
    "$674": Prop(
        "unicode-bidi",
        {
            "$675": "embed",
            "$676": "isolate",
            "$678": "isolate-override",
            "$350": "normal",
            "$677": "bidi-override",
            "$679": "plaintext",
        },
    ),
    "$83": Prop("border-color"),
    "$86": Prop("border-bottom-color"),
    "$85": Prop("border-left-color"),
    "$87": Prop("border-right-color"),
    "$84": Prop("border-top-color"),
    "$461": Prop("border-bottom-left-radius"),
    "$462": Prop("border-bottom-right-radius"),
    "$459": Prop("border-top-left-radius"),
    "$460": Prop("border-top-right-radius"),
    "$457": Prop("-webkit-border-horizontal-spacing"),
    "$456": Prop("-webkit-border-vertical-spacing"),
    "$88": Prop("border-style", BORDER_STYLES),
    "$91": Prop("border-bottom-style", BORDER_STYLES),
    "$90": Prop("border-left-style", BORDER_STYLES),
    "$92": Prop("border-right-style", BORDER_STYLES),
    "$89": Prop("border-top-style", BORDER_STYLES),
    "$93": Prop("border-width"),
    "$96": Prop("border-bottom-width"),
    "$95": Prop("border-left-width"),
    "$97": Prop("border-right-width"),
    "$94": Prop("border-top-width"),
    "$60": Prop("bottom"),
    "$580": Prop(
        "-kfx-box-align",
        {
            "$320": "center",
            "$59": "left",
            "$61": "right",
        },
    ),
    "$133": Prop(
        "page-break-after",
        {
            "$352": "always",
            "$383": "auto",
            "$353": "avoid",
        },
    ),
    "$134": Prop(
        "page-break-before",
        {
            "$352": "always",
            "$383": "auto",
            "$353": "avoid",
        },
    ),
    "$135": Prop(
        "page-break-inside",
        {
            "$383": "auto",
            "$353": "avoid",
        },
    ),
    "$708": Prop(
        "-kfx-character-width",
        {
            "$383": None,
        },
    ),
    "$476": Prop(
        "overflow",
        {
            False: "visible",
            True: "hidden",
        },
    ),
    "$112": Prop(
        "column-count",
        {
            "$383": "auto",
        },
    ),
    "$116": Prop("column-rule-color"),
    "$192": Prop(
        "direction",
        {
            "$376": "ltr",
            "$375": "rtl",
        },
    ),
    "$99": Prop(
        "box-decoration-break",
        {
            False: "slice",
            True: "clone",
        },
    ),
    "$73": Prop(
        "background-clip",
        {
            "$378": "border-box",
            "$377": "content-box",
            "$379": "padding-box",
        },
    ),
    "$70": Prop("-kfx-fill-color"),
    "$72": Prop("-kfx-fill-opacity"),
    "$140": Prop(
        "float",
        {
            "$59": "left",
            "$61": "right",
            "$786": "snap-block",
        },
    ),
    "$11": Prop("font-family"),
    "$16": Prop("font-size"),
    "$15": Prop(
        "font-stretch",
        {
            "$365": "condensed",
            "$368": "expanded",
            "$350": "normal",
            "$366": "semi-condensed",
            "$367": "semi-expanded",
        },
    ),
    "$12": Prop(
        "font-style",
        {
            "$382": "italic",
            "$350": "normal",
            "$381": "oblique",
        },
    ),
    "$13": Prop(
        "font-weight",
        {
            "$361": "bold",
            "$363": "900",
            "$357": "300",
            "$359": "500",
            "$350": "normal",
            "$360": "600",
            "$355": "100",
            "$362": "800",
            "$356": "200",
        },
    ),
    "$583": Prop("font-variant", {"$349": "normal", "$369": "small-caps"}),
    "$57": Prop("height"),
    "$458": Prop(
        "empty-cells",
        {
            False: "show",
            True: "hide",
        },
    ),
    "$127": Prop(
        "hyphens",
        {
            "$383": "auto",
            "$384": "manual",
            "$349": "none",
        },
    ),
    "$785": Prop("-kfx-keep-lines-together"),
    "$10": Prop("-kfx-attrib-xml-lang"),
    "$761": Prop("-kfx-layout-hints"),
    "$59": Prop("left"),
    "$32": Prop("letter-spacing"),
    "$780": Prop(
        "line-break",
        {
            "$783": "anywhere",
            "$383": "auto",
            "$781": "loose",
            "$350": "normal",
            "$782": "strict",
        },
    ),
    "$42": Prop(
        "line-height",
        {
            "$383": "normal",
        },
    ),
    "$577": Prop("-kfx-link-color"),
    "$576": Prop("-kfx-visited-color"),
    "$100": Prop(
        "list-style-type",
        {
            "$346": "lower-alpha",
            "$347": "upper-alpha",
            "$342": "circle",
            "$737": "cjk-earthly-branch",
            "$738": "cjk-heavenly-stem",
            "$736": "cjk-ideographic",
            "$796": "decimal-leading-zero",
            "$340": "disc",
            "$795": "georgian",
            "$739": "hiragana",
            "$740": "hiragana-iroha",
            "$271": None,
            "$743": "japanese-formal",
            "$744": "japanese-informal",
            "$741": "katakana",
            "$742": "katakana-iroha",
            "$793": "lower-armenian",
            "$791": "lower-greek",
            "$349": "none",
            "$343": "decimal",
            "$344": "lower-roman",
            "$345": "upper-roman",
            "$746": "simp-chinese-formal",
            "$745": "simp-chinese-informal",
            "$341": "square",
            "$748": "trad-chinese-formal",
            "$747": "trad-chinese-informal",
            "$794": "upper-armenian",
            "$792": "upper-greek",
        },
    ),
    "$503": Prop("list-style-image"),
    "$551": Prop(
        "list-style-position",
        {
            "$552": "inside",
            "$553": "outside",
        },
    ),
    "$46": Prop("margin"),
    "$49": Prop("margin-bottom"),
    "$48": Prop("margin-left"),
    "$50": Prop("margin-right"),
    "$47": Prop("margin-top"),
    "$64": Prop("max-height"),
    "$65": Prop("max-width"),
    "$62": Prop("min-height"),
    "$63": Prop("min-width"),
    "$45": Prop(
        "white-space",
        {
            False: "normal",
            True: "nowrap",
        },
    ),
    "$105": Prop("outline-color"),
    "$106": Prop("outline-offset"),
    "$107": Prop("outline-style", BORDER_STYLES),
    "$108": Prop("outline-width"),
    "$554": Prop(
        "text-decoration",
        {
            "$330": "overline dashed",
            "$331": "overline dotted",
            "$329": "overline double",
            "$349": None,
            "$328": "overline",
        },
    ),
    "$555": Prop("text-decoration-color"),
    "$51": Prop("padding"),
    "$54": Prop("padding-bottom"),
    "$53": Prop("padding-left"),
    "$55": Prop("padding-right"),
    "$52": Prop("padding-top"),
    "$183": Prop(
        "position",
        {
            "$324": "absolute",
            "$455": "oeb-page-foot",
            "$151": "oeb-page-head",
            "$488": "relative",
            "$489": "fixed",
        },
    ),
    "$61": Prop("right"),
    "$766": Prop(
        "ruby-align",
        {
            "$320": "center",
            "$773": "space-around",
            "$774": "space-between",
            "$680": "start",
        },
    ),
    "$764": Prop(
        "ruby-merge",
        {
            "$772": "collapse",
            "$771": "separate",
        },
    ),
    "$762": Prop(
        "ruby-position",
        {
            "$60": "under",
            "$58": "over",
        },
    ),
    "$763": Prop(
        "ruby-position",
        {
            "$59": "under",
            "$61": "over",
        },
    ),
    "$765": Prop(
        "ruby-align",
        {
            "$320": "center",
            "$773": "space-around",
            "$774": "space-between",
            "$680": "start",
        },
    ),
    "$496": Prop("box-shadow"),
    "$546": Prop(
        "box-sizing",
        {
            "$378": "border-box",
            "$377": "content-box",
            "$379": "padding-box",
        },
    ),
    "src": Prop("src"),
    "$27": Prop(
        "text-decoration",
        {
            "$330": "line-through dashed",
            "$331": "line-through dotted",
            "$329": "line-through double",
            "$349": None,
            "$328": "line-through",
        },
    ),
    "$28": Prop("text-decoration-color"),
    "$75": Prop("-webkit-text-stroke-color"),
    "$77": Prop(
        "-svg-stroke-linecap",
        {
            "$534": "butt",
            "$533": "round",
            "$341": "square",
        },
    ),
    "$529": Prop(
        "-svg-stroke-linejoin",
        {
            "$536": "bevel",
            "$535": "miter",
            "$533": "round",
        },
    ),
    "$530": Prop("-svg-stroke-miterlimit"),
    "$76": Prop("-webkit-text-stroke-width"),
    "$173": Prop("-kfx-style-name"),
    "$150": Prop(
        "border-collapse",
        {
            False: "separate",
            True: "collapse",
        },
    ),
    "$148": Prop("-kfx-attrib-colspan"),
    "$149": Prop("-kfx-attrib-rowspan"),
    "$34": Prop(
        "text-align",
        {
            "$320": "center",
            "$321": "justify",
            "$59": "left",
            "$61": "right",
        },
    ),
    "$35": Prop(
        "text-align-last",
        {
            "$383": "auto",
            "$320": "center",
            "$681": "end",
            "$321": "justify",
            "$59": "left",
            "$61": "right",
            "$680": "start",
        },
    ),
    "$21": Prop("background-color"),
    "$528": Prop("background-image"),
    "$19": Prop("color"),
    "$707": Prop(
        "text-combine-upright",
        {
            "$573": "all",
        },
    ),
    "$718": Prop("text-emphasis-color"),
    "$719": Prop(
        "-kfx-text-emphasis-position-horizontal",
        {
            "$58": "over",
            "$60": "under",
        },
    ),
    "$720": Prop(
        "-kfx-text-emphasis-position-vertical",
        {
            "$59": "left",
            "$61": "right",
        },
    ),
    "$717": Prop(
        "text-emphasis-style",
        {
            "$724": "filled",
            "$728": "filled circle",
            "$726": "filled dot",
            "$730": "filled double-circle",
            "$734": "filled sesame",
            "$732": "filled triangle",
            "$725": "open",
            "$729": "open circle",
            "$727": "open dot",
            "$731": "open double-circle",
            "$735": "open sesame",
            "$733": "open triangle",
        },
    ),
    "$706": Prop(
        "text-orientation",
        {
            "$383": "mixed",
            "$778": "sideways",
            "$779": "upright",
        },
    ),
    "$36": Prop("text-indent"),
    "$41": Prop(
        "text-transform",
        {
            "$373": "lowercase",
            "$349": "none",
            "$374": "capitalize",
            "$372": "uppercase",
        },
    ),
    "$497": Prop("text-shadow"),
    "$58": Prop("top"),
    "$98": Prop("transform"),
    "$549": Prop("transform-origin"),
    "$23": Prop(
        "text-decoration",
        {
            "$330": "underline dashed",
            "$331": "underline dotted",
            "$329": "underline double",
            "$349": None,
            "$328": "underline",
        },
    ),
    "$24": Prop("text-decoration-color"),
    "$68": Prop("visibility", {False: "hidden", True: "visible"}),
    "$716": Prop(
        "white-space",
        {
            "$715": "nowrap",
        },
    ),
    "$56": Prop("width"),
    "$569": Prop(
        "word-break",
        {
            "$570": "break-all",
            "$350": "normal",
        },
    ),
    "$33": Prop("word-spacing"),
    "$560": Prop(
        "writing-mode",
        {"$557": "horizontal-tb", "$559": "vertical-rl", "$558": "vertical-lr"},
    ),
    "$650": Prop("-amzn-shape-outside"),
    "$646": Prop("-kfx-collision"),
    "$616": Prop("-kfx-attrib-epub-type", {"$617": "noteref"}),
    "$658": Prop(
        "yj-float-align",
        {
            "$58": None,
        },
    ),
    "$672": Prop(
        "yj-float-bias",
        {
            "$671": None,
        },
    ),
    "$628": Prop(
        "clear",
        {
            "$59": "left",
            "$61": "right",
            "$421": "both",
            "$349": "none",
        },
    ),
    "$673": Prop("yj-float-to-block", {False: None}),
    "$644": Prop(
        "-amzn-page-footer",
        {
            "$442": "disable",
            "$441": "overlay",
        },
    ),
    "$643": Prop(
        "-amzn-page-header",
        {
            "$442": "disable",
            "$441": "overlay",
        },
    ),
    "$645": Prop("-amzn-max-crop-percentage"),
    "$790": Prop("-kfx-heading-level"),
    "$640": Prop("-kfx-user-margin-bottom-percentage"),
    "$641": Prop("-kfx-user-margin-left-percentage"),
    "$642": Prop("-kfx-user-margin-right-percentage"),
    "$639": Prop("-kfx-user-margin-top-percentage"),
    "$633": Prop(
        "-kfx-table-vertical-align",
        {
            "$350": "baseline",
            "$60": "bottom",
            "$320": "middle",
            "$58": "top",
        },
    ),
    "$649": Prop(
        "-kfx-attrib-epub-type",
        {
            "$442": "amzn:decorative",
            "$441": "amzn:not-decorative",
        },
    ),
    "$788": Prop(
        "page-break-after",
        {
            "$352": "always",
            "$383": "auto",
            "$353": "avoid",
        },
    ),
    "$789": Prop(
        "page-break-before",
        {
            "$352": "always",
            "$383": "auto",
            "$353": "avoid",
        },
    ),
}

YJ_PROPERTY_NAMES = set(YJ_PROPERTY_INFO.keys())


YJ_LENGTH_UNITS = {
    "$506": "ch",
    "$315": "cm",
    "$308": "em",
    "$309": "ex",
    "$317": "in",
    "$310": "lh",
    "$316": "mm",
    "$314": "%",
    "$318": "pt",
    "$319": "px",
    "$505": "rem",
    "$312": "vh",
    "$507": "vmax",
    "$313": "vmin",
    "$311": "vw",
}


COLOR_YJ_PROPERTIES = {
    "$83",
    "$86",
    "$85",
    "$87",
    "$84",
    "$116",
    "$498",
    "$70",
    "$121",
    "$105",
    "$555",
    "$28",
    "$75",
    "$21",
    "$19",
    "$718",
    "$24",
}

COLOR_NAME = {
    "#000000": "black",
    "#000080": "navy",
    "#0000ff": "blue",
    "#008000": "green",
    "#008080": "teal",
    "#00ff00": "lime",
    "#00ffff": "cyan",
    "#800000": "maroon",
    "#800080": "purple",
    "#808000": "olive",
    "#808080": "gray",
    "#ff0000": "red",
    "#ff00ff": "magenta",
    "#ffff00": "yellow",
    "#ffffff": "white",
}

COLOR_NAMES = set(COLOR_NAME.values())

COLOR_HEX = {}
for h, n in COLOR_NAME.items():
    COLOR_HEX[n] = h


GENERIC_FONT_NAMES = {
    "serif",
    "sans-serif",
    "cursive",
    "fantasy",
    "monospace",
    "Arial",
    "Caecilia",
    "Courier",
    "Georgia",
    "Lucida",
    "Times New Roman",
    "Trebuchet",
    "Amazon Ember",
    "Amazon Ember Bold",
    "Baskerville",
    "Bookerly",
    "Caecilia",
    "Caecilia Condensed",
    "Futura",
    "Helvetica",
    "OpenDyslexic",
    "Palatino",
    "Helvetica Light",
    "Helvetica Neue LT",
    "Noto Sans",
    "明朝",
    "ゴシック",
    "Source Code Pro",
    "Droid Sans",
    "Droid Serif",
    "Verdana",
    "Book Antiqua",
    "Calibri",
    "Calibri Light",
    "Cambria",
    "Comic Sans MS",
    "Courier New",
    "Lucida Sans Unicode",
    "Palatino Linotype",
    "Tahoma",
    "Trebuchet MS",
    "CCL",
    "Helvetica Neue",
    "Malabar",
    "Merriweather",
    "Sorts Mill Goudy",
    "Code2000",
    "Palatino LT Std",
    "Times",
    "ＭＳ 明朝",
    "@ＭＳ 明朝",
    "MS Mincho",
    "@MS Mincho",
    "AmazonEmber Medium",
    "Bookerly Italic",
    "BookerlyDisplay Regular",
}

DEFAULT_FONT_NAMES = {"default", "$amzn_fixup_default_font$"}


MISSPELLED_FONT_NAMES = {
    "san-serif": "sans-serif",
    "ariel": "Arial",
}


KNOWN_STYLES = {
    "-amzn-float": {"bottom", "top", "top,bottom"},
    "-amzn-max-crop-percentage": {"0 0 0 0"},
    "-amzn-page-align": {
        "all",
        "bottom",
        "bottom,left",
        "bottom,left,right",
        "bottom,right",
        "left",
        "left,right",
        "right",
        "top",
        "top,bottom,left",
        "top,bottom,right",
        "top,left",
        "top,left,right",
        "top,right",
    },
    "-amzn-page-footer": {"disable"},
    "-amzn-page-header": {"disable"},
    "-amzn-shape-outside": {"*"},
    "-webkit-border-horizontal-spacing": {"0"},
    "-webkit-border-vertical-spacing": {"0"},
    "-webkit-box-decoration-break": {"clone", "slice"},
    "-webkit-hyphens": {"auto", "manual", "none"},
    "-webkit-line-break": {"anywhere", "auto", "loose", "normal", "strict"},
    "-webkit-ruby-position": {"over", "under"},
    "-webkit-text-combine": {"horizontal", "none"},
    "-webkit-text-emphasis-color": {"#0"},
    "-webkit-text-emphasis-position": {"over right", "under left"},
    "-webkit-text-emphasis-style": {
        "filled",
        "filled circle",
        "filled dot",
        "filled double-circle",
        "filled sesame",
        "filled triangle",
        "open",
        "open circle",
        "open dot",
        "open double-circle",
        "open sesame",
        "open triangle",
    },
    "-webkit-text-orientation": {"mixed", "sideways", "upright"},
    "-webkit-text-stroke-color": {"#0"},
    "-webkit-text-stroke-width": {"0"},
    "-webkit-transform": {"*"},
    "-webkit-transform-origin": {"0 0"},
    "-webkit-writing-mode": {"horizontal-tb", "vertical-lr", "vertical-rl"},
    "background-clip": {"border-box", "content-box", "padding-box"},
    "background-color": {"#0"},
    "background-image": {"*"},
    "background-origin": {"border-box", "content-box"},
    "background-position": {"0 0"},
    "background-size": {"0 0", "auto 0", "0 auto", "contain", "cover"},
    "background-repeat": {"no-repeat", "repeat-x", "repeat-y"},
    "border-bottom-color": {"#0"},
    "border-bottom-left-radius": {"0"},
    "border-bottom-right-radius": {"0"},
    "border-bottom-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "border-bottom-width": {"0"},
    "border-collapse": {"collapse", "separate"},
    "border-color": {"#0"},
    "border-left-color": {"#0"},
    "border-left-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "border-left-width": {"0"},
    "border-right-color": {"#0"},
    "border-right-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "border-right-width": {"0"},
    "border-spacing": {"0 0"},
    "border-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "border-top-color": {"#0"},
    "border-top-left-radius": {"0"},
    "border-top-right-radius": {"0"},
    "border-top-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "border-top-width": {"0"},
    "border-width": {"0"},
    "bottom": {"0"},
    "box-decoration-break": {"clone", "slice"},
    "box-shadow": {
        "0 0 #0",
        "0 0 #0 inset",
        "0 0 0 #0",
        "0 0 0 #0 inset",
        "0 0 0 0 #0",
        "0 0 0 0 #0 inset",
    },
    "box-sizing": {"border-box", "content-box"},
    "clear": {"both", "left", "none", "right"},
    "color": {"#0"},
    "column-count": {"0", "auto"},
    "direction": {"ltr", "rtl"},
    "display": {
        "block",
        "inline",
        "inline-block",
        "none",
        "oeb-page-foot",
        "oeb-page-head",
        "inline-table",
    },
    "float": {"left", "right", "snap-block"},
    "font-family": {"*"},
    "font-size": {"0"},
    "font-style": {"italic", "normal", "oblique"},
    "font-variant": {"normal", "small-caps"},
    "font-weight": {"0", "bold", "normal"},
    "height": {"0"},
    "hyphens": {"auto", "manual", "none"},
    "left": {"0"},
    "letter-spacing": {"0", "normal"},
    "line-break": {"anywhere", "auto", "loose", "normal", "strict"},
    "line-height": {"0", "normal"},
    "list-style-image": {"*"},
    "list-style-position": {"inside", "outside"},
    "list-style-type": {
        "circle",
        "cjk-ideographic",
        "decimal",
        "decimal-leading-zero",
        "disc",
        "georgian",
        "katakana",
        "katakana-iroha",
        "lower-alpha",
        "lower-armenian",
        "lower-greek",
        "lower-roman",
        "none",
        "square",
        "upper-alpha",
        "upper-armenian",
        "upper-greek",
        "upper-roman",
    },
    "margin": {"0"},
    "margin-bottom": {"0"},
    "margin-left": {"0", "auto"},
    "margin-right": {"0", "auto"},
    "margin-top": {"0"},
    "max-height": {"0"},
    "max-width": {"0"},
    "min-height": {"0"},
    "min-width": {"0"},
    "orphans": {"0"},
    "outline-color": {"#0"},
    "outline-offset": {"0"},
    "outline-style": {
        "dashed",
        "dotted",
        "double",
        "groove",
        "inset",
        "none",
        "outset",
        "ridge",
        "solid",
    },
    "outline-width": {"0"},
    "overflow": {"hidden"},
    "padding": {"0"},
    "padding-bottom": {"0"},
    "padding-left": {"0"},
    "padding-right": {"0"},
    "padding-top": {"0"},
    "page-break-after": {"always", "auto", "avoid"},
    "page-break-before": {"always", "auto", "avoid"},
    "page-break-inside": {"auto", "avoid"},
    "position": {"absolute", "fixed", "relative"},
    "right": {"0"},
    "ruby-align": {"center", "space-around", "space-between", "start"},
    "ruby-position": {"over", "under"},
    "src": {"*"},
    "text-align": {"center", "justify", "left", "right"},
    "text-align-last": {"auto", "center", "end", "justify", "left", "right", "start"},
    "text-combine-upright": {"all", "none"},
    "text-decoration": {
        "line-through",
        "none !important",
        "overline",
        "underline",
        "overline dashed",
        "overline dotted",
        "overline double",
        "underline dashed",
        "underline dotted",
        "underline double",
        "line-through dashed",
        "line-through dotted",
        "line-through double",
        "overline underline",
        "line-through overline",
        "line-through underline",
        "line-through overline underline",
    },
    "text-decoration-color": {"#0"},
    "text-emphasis-color": {"#0"},
    "text-emphasis-position": {"over right", "under left"},
    "text-emphasis-style": {
        "filled",
        "filled circle",
        "filled dot",
        "filled double-circle",
        "filled sesame",
        "filled triangle",
        "open",
        "open circle",
        "open dot",
        "open double-circle",
        "open sesame",
        "open triangle",
    },
    "text-indent": {"0"},
    "text-orientation": {"mixed", "sideways", "upright"},
    "text-shadow": {"*"},
    "text-transform": {"capitalize", "none", "lowercase", "uppercase"},
    "top": {"0"},
    "transform": {"*"},
    "transform-origin": {"0 0"},
    "unicode-bidi": {
        "bidi-override",
        "embed",
        "isolate",
        "isolate-override",
        "normal",
        "plaintext",
    },
    "vertical-align": {
        "0",
        "baseline",
        "bottom",
        "middle",
        "sub",
        "super",
        "text-bottom",
        "text-top",
        "top",
    },
    "visibility": {"hidden", "visible"},
    "white-space": {"normal", "nowrap"},
    "widows": {"0"},
    "width": {"0"},
    "word-break": {"break-all", "normal"},
    "word-spacing": {"0", "normal"},
    "writing-mode": {"horizontal-tb", "vertical-lr", "vertical-rl"},
    "z-index": {"0"},
}


ARBITRARY_VALUE_PROPERTIES = {
    "-amzn-shape-outside",
    "-kfx-attrib-xml-lang",
    "-kfx-layout-hints",
    "-kfx-style-name",
    "background-image",
    "font-family",
    "list-style-image",
    "src",
}


COMPOSITE_SIDE_STYLES = [
    [
        "border-color",
        [
            "border-bottom-color",
            "border-left-color",
            "border-right-color",
            "border-top-color",
        ],
    ],
    [
        "border-style",
        [
            "border-bottom-style",
            "border-left-style",
            "border-right-style",
            "border-top-style",
        ],
    ],
    [
        "border-width",
        [
            "border-bottom-width",
            "border-left-width",
            "border-right-width",
            "border-top-width",
        ],
    ],
    ["margin", ["margin-bottom", "margin-left", "margin-right", "margin-top"]],
    ["padding", ["padding-bottom", "padding-left", "padding-right", "padding-top"]],
]

CONFLICTING_PROPERTIES = {
    "background": {
        "background-attachment",
        "background-clip",
        "background-color",
        "background-image",
        "background-origin",
        "background-position",
        "background-repeat",
        "background-size",
    },
    "border-color": {
        "border-bottom-color",
        "border-left-color",
        "border-right-color",
        "border-top-color",
    },
    "border-style": {
        "border-bottom-style",
        "border-left-style",
        "border-right-style",
        "border-top-style",
    },
    "border-width": {
        "border-bottom-width",
        "border-left-width",
        "border-right-width",
        "border-top-width",
    },
    "font": {"font-family", "font-size", "font-style", "font-variant", "font-weight"},
    "list-style": {"list-style-type", "list-style-position", "list-style-image"},
    "margin": {"margin-bottom", "margin-left", "margin-right", "margin-top"},
    "outline": {"outline-width", "outline-style", "outline-color"},
    "padding": {"padding-bottom", "padding-left", "padding-right", "padding-top"},
}

for name, conf_set in list(CONFLICTING_PROPERTIES.items()):
    for conf in conf_set:
        if conf not in CONFLICTING_PROPERTIES:
            CONFLICTING_PROPERTIES[conf] = set()

        CONFLICTING_PROPERTIES[conf].add(name)


ALTERNATE_EQUIVALENT_PROPERTIES = {
    "box-decoration-break": "-webkit-box-decoration-break",
    "hyphens": "-webkit-hyphens",
    "line-break": "-webkit-line-break",
    "ruby-position": "-webkit-ruby-position",
    "text-combine-upright": "-webkit-text-combine",
    "text-emphasis-color": "-webkit-text-emphasis-color",
    "text-emphasis-position": "-webkit-text-emphasis-position",
    "text-emphasis-style": "-webkit-text-emphasis-style",
    "text-orientation": "-webkit-text-orientation",
    "transform": "-webkit-transform",
    "transform-origin": "-webkit-transform-origin",
    "writing-mode": "-webkit-writing-mode",
}


HERITABLE_DEFAULT_PROPERTIES = {
    "-amzn-page-align": "none",
    "-kfx-attrib-xml-lang": None,
    "-kfx-link-color": None,
    "-kfx-user-margin-bottom-percentage": "100",
    "-kfx-user-margin-left-percentage": "100",
    "-kfx-user-margin-right-percentage": "100",
    "-kfx-user-margin-top-percentage": "100",
    "-kfx-visited-color": None,
    "-webkit-border-horizontal-spacing": "2px",
    "-webkit-border-vertical-spacing": "2px",
    "-webkit-text-stroke-color": None,
    "-webkit-text-stroke-width": "0",
    "border-collapse": "separate",
    "border-spacing": "2px 2px",
    "caption-side": "top",
    "color": None,
    "cursor": "auto",
    "direction": "ltr",
    "empty-cells": "show",
    "font": None,
    "font-family": DEFAULT_DOCUMENT_FONT_FAMILY,
    "font-feature-settings": None,
    "font-language-override": "normal",
    "font-kerning": "auto",
    "font-size": "1rem",
    "font-size-adjust": "none",
    "font-stretch": "normal",
    "font-style": "normal",
    "font-synthesis": "weight style",
    "font-variant": "normal",
    "font-weight": "normal",
    "hanging-punctuation": "none",
    "hyphens": None,
    "letter-spacing": "normal",
    "line-break": "auto",
    "line-height": "normal",
    "list-style": None,
    "list-style-image": "none",
    "list-style-position": "outside",
    "list-style-type": "disc",
    "orphans": "2",
    "overflow-wrap": "normal",
    "quotes": None,
    "ruby-align": "space-around",
    "ruby-merge": "separate",
    "ruby-position": "over",
    "tab-size": "8",
    "text-align": None,
    "text-align-last": "auto",
    "text-combine-upright": "none",
    "text-justify": "auto",
    "text-shadow": "none",
    "text-transform": "none",
    "text-indent": "0",
    "text-orientation": "mixed",
    "text-underline-position": "auto",
    "unicode-bidi": "normal",
    "visibility": "visible",
    "white-space": "normal",
    "widows": "2",
    "word-break": "normal",
    "word-spacing": "normal",
    "word-wrap": "normal",
    "writing-mode": "horizontal-tb",
}

HERITABLE_PROPERTIES = set(HERITABLE_DEFAULT_PROPERTIES.keys())

REVERSE_HERITABLE_PROPERTIES = HERITABLE_PROPERTIES - {
    "-amzn-page-align",
    "-kfx-user-margin-bottom-percentage",
    "-kfx-user-margin-left-percentage",
    "-kfx-user-margin-right-percentage",
    "-kfx-user-margin-top-percentage",
}

NON_HERITABLE_DEFAULT_PROPERTIES = {
    "background-clip": "border-box",
    "background-color": "transparent",
    "background-image": "none",
    "background-origin": "padding-box",
    "background-position": "0% 0%",
    "background-repeat": "repeat",
    "background-size": "auto auto",
    "box-sizing": "content-box",
    "box-decoration-break": "slice",
    "column-count": "auto",
    "float": "none",
    "margin-bottom": "0",
    "margin-left": "0",
    "margin-right": "0",
    "margin-top": "0",
    "overflow": "visible",
    "padding-bottom": "0",
    "padding-left": "0",
    "padding-right": "0",
    "padding-top": "0",
    "page-break-after": "auto",
    "page-break-before": "auto",
    "page-break-inside": "auto",
    "position": "static",
    "text-decoration": "none",
    "text-emphasis-position": "over right",
    "transform": "none",
    "transform-origin": "50% 50% 0",
    "vertical-align": "baseline",
    "z-index": "auto",
}


RESET_CSS_DATA = (
    "html {color: #000; background: #FFF;}\n"
    + "body,div,dl,dt,dd,ul,ol,li,h1,h2,h3,h4,h5,h6,th,td {margin: 0; padding: 0;}\n"
    + "table {border-collapse: collapse; border-spacing: 0;}\n"
    + "fieldset,img {border: 0;}\n"
    + "caption,th,var {font-style: normal; font-weight: normal;}\n"
    + "li {list-style: none;}\n"
    + "caption,th {text-align: left;}\n"
    + "h1,h2,h3,h4,h5,h6 {font-size: 100%; font-weight: normal;}\n"
    + "sup {vertical-align: text-top;}\n"
    + "sub {vertical-align: text-bottom;}\n"
    + "a.app-amzn-magnify {display: block; width: 100%; height: 100%;}\n"
)


AMAZON_SPECIAL_CLASSES = [
    "app-amzn-magnify",
]


INLINE_ELEMENTS = {"a", "bdo", "br", "img", "object", "rp", "ruby", "span"}


style_cache = {}


class KFX_EPUB_Properties(object):
    def Style(self, x):
        return Style(x)

    def process_content_properties(self, content):
        content_properties = {}
        for property_name in list(content.keys()):
            if property_name in YJ_PROPERTY_NAMES:
                content_properties[property_name] = content.pop(property_name)

        return self.convert_yj_properties(content_properties)

    def convert_yj_properties(self, yj_properties):
        declarations = {}

        for yj_property_name, yj_value in yj_properties.items():
            value = self.property_value(yj_property_name, yj_value)

            if yj_property_name in YJ_PROPERTY_INFO:
                property = YJ_PROPERTY_INFO[yj_property_name].name
            else:
                log.warning("unknown property name: %s" % yj_property_name)
                property = str(yj_property_name).replace("_", "-")

            if property == "position" and value in ["oeb-page-foot", "oeb-page-head"]:
                property = (
                    "display"
                    if self.epub.generate_epub2 and EMIT_OEB_PAGE_PROPS
                    else None
                )

            if (property is not None) and (value is not None):
                decl_value = declarations.get(property)
                if decl_value is not None and decl_value != value:
                    if property == "-kfx-attrib-epub-type":
                        vals = set(decl_value.split() + value.split())
                        for val in vals:
                            if not val.startswith("amzn:"):
                                log.error(
                                    'Property %s has multiple incompatible values: "%s" and "%s"'
                                    % (property, decl_value, value)
                                )
                                break
                        else:
                            value = " ".join(sorted(list(vals)))

                    elif property == "text-decoration":
                        vals = set(decl_value.split() + value.split())
                        value = " ".join(sorted(list(vals)))

                    else:
                        log.error(
                            'Property %s has multiple values: "%s" and "%s"'
                            % (property, decl_value, value)
                        )

                declarations[property] = value

        if declarations.get("text-combine-upright") == "all":
            self.text_combine_in_use = True
            if declarations.get("writing-mode") == "horizontal-tb":
                declarations.pop("writing-mode")

        if (
            "-kfx-background-positionx" in declarations
            or "-kfx-background-positiony" in declarations
        ):
            declarations["background-position"] = "%s %s" % (
                declarations.pop("-kfx-background-positionx", "50%"),
                declarations.pop("-kfx-background-positiony", "50%"),
            )

        if (
            "-kfx-background-sizex" in declarations
            or "-kfx-background-sizey" in declarations
        ):
            declarations["background-size"] = "%s %s" % (
                declarations.pop("-kfx-background-sizex", "auto"),
                declarations.pop("-kfx-background-sizey", "auto"),
            )

        if "-kfx-fill-color" in declarations or "-kfx-fill-opacity" in declarations:
            declarations["background-color"] = self.add_color_opacity(
                declarations.pop("-kfx-fill-color", "#ffffff"),
                declarations.pop("-kfx-fill-opacity", None),
            )

        if (
            "-kfx-text-emphasis-position-horizontal" in declarations
            or "-kfx-text-emphasis-position-vertical" in declarations
        ):
            declarations["text-emphasis-position"] = " ".join(
                [
                    v
                    for v in [
                        declarations.pop(
                            "-kfx-text-emphasis-position-horizontal", None
                        ),
                        declarations.pop("-kfx-text-emphasis-position-vertical", None),
                    ]
                    if v
                ]
            )

        if "-kfx-keep-lines-together" in declarations:
            for prop, val in zip(
                ["orphans", "widows"],
                declarations.pop("-kfx-keep-lines-together").split(),
            ):
                if val != "inherit":
                    declarations[prop] = val

        if (
            "text-decoration-color" in declarations
            and "text-decoration" not in declarations
            and declarations["text-decoration-color"] == "rgba(255,255,255,0)"
        ):
            declarations.pop("text-decoration-color")
            declarations["text-decoration"] = "none !important"

        if (
            FIX_NONSTANDARD_FONT_WEIGHT
            and "font-weight" in declarations
            and re.match(r"^[0-9]+$", declarations["font-weight"])
        ):
            weight_num = int(declarations["font-weight"])
            declarations["font-weight"] = "normal" if weight_num <= 500 else "bold"

        for combined_prop, individual_props in COMPOSITE_SIDE_STYLES:
            val = declarations.get(combined_prop, None)
            if val is not None:
                for individual_prop in individual_props:
                    if individual_prop not in declarations:
                        declarations[individual_prop] = val

                declarations.pop(combined_prop)

        return self.Style(declarations)

    def property_value(self, yj_property_name, yj_value, svg=False):
        property_info = YJ_PROPERTY_INFO.get(yj_property_name, None)
        value_map = property_info.values if property_info is not None else None

        val_type = ion_type(yj_value)

        if val_type is IonStruct:
            if "$307" in yj_value:
                magnitude = yj_value.pop("$307")
                unit = yj_value.pop("$306")
                if unit not in YJ_LENGTH_UNITS:
                    log.error(
                        "Property %s has unknown unit: %s" % (yj_property_name, unit)
                    )

                if (
                    DETECT_LAYOUT_ENHANCER
                    and yj_property_name == "$65"
                    and unit == "$318"
                    and magnitude in [216, 270, 324, 360]
                ):
                    log.warning(
                        "YJImageLayoutEnhancer detected, max_width=%s"
                        % value_str(magnitude, YJ_LENGTH_UNITS.get(unit, unit))
                    )

                if FIX_PT_TO_PX and unit == "$318" and magnitude > 0:
                    if int(magnitude * 1000) % 225 == 0:
                        px_value = int(magnitude * 1000) / 450.0
                        magnitude = px_value
                        unit = "$319"

                if unit == "$319":
                    magnitude = self.adjust_pixel_value(magnitude)

                value = value_str(magnitude, YJ_LENGTH_UNITS.get(unit, unit))

                if (
                    USE_NORMAL_LINE_HEIGHT
                    and yj_property_name == "$42"
                    and value == NORMAL_LINE_HEIGHT_EM
                ):
                    value = "normal"

            elif "$19" in yj_value:
                value = self.fix_color_value(yj_value.pop("$19"))

            elif "$499" in yj_value and "$500" in yj_value:
                values = []
                for sub_property in ["$499", "$500", "$501", "$502", "$498"]:
                    if sub_property in yj_value:
                        values.append(
                            self.property_value(
                                sub_property, yj_value.pop(sub_property)
                            )
                        )

                if yj_value.pop("$336", False):
                    values.append("inset")

                value = " ".join(values)

            elif "$58" in yj_value and yj_property_name == "$549":
                values = []
                for sub_property in ["$59", "$58"]:
                    if sub_property in yj_value:
                        values.append(
                            self.property_value(
                                sub_property, yj_value.pop(sub_property)
                            )
                        )
                    else:
                        log.error(
                            "Missing sub-property %s for %s"
                            % (sub_property, yj_property_name)
                        )
                        values.append("50%")

                value = " ".join(values)

            elif "$58" in yj_value:
                values = []
                for sub_property in ["$58", "$61", "$60", "$59"]:
                    if sub_property in yj_value:
                        val = self.property_value(
                            sub_property, yj_value.pop(sub_property)
                        )
                        if val != "0" and not val.endswith("%"):
                            log.error(
                                "Property %s has unexpected value: %s"
                                % (yj_property_name, val)
                            )
                        values.append(val.replace("%", ""))
                    else:
                        log.error(
                            "Missing sub-property %s for %s"
                            % (sub_property, yj_property_name)
                        )

                value = " ".join(values)

            elif "$175" in yj_value:
                yj_value.pop("$57", None)
                yj_value.pop("$56", None)
                value = self.property_value("$175", yj_value.pop("$175"))

            elif "$131" in yj_value or "$132" in yj_value:
                value = "%s %s" % (
                    yj_value.pop("$131", "inherit"),
                    yj_value.pop("$132", "inherit"),
                )

            else:
                log.error(
                    "Property %s has unknown dict value content: %s"
                    % (yj_property_name, repr(yj_value))
                )
                yj_value = {}
                value = "?"

            self.check_empty(yj_value, "Property %s value" % yj_property_name)

        elif val_type is IonString:
            if yj_property_name == "$11":
                value = self.fix_font_family_list(yj_value)
            elif yj_property_name == "$10":
                value = self.fix_language(yj_value)
            else:
                value = yj_value

        elif val_type is IonSymbol:
            if yj_property_name == "$173":
                value = self.unique_part_of_local_symbol(yj_value)
                if not value:
                    value = None

            elif yj_property_name in {"$479", "$175", "$528"}:
                value = 'url("%s")' % urllib.parse.quote(
                    urlrelpath(
                        self.process_external_resource(yj_value).filename,
                        ref_from=self.epub.STYLES_CSS_FILEPATH,
                    )
                )

            elif yj_property_name in COLOR_YJ_PROPERTIES:
                if yj_value == "$349":
                    value = self.fix_color_value(0)
                else:
                    log.warning(
                        "unexpected symbolic property value for %s: %s"
                        % (yj_property_name, yj_value)
                    )

            else:
                if value_map is not None:
                    if yj_value in value_map:
                        value = value_map[yj_value]
                    else:
                        log.warning(
                            "unknown property value for %s: %s"
                            % (yj_property_name, yj_value)
                        )
                        value = str(yj_value)
                else:
                    log.warning(
                        "unexpected symbolic property value for %s: %s"
                        % (yj_property_name, yj_value)
                    )
                    value = str(yj_value)

                if yj_property_name == "$11":
                    value = self.fix_font_family_list(value)

        elif val_type in [IonInt, IonFloat, IonDecimal]:
            value = value_str(yj_value)

            if yj_property_name in COLOR_YJ_PROPERTIES:
                if yj_property_name == "$70" and int(yj_value) & ALPHA_MASK == 0:
                    value = int(yj_value) | ALPHA_MASK

                value = self.fix_color_value(value)

            elif (
                value != "0"
                and yj_property_name
                not in {
                    "$112",
                    "$13",
                    "$148",
                    "$149",
                    "$645",
                    "$647",
                    "$648",
                    "$790",
                    "$640",
                    "$641",
                    "$642",
                    "$639",
                    "$72",
                    "$126",
                    "$125",
                    "$42",
                }
                and not svg
            ):
                value = value_str(self.adjust_pixel_value(yj_value))

                value += "px"

            else:
                value = value_str(yj_value)

        elif val_type is IonBool:
            if value_map is not None:
                if yj_value in value_map:
                    value = value_map[yj_value]
                else:
                    log.warning(
                        "unknown property value for %s: %s"
                        % (yj_property_name, yj_value)
                    )
                    value = str(yj_value)
            else:
                log.warning(
                    "unexpected boolean property value for %s: %s"
                    % (yj_property_name, yj_value)
                )
                value = str(yj_value)

        elif val_type is IonList:
            if yj_property_name == "$650":
                value = self.process_polygon(yj_value)

            elif yj_property_name == "$646" and len(yj_value) > 0:
                values = []
                for collision in yj_value:
                    if collision in COLLISIONS:
                        values.append(COLLISIONS[collision])
                    else:
                        log.error("Unexpected yj.collision value: %s" % str(collision))

                value = " ".join(sorted(values))

            elif yj_property_name == "$98":
                value = self.process_transform(yj_value, svg)

            elif yj_property_name == "$497":
                values = []
                for text_shadow in yj_value:
                    values.append(self.property_value(yj_property_name, text_shadow))

                value = ", ".join(values)

            elif yj_property_name == "$761":
                values = []
                for layout_hint in yj_value:
                    if layout_hint in LAYOUT_HINT_CLASS_NAMES:
                        values.append(LAYOUT_HINT_CLASS_NAMES[layout_hint])
                    else:
                        log.warning("Unexpected layout_hint %s" % layout_hint)

                value = " ".join(values)

            else:
                log.error(
                    "unexpected IonList property value for %s: %s"
                    % (yj_property_name, yj_value)
                )
                value = "?"

        else:
            log.error(
                "Property %s has unknown value format (%s): %s"
                % (yj_property_name, type_name(yj_value), repr(yj_value))
            )
            value = "?"

        if yj_property_name in {"$640", "$641", "$642", "$639"} and value not in [
            "100",
            "-100",
        ]:
            log.error(
                "Property %s has disallowed value: %s" % (yj_property_name, value)
            )

        if yj_property_name in {"$32", "$33"} and value == "0em":
            value = "normal"

        return value

    def fixup_styles_and_classes(self):
        if STYLE_TEST:
            log.warning("Style simplification disabled")
            return

        self.css_rules = {}

        self.non_heritable_default_properties = self.Style(
            NON_HERITABLE_DEFAULT_PROPERTIES
        )

        heritable_defaults_filtered = dict(
            [(k, v) for k, v in HERITABLE_DEFAULT_PROPERTIES.items() if v is not None]
        )

        for book_part in self.epub.book_parts:
            heritable_default_properties = self.Style(heritable_defaults_filtered)
            lang = book_part.html.get(XML_LANG)
            if lang:
                heritable_default_properties.update(
                    self.Style({"-kfx-attrib-xml-lang": lang}), replace=True
                )

            self.simplify_styles(
                book_part.body(),
                book_part,
                heritable_default_properties,
                REVERSE_INHERITANCE and not self.epub.illustrated_layout,
            )

            self.add_composite_and_equivalent_styles(book_part.body(), book_part)

        style_counts = collections.defaultdict(lambda: 0)

        for book_part in self.epub.book_parts:
            body = book_part.body()
            for e in body.iter("*"):
                class_name = e.get("class")
                if class_name and (class_name not in AMAZON_SPECIAL_CLASSES):
                    selector = class_selector(class_name)
                    if selector not in self.missing_special_classes:
                        log.error("Unexpected class found: %s" % class_name)
                        self.missing_special_classes.add(selector)

                if "style" in e.attrib:
                    style = self.get_style(e)
                    style_modified = False

                    style_attribs = style.partition(
                        name_prefix="-kfx-attrib-", remove_prefix=True
                    )
                    if style_attribs:
                        style_modified = True
                        for name, value in style_attribs.items():
                            if name.startswith("epub-"):
                                name = qname(EPUB_NS_URI, name.partition("-")[2])
                                if name == EPUB_TYPE and self.epub.generate_epub2:
                                    continue
                            elif name.startswith("xml-"):
                                name = qname(XML_NS_URI, name.partition("-")[2])

                            if name in [
                                "colspan",
                                "rowspan",
                                "valign",
                            ] and e.tag not in ["tbody", "tr", "td"]:
                                log.error(
                                    "Unexpected class_attribute in %s: %s"
                                    % (e.tag, name)
                                )

                            e.set(name, value)

                    if style_modified:
                        self.set_style(e, style)

                    if (
                        CVT_DIRECTION_PROPERTY_TO_MARKUP or not self.epub.generate_epub2
                    ) and ("direction" in style or "unicode-bidi" in style):
                        unicode_bidi = style.get("unicode-bidi", "normal")

                        has_block = False
                        has_content = e.text
                        for ex in e.iterfind(".//*"):
                            if ex.tag in {
                                "aside",
                                "div",
                                "figure",
                                "h1",
                                "h2",
                                "h3",
                                "h4",
                                "h5",
                                "h6",
                                "iframe",
                                "li",
                                "ol",
                                "table",
                                "td",
                                "ul",
                            }:
                                has_block = True

                            if (
                                ex.text
                                or ex.tail
                                or ex.tag
                                in {"audio", "img", "li", MATH, "object", SVG, "video"}
                            ):
                                has_content = True

                            if has_block and has_content:
                                break

                        if not has_content:
                            style.pop("direction", None)
                            style.pop("unicode-bidi", None)
                            self.set_style(e, style)

                        elif unicode_bidi in ["embed", "normal"] or has_block:
                            if "direction" in style:
                                e.set("dir", style.pop("direction"))

                            style.pop("unicode-bidi", None)
                            self.set_style(e, style)

                        elif unicode_bidi in [
                            "isolate",
                            "bidi-override",
                            "isolate-override",
                        ]:
                            bdx = etree.Element(
                                "bdo" if "override" in unicode_bidi else "bdi"
                            )
                            if "direction" in style:
                                bdx.set("dir", style.pop("direction"))

                            if e.tag != "img":
                                bdx.text = e.text
                                e.text = None

                                while len(e) > 0:
                                    ec = e[0]
                                    e.remove(ec)
                                    bdx.append(ec)

                                e.insert(0, bdx)

                            style.pop("unicode-bidi", None)
                            self.set_style(e, style)

                        else:
                            log.error(
                                "Cannot produce EPUB3 equivalent for: unicode-bidi:%s direction:%s"
                                % (unicode_bidi, style.get("direction", "?"))
                            )

                    kfx_style_name = style.pop("-kfx-style-name", None)
                    if kfx_style_name and not style:
                        self.set_style(e, style)

                if "style" in e.attrib:
                    style_counts[e.get("style")] += 1

        sorted_style_data = []
        known_class_name_count = collections.defaultdict(lambda: 0)

        for class_name in AMAZON_SPECIAL_CLASSES:
            known_class_name_count[class_name] = 2

        for style_str, count in sorted(style_counts.items(), key=lambda sc: -sc[1]):
            style = self.Style(style_str)

            class_name = re.sub(
                r"[^A-Za-z0-9_-]", "_", style.pop("-kfx-style-name", "")
            )

            class_name_prefixes = set()
            if "-kfx-layout-hints" in style:
                class_name_prefixes.update(style.pop("-kfx-layout-hints").split())

            if "-kfx-heading-level" in style:
                class_name_prefixes.discard("heading")
                class_name_prefixes.add("h" + style.pop("-kfx-heading-level"))

            class_name_prefix = (
                "-".join(sorted(list(class_name_prefixes)))
                if class_name_prefixes
                else DEFAULT_CLASS_NAME_PREFIX
            )
            known_class_name_count[class_name_prefix] += 1

            class_name = self.prefix_unique_part_of_symbol(
                class_name, class_name_prefix
            )
            known_class_name_count[class_name] += 1
            sorted_style_data.append((style_str, style, class_name))

        classes = {}
        style_class_names = {}
        used_class_name_count = collections.defaultdict(lambda: 0)
        referenced_classes = set()
        selector_classes = set()

        for style_str, style, class_name in sorted_style_data:
            if known_class_name_count[class_name] > 1 or class_name in classes:
                while True:
                    unique = used_class_name_count[class_name]
                    used_class_name_count[class_name] += 1
                    class_name = "%s-%d" % (class_name, unique)
                    if (
                        known_class_name_count[class_name] == 0
                        and class_name not in classes
                    ):
                        break

            for prop_name_prefix, selector_suffix in [
                ("-kfx-firstline-", "::first-line"),
                ("-kfx-link-", ":link"),
                ("-kfx-visited-", ":visited"),
            ]:
                selector_style = style.partition(
                    name_prefix=prop_name_prefix, remove_prefix=True
                )
                if selector_style:
                    self.css_rules[class_selector(class_name) + selector_suffix] = (
                        selector_style
                    )
                    selector_classes.add(class_name)

            classes[class_name] = style
            style_class_names[style_str] = class_name

        for book_part in self.epub.book_parts:
            body = book_part.body()
            for e in body.iter("*"):
                style_str = e.get("style", "")
                if style_str in style_class_names:
                    class_name = style_class_names[style_str]
                    class_style = classes[class_name]

                    if (
                        (KEEP_STYLES_INLINE or book_part.is_fxl)
                        and class_name not in selector_classes
                        and "-kfx-media-query" not in class_style
                    ):
                        e.set("style", class_style.tostring())
                        self.inventory_style(class_style)
                    else:
                        self.add_class(e, class_name, before=True)
                        referenced_classes.add(class_name)
                        e.attrib.pop("style", None)

                elif style_str:
                    log.warning("Style has no class name: %s" % style_str)

        for class_name, class_style in classes.items():
            if class_name in referenced_classes:
                media_query = class_style.pop("-kfx-media-query")
                if class_style:
                    target = (
                        self.media_queries[media_query]
                        if media_query
                        else self.css_rules
                    )
                    target[class_selector(class_name)] = class_style

        for class_style in list(self.css_rules.values()) + self.font_faces:
            self.inventory_style(class_style)

        for mq_classes in self.media_queries.values():
            for class_style in mq_classes.values():
                self.inventory_style(class_style)

    def inventory_style(self, style):
        reported = set()
        for key, value in style.items():
            simple_value = " ".join(zero_quantity(v) for v in value.split())
            if (
                (simple_value not in KNOWN_STYLES.get(key, set()))
                and ("*" not in KNOWN_STYLES.get(key, set()))
                and (key, value) not in reported
            ):
                log.error("Unexpected style definition: %s: %s" % (key, value))

                reported.add((key, value))

    def update_default_font_and_language(self):
        content_font_families = collections.defaultdict(lambda: 0)
        content_languages = collections.defaultdict(lambda: 0)

        def scan_content(elem, font_family, lang):
            style = elem.get("style", "")
            if "font-family" in style or "-kfx-attrib-xml-lang" in style:
                sty = self.Style(style)
                font_family = sty.get("font-family", font_family)
                lang = sty.get("-kfx-attrib-xml-lang", lang)

            text_len = len(elem.text or "")

            for e in elem.iterfind("*"):
                if e.tag != "head":
                    text_len += scan_content(e, font_family, lang)

            if text_len:
                content_font_families[font_family] += text_len
                content_languages[lang] += text_len

            return len(elem.tail or "")

        for book_part in self.epub.book_parts:
            scan_content(book_part.html, None, None)

        best_font_family, best_merit = self.default_font_family, 0
        default_font_family_pattern = re.compile(
            re.escape(self.default_font_family) + "(,.+)?$"
        )

        for font_family, merit in content_font_families.items():
            if (
                merit > best_merit
                and font_family
                and re.match(default_font_family_pattern, font_family)
            ):
                best_font_family, best_merit = font_family, merit

        self.default_font_family = best_font_family

        best_language, best_merit = self.epub.language, 0

        if self.epub.language:
            default_language_pattern = re.compile(
                re.escape(self.epub.language) + "(-.+)?$", re.IGNORECASE
            )

            for language, merit in content_languages.items():
                if (
                    merit > best_merit
                    and language
                    and re.match(default_language_pattern, language)
                ):
                    best_language, best_merit = language, merit

            self.epub.language = best_language

    def set_html_defaults(self):
        for book_part in self.epub.book_parts:
            if not book_part.is_cover_page:
                body = book_part.body()
                body_sty = self.get_style(body)

                if "font-family" not in body_sty and self.default_font_family:
                    body_sty["font-family"] = self.default_font_family

                if "font-size" not in body_sty:
                    body_sty["font-size"] = self.default_font_size

                if "line-height" not in body_sty:
                    body_sty["line-height"] = self.default_line_height

                if "writing-mode" not in body_sty:
                    body_sty["writing-mode"] = self.epub.writing_mode

                self.set_style(body, body_sty)

                if self.epub.language:
                    book_part.html.set(XML_LANG, self.epub.language)

    def simplify_styles(
        self,
        elem,
        book_part,
        inherited_properties,
        reverse_inheritance,
        default_ordered_list_value=None,
    ):
        inherited_properties = inherited_properties.copy()

        if split_value(inherited_properties.get("font-size", ""))[1] == "em":
            inherited_properties["font-size"] = "1em"

        sty = inherited_properties.copy().update(self.get_style(elem), replace=True)
        orig_sty = sty.copy()

        sty.pop("-kfx-render", None)

        if (
            book_part.is_fxl
            and elem.tag in {"a", "span"}
            and sty.get("display", "inline") == "inline"
            and ("height" in sty or "width" in sty)
        ):
            sty["display"] = "inline-block"

        if sty.get("position", "static") == "static":
            for positioning in ["top", "bottom", "left", "right"]:
                if positioning in sty:
                    if sty[positioning] == "0":
                        sty.pop(positioning)
                    else:
                        log.warning(
                            "%s style with unexpected position: %s"
                            % (elem.tag, sty.tostring())
                        )

        sty["border-spacing"] = "%s %s" % (
            sty["-webkit-border-horizontal-spacing"],
            sty["-webkit-border-vertical-spacing"],
        )

        sides = []
        for s in ["top", "bottom", "left", "right"]:
            if sty.pop("-kfx-user-margin-%s-percentage" % s, "100") == "-100":
                sides.append(s)

        page_align = sty["-amzn-page-align"] = (
            (",".join(sides) if len(sides) < 4 else "all") if len(sides) > 0 else "none"
        )

        for name, val in list(sty.items()):
            if name in {
                "padding",
                "padding-top",
                "padding-bottom",
                "padding-left",
                "padding-right",
            } and val.startswith("-"):
                log.warning("Discarding invalid %s: %s" % (name, val))
                sty.pop(name)

            elif name not in ARBITRARY_VALUE_PROPERTIES:
                quantity, unit = split_value(val)

                if unit == "lh" and quantity is not None:
                    if name == "line-height":
                        if (
                            USE_NORMAL_LINE_HEIGHT
                            and quantity >= 0.99
                            and quantity <= 1.01
                        ):
                            sty[name] = "normal"
                        else:
                            quantity = quantity * LINE_HEIGHT_SCALE_FACTOR

                            if (MINIMUM_LINE_HEIGHT is not None) and (
                                quantity < MINIMUM_LINE_HEIGHT
                            ):
                                quantity = MINIMUM_LINE_HEIGHT

                            sty[name] = value_str(quantity)
                    else:
                        sty[name] = value_str(quantity * LINE_HEIGHT_SCALE_FACTOR, "em")

                    quantity, unit = split_value(sty[name])

                if (
                    unit == "rem"
                    and quantity is not None
                    and (
                        self.epub.generate_epub2 or self.epub.GENERATE_EPUB2_COMPATIBLE
                    )
                ):
                    if name == "font-size":
                        base_font_size = inherited_properties["font-size"]
                    else:
                        base_font_size = orig_sty["font-size"]

                    base_font_size_quantity, base_font_size_unit = split_value(
                        base_font_size
                    )

                    if base_font_size_unit == "rem":
                        quantity = quantity / base_font_size_quantity
                        unit = "em"
                    elif base_font_size_unit == "em":
                        unit = "em"
                    else:
                        log.error(
                            "Cannot convert %s:%s with incorrect base font size units %s"
                            % (name, val, base_font_size)
                        )

                    if (
                        name == "line-height"
                        and (MINIMUM_LINE_HEIGHT is not None)
                        and (quantity < MINIMUM_LINE_HEIGHT)
                    ):
                        quantity = MINIMUM_LINE_HEIGHT

                    sty[name] = value_str(quantity, unit)

                if (unit == "vh" or unit == "vw") and quantity is not None:
                    if page_align != "none" and name in ["height", "width"]:
                        if name[0] != unit[1]:
                            if not ("height" in sty and "width" in sty):
                                if elem.tag == "img":
                                    img_filename = get_url_filename(
                                        urlabspath(
                                            elem.get("src"), ref_from=book_part.filename
                                        )
                                    )
                                    img_file = self.epub.oebps_files[img_filename]
                                    orig_prop = name
                                    sty.pop(orig_prop)

                                    if name == "width":
                                        quantity = (
                                            quantity * img_file.height
                                        ) / img_file.width
                                        name = "height"
                                    else:
                                        quantity = (
                                            quantity * img_file.width
                                        ) / img_file.height
                                        name = "width"

                                    if quantity > 99.0 and quantity < 101.0:
                                        quantity = 100.0
                                    else:
                                        log.warning(
                                            "converted %s:%s for img %dw x %dh to %s:%f%%"
                                            % (
                                                orig_prop,
                                                val,
                                                img_file.width,
                                                img_file.height,
                                                name,
                                                quantity,
                                            )
                                        )

                                else:
                                    log.error(
                                        "viewport-based units with wrong property on non-image: %s:%s"
                                        % (name, val)
                                    )
                            else:
                                log.error(
                                    "viewport-based units with wrong property: %s:%s"
                                    % (name, val)
                                )

                        sty[name] = value_str(quantity, "%")
                        quantity, unit = split_value(sty[name])
                    else:
                        log.error(
                            "viewport-based units with wrong property or without page-align: %s:%s"
                            % (name, val)
                        )

        if ("outline-width" in sty) and (sty.get("outline-style", "none") == "none"):
            sty.pop("outline-width")

        if elem.tag == "ol":
            if "start" in elem.attrib:
                default_ordered_list_value = int(elem.get("start"))
                if default_ordered_list_value == 1:
                    elem.attrib.pop("start")
            else:
                default_ordered_list_value = 1

        elif elem.tag == "ul":
            if "start" in elem.attrib:
                elem.attrib.pop("start")

            default_ordered_list_value = False

        elif elem.tag == "li":
            if "value" in elem.attrib:
                ordered_list_value = int(elem.get("value"))
                if (default_ordered_list_value is False) or (
                    ordered_list_value == default_ordered_list_value
                ):
                    elem.attrib.pop("value")

            default_ordered_list_value = None

        else:
            default_ordered_list_value = None

        if (
            sty.get("background-image", "none") != "none"
            and "-amzn-max-crop-percentage" in sty
        ):
            if sty["-amzn-max-crop-percentage"] == "0 0 0 0":
                sty.pop("-amzn-max-crop-percentage")
                sty["background-size"] = "contain"
            elif sty["-amzn-max-crop-percentage"] == "0 100 100 0":
                sty.pop("-amzn-max-crop-percentage")
                sty["background-size"] = "cover"

        if (
            elem.tag == "a"
            and "color" not in sty
            and "-kfx-link-color" in sty
            and "-kfx-visited-color" in sty
            and sty["-kfx-link-color"] == sty["-kfx-visited-color"]
        ):
            sty["color"] = sty.pop("-kfx-link-color")
            sty.pop("-kfx-visited-color")

        parent_sty = sty.copy()

        for name in [
            "font-size",
            "-kfx-user-margin-bottom-percentage",
            "-kfx-user-margin-left-percentage",
            "-kfx-user-margin-right-percentage",
            "-kfx-user-margin-top-percentage",
        ]:
            parent_sty[name] = orig_sty[name]

        for name, val in list(parent_sty.items()):
            if name not in HERITABLE_PROPERTIES:
                parent_sty.pop(name)
            elif (
                name not in ARBITRARY_VALUE_PROPERTIES
                and name != "line-height"
                and split_value(val)[1] == "%"
            ):
                parent_sty.pop(name)

        for child in elem.findall("*"):
            self.simplify_styles(
                child,
                book_part,
                parent_sty,
                reverse_inheritance,
                default_ordered_list_value,
            )

            if (child.tag == "li") and (
                default_ordered_list_value not in [None, False]
            ):
                default_ordered_list_value += 1

        num_children = len(elem)
        if reverse_inheritance and num_children > 0:
            if elem.text or elem.tail:
                log.error(
                    "elem %s with children has text or tail in %s"
                    % (elem.tag, book_part.filename)
                )
            else:
                child_props = collections.defaultdict(dict)
                for child in elem.findall("*"):
                    child_sty = self.get_style(child)
                    for name, val in child_sty.items():
                        if name in REVERSE_HERITABLE_PROPERTIES:
                            if val not in child_props[name]:
                                child_props[name][val] = 1
                            else:
                                child_props[name][val] += 1

                new_heritable_sty = {}
                for name, vals in child_props.items():
                    total = 0
                    most_common = None
                    for val, count in vals.items():
                        total += count
                        if most_common is None or count > vals[most_common]:
                            most_common = val

                    if total < num_children and sty.get(name) is None:
                        pass
                    elif (
                        vals[most_common] >= num_children * REVERSE_INHERITANCE_FRACTION
                    ):
                        new_heritable_sty[name] = most_common

                if len(new_heritable_sty) > 0:
                    for child in elem.findall("*"):
                        child_sty = self.get_style(child)

                        for name, new_heritable_val in new_heritable_sty.items():
                            val = child_sty.get(name)
                            if val is not None:
                                if val == new_heritable_val:
                                    child_sty.pop(name)
                            elif sty[name] != new_heritable_val:
                                child_sty[name] = sty[name]

                        self.set_style(child, child_sty)

                    sty.update(new_heritable_sty, replace=True)

        inherited_properties.update(self.non_heritable_default_properties)

        if split_value(sty.get("font-size", ""))[1] == "em":
            inherited_properties["font-size"] = "1em"

        if (
            sty.get("background-color", "transparent") == "transparent"
            and sty.get("background-image", "none") == "none"
        ):
            for name in [
                "background-clip",
                "background-origin",
                "background-position",
                "background-repeat",
                "background-size",
            ]:
                sty.pop(name, None)

        remove_from = inherited_properties if elem.tag == "a" else sty
        remove_from.pop("-kfx-link-color", None)
        remove_from.pop("-kfx-visited-color", None)

        for name, val in list(sty.items()):
            if val == inherited_properties.get(name, ""):
                sty.pop(name)

        self.set_style(elem, sty)

    def add_composite_and_equivalent_styles(self, elem, book_part):
        sty = self.get_style(elem)

        for combined_prop, individual_props in COMPOSITE_SIDE_STYLES:
            val = sty.get(individual_props[0], None)
            if val is not None:
                for individual_prop in individual_props[1:]:
                    if sty.get(individual_prop, None) != val:
                        break
                else:
                    sty[combined_prop] = val
                    for individual_prop in individual_props:
                        sty.pop(individual_prop)

        for name, val in list(sty.items()):
            alt_name = ALTERNATE_EQUIVALENT_PROPERTIES.get(name)
            if alt_name is not None:
                if name == "text-combine-upright" and val == "all":
                    sty[alt_name] = "horizontal"
                else:
                    sty[alt_name] = val

        display = sty.get("display", "")
        ineffective_properties = []

        if display == "inline" or (
            elem.tag in INLINE_ELEMENTS and display not in {"block", "inline-block"}
        ):
            ineffective_properties.extend(
                [
                    "list-style-image",
                    "list-style-position",
                    "list-style-type",
                    "column-count",
                    "text-align",
                    "text-align-last",
                    "text-indent",
                ]
            )

            if elem.tag != "img":
                ineffective_properties.extend(
                    [
                        "height",
                        "width",
                        "max-height",
                        "max-width",
                        "overflow",
                        "-amzn-page-align",
                        "-amzn-page-footer",
                        "-amzn-page-header",
                    ]
                )

        if ineffective_properties:
            ineffective_sty = sty.partition(
                property_names=ineffective_properties, modify=False
            )

            if ineffective_sty:
                log.warning(
                    "Ineffective property in %s element for kfx-style %s in %s: %s"
                    % (
                        elem.tag,
                        sty.get("-kfx-style-name", "?"),
                        book_part.filename,
                        ineffective_sty.tostring(),
                    )
                )

        self.set_style(elem, sty)

        for child in elem.findall("*"):
            self.add_composite_and_equivalent_styles(child, book_part)

    def fix_font_family_list(self, value):
        return self.join_font_family_value(
            remove_duplicates(
                [
                    self.fix_font_name(name)
                    for name in self.split_font_family_value(value)
                ]
            )
        )

    def split_font_family_value(self, value):
        return [self.unquote_font_name(name.strip()) for name in value.split(",")]

    def join_font_family_value(self, value_list):
        return ",".join([self.quote_font_name(font_name) for font_name in value_list])

    def fix_font_name(self, name, add=False, generic=False):
        name = self.unquote_font_name(name)

        name = re.sub(
            r"-(oblique|italic|bold|regular|roman|medium)$",
            r" \1",
            name,
            flags=re.IGNORECASE,
        )
        name = MISSPELLED_FONT_NAMES.get(name.lower(), name)

        name = name.replace("sans-serif", "sans_serif")

        prefix, sep, name = name.rpartition("-")

        name = name.replace("sans_serif", "sans-serif").strip()

        if add:
            self.font_name_replacements[name.lower()] = name

            if not generic:
                self.font_names.add(name)

        else:
            name = self.font_name_replacements.get(
                name.lower(), capitalize_font_name(name)
            )

            if name not in self.font_names and name not in GENERIC_FONT_NAMES:
                self.missing_font_names.add(name)

        return name

    def fix_language(self, lang):
        prefix, sep, suffix = lang.partition("-")

        if len(suffix) < 4:
            suffix = suffix.upper()
        else:
            suffix = suffix[0].upper() + suffix[1:]

        return prefix + sep + suffix

    def fix_color_value(self, value):
        if isstring(value) and not re.match(r"^[0-9]+$", value):
            return value

        color = int(value)
        return self.color_str(color, self.int_to_alpha(color >> 24))

    def add_color_opacity(self, value, opacity):
        if opacity is None:
            return value

        color = self.color_int(value)

        orig_alpha = self.int_to_alpha(color >> 24)
        if orig_alpha not in {0.0, 1.0}:
            log.error(
                "Unexpected combination of alpha (%s) and opacity (%s) for color %s"
                % (orig_alpha, opacity, value)
            )

        return self.color_str(color, float(opacity))

    def color_str(self, rgb_int, alpha):
        if alpha == 1.0:
            hex_color = "#%06x" % (rgb_int & 0x00FFFFFF)
            if hex_color in COLOR_NAME:
                return COLOR_NAME[hex_color]

            return (
                "#000"
                if hex_color == "#000000"
                else ("#fff" if hex_color == "#ffffff" else hex_color)
            )

        red = (rgb_int & 0x00FF0000) >> 16
        green = (rgb_int & 0x0000FF00) >> 8
        blue = rgb_int & 0x000000FF
        alpha_str = "0" if alpha == 0.0 else "%0.3f" % alpha

        return "rgba(%d,%d,%d,%s)" % (red, green, blue, alpha_str)

    def color_int(self, color):
        if color in COLOR_HEX:
            color = COLOR_HEX[color]

        m = re.match(r"^#([0-9a-f]{3,6})$", color, flags=re.IGNORECASE)
        if m:
            rgb = m.group(1)
            if len(rgb) == 3:
                rgb = rgb[0] + rgb[0] + rgb[1] + rgb[1] + rgb[2] + rgb[2]

            return 0xFF000000 + int(rgb, 16)

        m = re.match(
            r"^rgba\(([0-9]+),([0-9]+),([0-9]+),([0-9.]+)\)$",
            color,
            flags=re.IGNORECASE,
        )
        if m:
            red = int(m.group(1))
            green = int(m.group(2))
            blue = int(m.group(3))
            alpha_int = self.alpha_to_int(float(m.group(4)))
            return (alpha_int << 24) + (red << 16) + (green << 8) + blue

        raise Exception("cannot parse color value: %s" % color)

    def int_to_alpha(self, alpha_int):
        if alpha_int < 2:
            return 0.0

        if alpha_int > 253:
            return 1.0

        return max(min(float(alpha_int + 1) / 256.0, 1.0), 0.0)

    def alpha_to_int(self, alpha):
        if alpha < 0.012:
            return 0

        if alpha > 0.996:
            return 255

        return max(min(int(alpha * 256.0 + 0.5) - 1, 255), 0)

    def pixel_value(self, value):
        if ion_type(value) is IonStruct:
            unit = value.pop("$306")
            if unit != "$319":
                log.error(
                    "%s Expected px value, found %s" % (self.content_context, unit)
                )

            value = value.pop("$307")

        if ion_type(value) in [IonDecimal, IonFloat]:
            value = int(value)

        if ion_type(value) is not IonInt:
            log.error(
                "%s Expected int for px value, found %s"
                % (self.content_context, type_name(value))
            )
            return value

        return self.adjust_pixel_value(value)

    def adjust_pixel_value(self, value):
        if FIX_PRINT_REPLICA_PIXEL_VALUES and self.epub.is_print_replica:
            px_value = round(value / 100, 2)
            value = px_value

        return value

    def add_class(self, elem, class_name, before=False):
        classes = elem.get("class", "").split()
        if class_name and class_name not in classes:
            if before:
                classes.insert(0, class_name)
            else:
                classes.append(class_name)

            elem.set("class", " ".join(classes))

    def get_style(self, elem, remove=False):
        return self.Style(
            elem.attrib.pop("style", "") if remove else elem.get("style", "")
        )

    def set_style(self, elem, new_style):
        if type(new_style) is not Style:
            raise Exception("set_style: type %s" % type_name(new_style))

        style_str = new_style.tostring()
        if style_str:
            elem.set("style", style_str)
        else:
            elem.attrib.pop("style", None)

    def add_style(self, elem, new_style, replace=None):
        if type(new_style) is not Style and type(new_style) is not dict:
            raise Exception("add_style: type %s" % type_name(new_style))

        if new_style:
            orig_style_str = elem.get("style", "")

            if orig_style_str:
                new_style = self.Style(orig_style_str).update(new_style, replace)
            elif type(new_style) is not Style:
                new_style = self.Style(new_style)

            self.set_style(elem, new_style)

    def create_css_files(self):
        for css_file in sorted(list(self.css_files)):
            if css_file == self.epub.RESET_CSS_FILEPATH:
                self.epub.manifest_resource(
                    self.epub.RESET_CSS_FILEPATH,
                    data=RESET_CSS_DATA.encode("utf-8"),
                    mimetype="text/css",
                )

            elif css_file == self.epub.STYLES_CSS_FILEPATH:
                css_lines = ['@charset "UTF-8";']

                if self.font_faces:
                    css_lines.extend(
                        [
                            "@font-face {%s}" % ff.tostring()
                            for ff in sorted(self.font_faces)
                        ]
                    )

                if self.css_rules:
                    css_lines.extend(
                        [
                            "%s {%s}" % (cn, self.css_rules[cn])
                            for cn in sorted(
                                self.css_rules.keys(), key=natural_sort_key
                            )
                        ]
                    )

                for mq, css_rules in sorted(self.media_queries.items()):
                    css_lines.append("@media %s {" % mq)
                    css_lines.extend(
                        [
                            "    %s {%s}" % (cn, css_rules[cn])
                            for cn in sorted(css_rules.keys(), key=natural_sort_key)
                        ]
                    )
                    css_lines.append("}")

                self.epub.manifest_resource(
                    self.epub.STYLES_CSS_FILEPATH,
                    data="\n".join(css_lines).encode("utf-8"),
                    mimetype="text/css",
                )

    def quote_font_name(self, value):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", value):
            return value

        if "'" not in value:
            return "'" + value + "'"

        return '"' + value.replace('"', '\\"') + '"'

    def unquote_font_name(self, value):
        orig_value = value

        if len(value) > 1 and value[0] in ["'", '"'] and value[0] == value[-1]:
            value = value[1:-1]

        if "'" in value or '"' in value:
            if orig_value not in self.incorrect_font_quoting:
                log.warning("Incorrectly quoted font family: %s" % orig_value)
                self.incorrect_font_quoting.add(orig_value)

            value = value.replace('"', "").replace("'", "").strip()

        return value


@functools.total_ordering
class Style(object):
    def __init__(self, src, sstr=None):
        self.style_str = self.properties = None

        if type(src) is etree.Element:
            src = src.get("style", "")

        if isinstance(src, bytes):
            src = src.decode("ascii")

        if isinstance(src, str):
            src = self.get_properties(src)

        if isinstance(src, dict):
            self.properties = dict(src)
            self.style_str = sstr
        else:
            raise Exception("Cannot create style from %s" % type_name(src))

    def get_properties(self, style_str):
        if style_str == "None":
            raise Exception("Unexpected 'None' encountered in style")

        if style_str not in style_cache:
            style_cache[style_str] = properties = {}

            for property in re.split(r"((?:[^;\(]|\([^\)]*\))+)", style_str)[1::2]:
                property = property.strip()
                if property:
                    name, sep, value = property.partition(":")
                    name = name.strip()
                    value = value.strip()

                    if sep != ":":
                        log.error(
                            "Malformed property %s in style: %s" % (name, style_str)
                        )
                    else:
                        if name in properties and properties[name] != value:
                            log.error(
                                "Conflicting property %s values in style: %s"
                                % (name, style_str)
                            )

                        properties[name] = value

        return dict(style_cache[style_str])

    def tostring(self):
        if self.style_str is None:
            self.style_str = "; ".join(
                ["%s: %s" % s for s in sorted(self.properties.items())]
            )

        return self.style_str

    def keys(self):
        return self.properties.keys()

    def items(self):
        return self.properties.items()

    def get(self, key, default=None):
        return self.properties.get(key, default)

    def __len__(self):
        return len(self.properties)

    def __repr__(self):
        return self.tostring()

    def __str__(self):
        return self.tostring()

    def __eq__(self, other):
        if not isinstance(other, Style):
            raise Exception("Style __eq__: comparing with %s" % type_name(other))

        if self.style_str is not None and other.style_str is not None:
            return self.style_str == other.style_str

        return self.properties == other.properties

    def __lt__(self, other):
        if not isinstance(other, Style):
            raise Exception("Style __lt__: comparing with %s" % type_name(other))

        return self.tostring() < other.tostring()

    def __hash__(self):
        return hash(self.tostring())

    def __getitem__(self, key):
        return self.properties[key]

    def __contains__(self, key):
        return key in self.properties

    def __setitem__(self, key, value):
        self.properties[key] = value
        self.style_str = None

    def pop(self, key, default=None):
        value = self.properties.pop(key, default)
        self.style_str = None
        return value

    def clear(self):
        self.properties = {}
        self.style_str = None
        return self

    def copy(self):
        return Style(self.properties, self.style_str)

    def update(self, other, replace=None):
        if type(other) is Style:
            other = other.properties

        for name, value in other.items():
            if (name in CONFLICTING_PROPERTIES) and not CONFLICTING_PROPERTIES[
                name
            ].isdisjoint(set(self.properties.keys())):
                log.error(
                    "Setting conflicting property: %s with %s"
                    % (name, list_symbols(self.properties.keys()))
                )

            if name in self.properties and self.properties[name] != value:
                if replace is Exception:
                    raise Exception(
                        "Setting conflicting property value: %s = %s >> %s"
                        % (name, self.properties[name], value)
                    )

                if replace is None:
                    log.error(
                        "Setting conflicting property value: %s = %s >> %s"
                        % (name, self.properties[name], value)
                    )
                elif not replace:
                    continue

            self.properties[name] = value
            self.style_str = None

        return self

    def partition(
        self,
        property_names=None,
        name_prefix=None,
        remove_prefix=False,
        add_prefix=False,
        keep=False,
        keep_all=False,
        modify=True,
    ):
        match_props = {}
        other_props = {}

        for name, value in self.properties.items():
            if name_prefix is not None:
                if add_prefix:
                    name = "%s-%s" % (name_prefix, name)
                    match = True
                else:
                    match = name.startswith(name_prefix)

                if match and remove_prefix:
                    name = name[len(name_prefix) :]
            else:
                match = name in property_names

            if match:
                match_props[name] = value
            else:
                other_props[name] = value

        if keep and modify:
            self.properties = match_props
            self.style_str = None

        if keep or keep_all:
            return Style(other_props)

        if modify:
            self.properties = other_props
            self.style_str = None

        return Style(match_props)

    def remove_default_properties(self, default_style):
        defaults = default_style.properties

        for name, value in self.properties.items():
            if value == defaults.get(name, ""):
                self.properties.pop(name)
                self.style_str = None

        return self


def value_str(quantity, unit="", emit_zero_unit=False):
    if quantity is None:
        return unit

    if abs(quantity) < 1e-6:
        q_str = "0"
    elif type(quantity) is float:
        q_str = "%g" % quantity
    else:
        q_str = str(quantity)

    if "e" in q_str.lower():
        q_str = "%.4f" % quantity

    if "." in q_str:
        q_str = q_str.rstrip("0").rstrip(".")

    if q_str == "0" and not emit_zero_unit:
        return q_str

    return q_str + unit


def zero_quantity(val):
    if (
        re.match(r"^#[0-9a-f]+$", val)
        or re.match(r"^rgba\([0-9]+,[0-9]+,[0-9]+,[0-9.]+\)$", val)
        or val in COLOR_NAMES
    ):
        return "#0"

    num_match = re.match(
        r"^([+-]?[0-9]+\.?[0-9]*)(|em|ex|ch|rem|vw|vh|vmin|vmax|%|cm|mm|in|px|pt|pc)$",
        val,
    )
    if num_match:
        return "0"

    return val


def split_value(val):
    num_match = re.match(r"^([+-]?[0-9]+\.?[0-9]*)", val)
    if not num_match:
        return (None, val)

    num = num_match.group(1)
    unit = val[len(num) :]

    return (decimal.Decimal(num), unit)


def capitalize_font_name(name):
    return " ".join(
        [
            (word.capitalize() if len(word) > 2 else word.upper())
            for word in name.split()
        ]
    )


def class_selector(class_name):
    return "." + class_name
