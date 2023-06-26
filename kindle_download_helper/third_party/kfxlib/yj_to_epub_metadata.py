from __future__ import absolute_import, division, print_function, unicode_literals

from .message_logging import log
from .python_transition import IS_PYTHON2
from .yj_structure import METADATA_NAMES, SYM_TYPE
from .yj_to_epub_properties import (
    DEFAULT_DOCUMENT_FONT_FAMILY,
    DEFAULT_DOCUMENT_FONT_SIZE,
    DEFAULT_DOCUMENT_LINE_HEIGHT,
    DEFAULT_FONT_NAMES,
    DEFAULT_KC_COMIC_FONT_SIZE,
)

if IS_PYTHON2:
    from .python_transition import str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


ORIENTATIONS = {
    "$385": "portrait",
    "$386": "landscape",
    "$349": "none",
}


class KFX_EPUB_Metadata(object):
    def process_document_data(self):
        document_data = self.book_data.pop("$538", {})

        if "$433" in document_data:
            orientation_lock_ = document_data.pop("$433")
            if orientation_lock_ in ORIENTATIONS:
                self.epub.orientation_lock = ORIENTATIONS[orientation_lock_]
            else:
                log.error("Unexpected orientation_lock: %s" % orientation_lock_)
                self.epub.orientation_lock = "none"
        else:
            self.epub.orientation_lock = "none"

        if "$436" in document_data:
            selection = document_data.pop("$436")
            if selection not in ["$442", "$441"]:
                log.error("Unexpected document selection: %s" % selection)

        if "$477" in document_data:
            spacing_percent_base = document_data.pop("$477")
            if spacing_percent_base != "$56":
                log.error(
                    "Unexpected document spacing_percent_base: %s"
                    % spacing_percent_base
                )

        if "$581" in document_data:
            pan_zoom = document_data.pop("$581")
            if pan_zoom != "$441":
                log.error("Unexpected document pan_zoom: %s" % pan_zoom)

        if "$665" in document_data:
            self.epub.set_book_type("comic")
            comic_panel_view_mode = document_data.pop("$665")
            if comic_panel_view_mode != "$666":
                log.error(
                    "Unexpected comic panel view mode: %s" % comic_panel_view_mode
                )

        if "$668" in document_data:
            auto_contrast = document_data.pop("$668")
            if auto_contrast != "$573":
                log.error("Unexpected auto_contrast: %s" % auto_contrast)

        document_data.pop("$597", None)

        if "max_id" in document_data:
            max_id = document_data.pop("max_id")
            if self.book_symbol_format != SYM_TYPE.SHORT:
                log.error(
                    "Unexpected document_data max_id=%s for %s symbol format"
                    % (max_id, self.book_symbol_format)
                )
        elif self.book_symbol_format == SYM_TYPE.SHORT:
            log.error(
                "Book has %s symbol format without document_data max_id"
                % self.book_symbol_format
            )

        document_data.pop("yj.semantics.book_theme_metadata", None)

        document_data.pop("yj.semantics.containers_with_semantics", None)

        document_data.pop("yj.semantics.page_number_begin", None)

        document_data.pop("yj.print.settings", None)
        document_data.pop("yj.authoring.auto_panel_settings_auto_mask_color_flag", None)
        document_data.pop("yj.authoring.auto_panel_settings_mask_color", None)
        document_data.pop("yj.authoring.auto_panel_settings_opacity", None)
        document_data.pop("yj.authoring.auto_panel_settings_padding_bottom", None)
        document_data.pop("yj.authoring.auto_panel_settings_padding_left", None)
        document_data.pop("yj.authoring.auto_panel_settings_padding_right", None)
        document_data.pop("yj.authoring.auto_panel_settings_padding_top", None)

        self.reading_orders = document_data.pop("$169", [])

        self.font_name_replacements["default"] = DEFAULT_DOCUMENT_FONT_FAMILY

        doc_style = self.process_content_properties(document_data)

        column_count = doc_style.pop("column-count", "auto")
        if column_count != "auto":
            log.warning("Unexpected document column_count: %s" % column_count)

        self.epub.page_progression_direction = doc_style.pop("direction", "ltr")

        self.default_font_family = doc_style.pop(
            "font-family", DEFAULT_DOCUMENT_FONT_FAMILY
        )

        for default_name in DEFAULT_FONT_NAMES:
            for font_family in self.split_font_family_value(self.default_font_family):
                self.font_name_replacements[default_name] = font_family

        self.default_font_size = doc_style.pop("font-size", DEFAULT_DOCUMENT_FONT_SIZE)
        if self.default_font_size not in [
            DEFAULT_DOCUMENT_FONT_SIZE,
            DEFAULT_KC_COMIC_FONT_SIZE,
        ]:
            log.warning("Unexpected document font-size: %s" % self.default_font_size)

        self.default_line_height = doc_style.pop(
            "line-height", DEFAULT_DOCUMENT_LINE_HEIGHT
        )
        if self.default_line_height != DEFAULT_DOCUMENT_LINE_HEIGHT:
            log.warning(
                "Unexpected document line-height: %s" % self.default_line_height
            )

        self.epub.writing_mode = doc_style.pop("writing-mode", "horizontal-tb")
        if self.epub.writing_mode not in [
            "horizontal-tb",
            "vertical-lr",
            "vertical-rl",
        ]:
            log.warning("Unexpected document writing-mode: %s" % self.epub.writing_mode)

        self.check_empty(doc_style.properties, "document data styles")
        self.check_empty(document_data, "$538")

    def process_content_features(self):
        content_features = self.book_data.pop("$585", {})

        for feature in content_features.pop("$590", []):
            key = "%s/%s" % (feature.pop("$586", ""), feature.pop("$492", ""))
            version_info = feature.pop("$589", {})
            version = version_info.pop("version", {})
            version.pop("$587", "")
            version.pop("$588", "")

            self.check_empty(version_info, "content_features %s version_info" % key)
            self.check_empty(feature, "content_features %s feature" % key)

        if content_features.pop("$598", content_features.pop("$155", "$585")) != "$585":
            log.error("content_features id/kfx_id is incorrect")

        self.check_empty(content_features, "$585")

    def process_metadata(self):
        self.cover_resource = None

        book_metadata = self.book_data.pop("$490", {})

        for categorised_metadata in book_metadata.pop("$491", []):
            category = categorised_metadata.pop("$495")
            for metadata in categorised_metadata.pop("$258"):
                key = metadata.pop("$492")
                self.process_metadata_item(category, key, metadata.pop("$307"))
                self.check_empty(
                    metadata, "categorised_metadata %s/%s" % (category, key)
                )

            self.check_empty(categorised_metadata, "categorised_metadata %s" % category)

        self.check_empty(book_metadata, "$490")

        for key, value in self.book_data.pop("$258", {}).items():
            self.process_metadata_item("", METADATA_NAMES.get(key, str(key)), value)

        if self.epub.fixed_layout and not self.epub.is_print_replica:
            self.epub.set_book_type("comic")

    def process_metadata_item(self, category, key, value):
        cat_key = "%s/%s" % (category, key) if category else key

        if cat_key == "kindle_title_metadata/ASIN" or cat_key == "ASIN":
            if not self.epub.asin:
                self.epub.asin = value
        elif cat_key == "kindle_title_metadata/author":
            if value:
                self.epub.authors.insert(0, value)
        elif cat_key == "kindle_title_metadata/author_pronunciation":
            if value:
                self.epub.author_pronunciations.insert(0, value)
        elif cat_key == "author":
            if not self.epub.authors:
                self.epub.authors = [a.strip() for a in value.split("&") if a]
        elif (
            cat_key == "kindle_title_metadata/cde_content_type"
            or cat_key == "cde_content_type"
        ):
            self.cde_content_type = value
            if value == "MAGZ":
                self.epub.set_book_type("magazine")
            elif value == "EBSP":
                self.epub.is_sample = True
        elif cat_key == "kindle_title_metadata/description" or cat_key == "description":
            self.epub.description = value.strip()
        elif cat_key == "kindle_title_metadata/cover_image":
            self.cover_resource = value
        elif cat_key == "cover_image":
            self.cover_resource = value
        elif cat_key == "kindle_title_metadata/dictionary_lookup":
            self.epub.is_dictionary = True
            self.epub.source_language = value.pop("$474")
            self.epub.target_language = value.pop("$163")
            self.check_empty(value, "kindle_title_metadata/dictionary_lookup")
        elif cat_key == "kindle_title_metadata/issue_date":
            self.epub.pubdate = value
        elif cat_key == "kindle_title_metadata/language" or cat_key == "language":
            self.epub.language = self.fix_language(value)
        elif cat_key == "kindle_title_metadata/publisher" or cat_key == "publisher":
            self.epub.publisher = value.strip()
        elif cat_key == "kindle_title_metadata/title" or cat_key == "title":
            if not self.epub.title:
                self.epub.title = value.strip()
        elif cat_key == "kindle_title_metadata/title_pronunciation":
            if not self.epub.title_pronunciation:
                self.epub.title_pronunciation = value.strip()
        elif cat_key == "kindle_ebook_metadata/book_orientation_lock":
            if value != self.epub.orientation_lock:
                log.error(
                    "Conflicting orientation lock values: %s, %s"
                    % (self.epub.orientation_lock, value)
                )
            self.epub.orientation_lock = value
        elif cat_key == "kindle_title_metadata/is_dictionary":
            self.epub.is_dictionary = value
        elif cat_key == "kindle_title_metadata/is_sample":
            self.epub.is_sample = value
        elif cat_key == "kindle_title_metadata/override_kindle_font":
            self.epub.override_kindle_font = value
        elif cat_key == "kindle_capability_metadata/continuous_popup_progression":
            self.epub.set_book_type("comic")
        elif cat_key == "kindle_capability_metadata/yj_fixed_layout":
            self.epub.fixed_layout = True
        elif cat_key == "kindle_capability_metadata/yj_forced_continuous_scroll":
            self.epub.scrolled_continuous = True
        elif cat_key == "kindle_capability_metadata/yj_guided_view_native":
            self.epub.guided_view_native = True
        elif cat_key == "kindle_capability_metadata/yj_publisher_panels":
            self.epub.set_book_type("comic")
            self.epub.region_magnification = True
        elif cat_key == "kindle_capability_metadata/yj_facing_page":
            self.epub.set_book_type("comic")
        elif cat_key == "kindle_capability_metadata/yj_double_page_spread":
            self.epub.set_book_type("comic")
        elif cat_key == "kindle_capability_metadata/yj_textbook":
            self.epub.set_book_type("print replica")
        elif cat_key == "kindle_capability_metadata/yj_illustrated_layout":
            self.epub.illustrated_layout = self.epub.html_cover = True
        elif cat_key == "reading_orders":
            if not self.reading_orders:
                self.reading_orders = value
        elif cat_key == "support_landscape":
            if value is False and self.epub.orientation_lock == "none":
                self.epub.orientation_lock = "portrait"
        elif cat_key == "support_portrait":
            if value is False and self.epub.orientation_lock == "none":
                self.epub.orientation_lock = "landscape"
