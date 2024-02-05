from __future__ import absolute_import, division, print_function, unicode_literals

import io
import random
import string

from PIL import Image

from .ion import IS, IonBLOB, IonStruct, IonSymbol, ion_type, unannotated
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    convert_pdf_to_jpeg,
    disable_debug_log,
    jpeg_type,
    list_symbols,
    list_symbols_unsorted,
    quote_name,
)
from .yj_container import YJFragment, YJFragmentKey
from .yj_structure import (
    FORMAT_SYMBOLS,
    KFX_COVER_RESOURCE,
    METADATA_NAMES,
    METADATA_SYMBOLS,
    SYMBOL_FORMATS,
)
from .yj_versions import (
    PACKAGE_VERSION_PLACEHOLDERS,
    is_known_feature,
    is_known_generator,
    is_known_metadata,
)

if IS_PYTHON2:
    from .python_transition import repr, str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


class YJ_Metadata(object):
    def __init__(self, author_sort_fn=None, replace_existing_authors_with_sort=False):
        self.authors = []
        self.author_sort_fn = (
            author_sort_name if author_sort_fn is None else author_sort_fn
        )
        self.replace_existing_authors_with_sort = replace_existing_authors_with_sort
        self.title = self.cde_content_type = self.asin = self.cover_image_data = (
            self.description
        ) = None
        self.issue_date = self.language = self.publisher = self.book_id = (
            self.features
        ) = self.asset_id = None


class BookMetadata(object):
    def get_yj_metadata_from_book(self):
        yj_metadata = YJ_Metadata()
        authors = []

        fragment = self.fragments.get("$490")
        if fragment is not None:
            for cm in fragment.value.get("$491", {}):
                if cm.get("$495", "") == "kindle_title_metadata":
                    for kv in cm.get("$258", []):
                        key = kv.get("$492", "")
                        val = kv.get("$307", "")

                        if key == "author":
                            authors.append(val)
                        elif key == "title":
                            yj_metadata.title = val
                        elif key == "cde_content_type":
                            yj_metadata.cde_content_type = val
                        elif key == "ASIN":
                            yj_metadata.asin = val
                        elif key == "description":
                            yj_metadata.description = val
                        elif key == "issue_date":
                            yj_metadata.issue_date = val
                        elif key == "language":
                            yj_metadata.language = val
                        elif key == "publisher":
                            yj_metadata.publisher = val
                        elif key == "book_id":
                            yj_metadata.book_id = val
                        elif key == "asset_id":
                            yj_metadata.asset_id = val

        fragment = self.fragments.get("$258")
        if fragment is not None:
            for name, val in fragment.value.items():
                key = METADATA_NAMES.get(name, "")

                if key == "author" and not authors:
                    if " & " in val:
                        for author in val.split("&"):
                            authors.append(author.strip())
                    elif " and " in val:
                        auths = val.split(" and ")
                        if len(auths) == 2 and "," in auths[0] and "," not in auths[1]:
                            auths = auths[0].split(",") + [auths[1]]
                        for author in auths:
                            authors.append(author.strip())
                    elif val:
                        authors.append(val)

                elif key == "title" and not yj_metadata.title:
                    yj_metadata.title = val
                elif key == "cde_content_type" and not yj_metadata.cde_content_type:
                    yj_metadata.cde_content_type = val
                elif key == "ASIN" and not yj_metadata.asin:
                    yj_metadata.asin = val
                elif key == "description" and not yj_metadata.description:
                    yj_metadata.description = val
                elif key == "issue_date" and not yj_metadata.issue_date:
                    yj_metadata.issue_date = val
                elif key == "language" and not yj_metadata.language:
                    yj_metadata.language = val
                elif key == "publisher" and not yj_metadata.publisher:
                    yj_metadata.publisher = val
                elif key == "asset_id" and not yj_metadata.asset_id:
                    yj_metadata.asset_id = val

        yj_metadata.authors = []
        for author in authors:
            author = unsort_author_name(author)
            if author and author not in yj_metadata.authors:
                yj_metadata.authors.append(author)

        cover_image_data = self.get_cover_image_data()
        if cover_image_data is not None:
            yj_metadata.cover_image_data = cover_image_data

        yj_metadata.features = self.get_features()

        return yj_metadata

    def set_yj_metadata_to_book(self, yj_metadata):
        authors = (
            [yj_metadata.author_sort_fn(author) for author in yj_metadata.authors]
            if yj_metadata.authors is not None
            else None
        )

        if yj_metadata.asin is True:
            yj_metadata.asin = "".join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(32)
            )

        book_metadata_fragment = self.fragments.get("$490")
        metadata_fragment = self.fragments.get("$258")

        if book_metadata_fragment is None and metadata_fragment is None:
            log.error("Cannot set metadata due to missing metadata fragments in book")

        cover_image = None
        if yj_metadata.cover_image_data is not None:
            new_cover_image_data = self.fix_cover_image_data(
                yj_metadata.cover_image_data
            )
            if new_cover_image_data != self.get_cover_image_data():
                cover_image = self.set_cover_image_data(new_cover_image_data)

        if book_metadata_fragment is not None:
            for cm in book_metadata_fragment.value.get("$491", {}):
                if cm.get("$495", "") == "kindle_title_metadata":
                    new_ksv = []
                    for kv in cm.get("$258", []):
                        key = kv.get("$492", "")
                        val = kv.get("$307", "")

                        if (
                            key == "author"
                            and yj_metadata.replace_existing_authors_with_sort
                        ):
                            if authors is None:
                                authors = []

                            authors.append(yj_metadata.author_sort_fn(val))

                        elif (
                            (key == "author" and authors is not None)
                            or (key == "title" and yj_metadata.title is not None)
                            or (
                                key == "cde_content_type"
                                and yj_metadata.cde_content_type is not None
                            )
                            or (key == "ASIN" and yj_metadata.asin is not None)
                            or (key == "content_id" and yj_metadata.asin is not None)
                            or (key == "cover_image" and cover_image is not None)
                            or (
                                key == "description"
                                and yj_metadata.description is not None
                            )
                            or (
                                key == "issue_date"
                                and yj_metadata.issue_date is not None
                            )
                            or (key == "language" and yj_metadata.language is not None)
                            or (
                                key == "publisher" and yj_metadata.publisher is not None
                            )
                        ):
                            pass

                        elif key:
                            new_ksv.append((key, len(new_ksv), val))

                    if authors is not None:
                        for author in authors:
                            new_ksv.append(("author", len(new_ksv), author))

                    if yj_metadata.title is not None:
                        new_ksv.append(("title", len(new_ksv), yj_metadata.title))

                    if yj_metadata.cde_content_type is not None:
                        new_ksv.append(
                            (
                                "cde_content_type",
                                len(new_ksv),
                                yj_metadata.cde_content_type,
                            )
                        )

                    if yj_metadata.asin is not None:
                        new_ksv.append(("ASIN", len(new_ksv), yj_metadata.asin))
                        new_ksv.append(("content_id", len(new_ksv), yj_metadata.asin))

                    if cover_image is not None:
                        new_ksv.append(("cover_image", len(new_ksv), cover_image))

                    if yj_metadata.description is not None:
                        new_ksv.append(
                            ("description", len(new_ksv), yj_metadata.description)
                        )

                    if yj_metadata.issue_date is not None:
                        new_ksv.append(
                            ("issue_date", len(new_ksv), yj_metadata.issue_date)
                        )

                    if yj_metadata.language is not None:
                        new_ksv.append(("language", len(new_ksv), yj_metadata.language))

                    if yj_metadata.publisher is not None:
                        new_ksv.append(
                            ("publisher", len(new_ksv), yj_metadata.publisher)
                        )

                    cm[IS("$258")] = [
                        IonStruct(IS("$492"), k, IS("$307"), v)
                        for k, s, v in sorted(new_ksv)
                    ]

        if metadata_fragment is not None:
            mdx = metadata_fragment.value

            if not (len(mdx) == 0 or (len(mdx) == 1 and "$169" in mdx)):
                if authors is not None:
                    mdx[IS("$222")] = " & ".join(authors)
                else:
                    mdx.pop("$222", None)

                if yj_metadata.title is not None:
                    mdx[IS("$153")] = yj_metadata.title
                else:
                    mdx.pop("$153", None)

                if yj_metadata.cde_content_type is not None:
                    mdx[IS("$251")] = yj_metadata.cde_content_type
                else:
                    mdx.pop("$251", None)

                if yj_metadata.asin is not None:
                    mdx[IS("$224")] = yj_metadata.asin
                else:
                    mdx.pop("$224", None)

                if cover_image is not None:
                    mdx[IS("$424")] = IS(cover_image)
                else:
                    mdx.pop("$424", None)

                if yj_metadata.description is not None:
                    mdx[IS("$154")] = yj_metadata.description
                else:
                    mdx.pop("$154", None)

                if yj_metadata.issue_date is not None:
                    mdx[IS("$219")] = yj_metadata.issue_date
                else:
                    mdx.pop("$219", None)

                if yj_metadata.language is not None:
                    mdx[IS("$10")] = yj_metadata.language
                else:
                    mdx.pop("$10", None)

                if yj_metadata.publisher is not None:
                    mdx[IS("$232")] = yj_metadata.publisher
                else:
                    mdx.pop("$232", None)

    def has_metadata(self):
        return (
            self.fragments.get(YJFragmentKey(ftype="$490")) is not None
            or self.fragments.get(YJFragmentKey(ftype="$258")) is not None
        )

    def has_cover_data(self):
        return self.get_cover_image_data() is not None

    def get_asset_id(self):
        return self.get_metadata_value("asset_id")

    @property
    def cde_type(self):
        if not hasattr(self, "_cached_cde_type"):
            self._cached_cde_type = self.get_metadata_value("cde_content_type")

        return self._cached_cde_type

    @property
    def is_magazine(self):
        return self.cde_type == "MAGZ"

    @property
    def is_sample(self):
        return self.cde_type == "EBSP"

    @property
    def is_print_replica(self):
        if not hasattr(self, "_cached_is_print_replica"):
            self._cached_is_print_replica = (
                self.get_metadata_value(
                    "yj_textbook", category="kindle_capability_metadata"
                )
                is not None
            )

        return self._cached_is_print_replica

    @property
    def is_fixed_layout(self):
        if not hasattr(self, "_cached_is_fixed_layout"):
            self._cached_is_fixed_layout = (
                self.get_metadata_value("yj_fixed_layout", "kindle_capability_metadata")
                is not None
            )

        return self._cached_is_fixed_layout

    @property
    def is_illustrated_layout(self):
        if not hasattr(self, "_cached_is_illustrated_layout"):
            self._cached_is_illustrated_layout = (
                self.get_feature_value("yj.illustrated_layout") is not None
            )

        return self._cached_is_illustrated_layout

    @property
    def is_conditional_structure(self):
        if not hasattr(self, "_cached_is_conditional_structure"):
            self._cached_is_conditional_structure = self.get_feature_value(
                "yj.conditional_structure"
            ) is not None or (
                self.get_feature_value("reflow-style", default=0) == 5
                and not self.is_magazine
            )

        return self._cached_is_conditional_structure

    @property
    def is_kfx_v1(self):
        if not hasattr(self, "_cached_is_kfx_v1"):
            fragment = self.fragments.get("$270", first=True)
            self._cached_is_kfx_v1 = (
                fragment.value.get("version", 0) == 1 if fragment is not None else False
            )

        return self._cached_is_kfx_v1

    @property
    def has_pdf_resource(self):
        if not hasattr(self, "_cached_has_pdf_resource"):
            for fragment in self.fragments.get_all("$164"):
                if fragment.value.get("$161") == "$565":
                    self._cached_has_pdf_resource = True
                    break
            else:
                self._cached_has_pdf_resource = False

        return self._cached_has_pdf_resource

    def get_metadata_value(self, name, category="kindle_title_metadata", default=None):
        try:
            fragment = self.fragments.get("$490")
            if fragment is not None:
                for cm in fragment.value["$491"]:
                    if cm["$495"] == category:
                        for kv in cm["$258"]:
                            if kv["$492"] == name:
                                return kv["$307"]

            metadata_symbol = METADATA_SYMBOLS.get(name)
            if metadata_symbol is not None:
                fragment = self.fragments.get("$258")
                if fragment is not None and metadata_symbol in fragment.value:
                    return fragment.value[metadata_symbol]
        except Exception:
            pass

        return default

    def get_feature_value(
        self, feature, namespace="com.amazon.yjconversion", default=None
    ):
        if namespace == "format_capabilities":
            fragment = self.fragments.get("$593", first=True)
            if fragment is not None:
                for fc in fragment.value:
                    if fc.get("$492", "") == feature:
                        return fc.get("version", "")
        else:
            fragment = self.fragments.get("$585", first=True)
            if fragment is not None:
                for cf in fragment.value.get("$590", []):
                    if (
                        cf.get("$586", "") == namespace
                        and cf.get("$492", "") == feature
                    ):
                        vi = cf.get("$589", {}).get("version", {})
                        major_version = vi.get("$587", 0)
                        minor_version = vi.get("$588", 0)
                        return (
                            major_version
                            if minor_version == 0
                            else (major_version, minor_version)
                        )

        return default

    def get_generators(self):
        generators = set()

        for fragment in self.fragments.get_all("$270"):
            if "version" in fragment.value:
                package_version = fragment.value.get("$588", "")
                generators.add(
                    (
                        fragment.value.get("$587", ""),
                        (
                            package_version
                            if package_version not in PACKAGE_VERSION_PLACEHOLDERS
                            else ""
                        ),
                    )
                )

        return generators

    def get_features(self):
        features = set()

        features.add(("symbols", "max_id", self.symtab.local_min_id - 1))

        for fragment in self.fragments.get_all("$593"):
            for fc in fragment.value:
                features.add(
                    ("format_capabilities", fc.get("$492", ""), fc.get("version", ""))
                )

        fragment = self.fragments.get("$585", first=True)
        if fragment is not None:
            for cf in fragment.value.get("$590", []):
                vi = cf.get("$589", {}).get("version", {})
                major_version = vi.get("$587", 0)
                minor_version = vi.get("$588", 0)
                features.add(
                    (
                        cf.get("$586", ""),
                        cf.get("$492", ""),
                        (
                            major_version
                            if minor_version == 0
                            else (major_version, minor_version)
                        ),
                    )
                )

        return features

    def report_features_and_metadata(self, unknown_only=False):
        report_generators = set()
        for generator in sorted(self.get_generators()):
            generator_version = ("%s/%s" % generator) if generator[1] else generator[0]
            if not is_known_generator(generator[0], generator[1]):
                log.warning("Unknown kfxgen: %s" % generator_version)
            elif not unknown_only:
                report_generators.add(generator_version)

        if report_generators:
            log.info("kfxgen version: %s" % list_symbols(report_generators))

        report_features = set()
        for namespace, key, value in sorted(self.get_features()):
            value_str = (
                quote_name(value)
                if isinstance(value, str)
                else (
                    ".".join([str(v) for v in value])
                    if isinstance(value, tuple)
                    else str(value)
                )
            )
            if is_known_feature(namespace, key, value):
                if not unknown_only:
                    report_features.add("%s-%s" % (key, value_str))
            elif namespace == "symbols":
                log.warning(
                    "Unknown %s feature: %s-%s" % (namespace, key, str(value_str))
                )
            else:
                log.error(
                    "Unknown %s feature: %s-%s" % (namespace, key, str(value_str))
                )

        if report_features:
            log.info("Features: %s" % list_symbols(report_features))

        metadata = []
        fragment = self.fragments.get("$490", first=True)
        if fragment is not None:
            for cm in fragment.value.get("$491", {}):
                category = cm.get("$495", "")
                for kv in cm.get("$258", []):
                    metadata.append(
                        (
                            kv.get("$492", ""),
                            category,
                            len(metadata),
                            kv.get("$307", ""),
                        )
                    )

        fragment = self.fragments.get("$258", first=True)
        if fragment is not None:
            for name, val in fragment.value.items():
                name = METADATA_NAMES.get(name, name.tostring())
                if name == "reading_orders":
                    val = len(val)
                metadata.append((name, "metadata", len(metadata), val))

        fragment = self.fragments.get("$389")
        if fragment is not None:
            for book_navigation in fragment.value:
                for nav_container in book_navigation.get("$392", []):
                    if ion_type(nav_container) is IonSymbol:
                        nav_container = self.fragments.get(
                            ftype="$391", fid=nav_container
                        )

                    if nav_container is not None:
                        nav_container = unannotated(nav_container)
                        if nav_container.get("$235", None) == "$237":
                            num_pages = len(nav_container.get("$247", []))
                            if num_pages:
                                metadata.append(
                                    (
                                        "pages",
                                        "book_navigation",
                                        len(metadata),
                                        num_pages,
                                    )
                                )

        report_metadata = []
        for key, cat, seq, val in sorted(metadata):
            if not is_known_metadata(cat, key, val):
                log.warning("Unknown %s: %s=%s" % (cat, key, str(val)))
            elif not unknown_only:
                if key == "cover_image":
                    try:
                        cover_resource = self.fragments[
                            YJFragmentKey(ftype="$164", fid=val)
                        ].value

                        cover_raw_data = None
                        if "$165" in cover_resource:
                            cover_raw_media = self.fragments.get(
                                ftype="$417", fid=cover_resource["$165"]
                            )
                            if cover_raw_media is not None:
                                cover_raw_data = cover_raw_media.value.tobytes()

                        resource_height = cover_resource.get("$423", 0)
                        resource_width = cover_resource.get("$422", 0)

                        if (
                            not (resource_width and resource_height)
                        ) and cover_raw_data is not None:
                            with disable_debug_log():
                                cover = Image.open(io.BytesIO(cover_raw_data))
                                resource_width, resource_height = cover.size
                                cover.close()

                        val = "%dx%d" % (resource_width, resource_height)

                        cover_format = SYMBOL_FORMATS.get(
                            cover_resource["$161"], "unknown"
                        )

                        if cover_raw_data is not None:
                            cover_format = jpeg_type(cover_raw_data, cover_format)

                        if cover_format != "JPEG":
                            val += "-" + cover_format

                    except Exception:
                        val = "???"

                elif key == "dictionary_lookup":
                    val = "%s-to-%s" % (val.get("$474", "?"), val.get("$163", "?"))

                elif key == "description" and len(val) > 20:
                    val = "..."

                meta_str = "%s=%s" % (key, quote_name(str(val)))

                if meta_str not in report_metadata:
                    report_metadata.append(meta_str)

        if report_metadata:
            log.info("Metadata: %s" % list_symbols_unsorted(report_metadata))

    def get_cover_image_data(self):
        cover_image_resource = self.get_metadata_value("cover_image")
        if not cover_image_resource:
            return None

        cover_resource = self.fragments.get(ftype="$164", fid=cover_image_resource)
        if cover_resource is None:
            return None

        cover_fmt = cover_resource.value["$161"]
        if ion_type(cover_fmt) is IonSymbol:
            cover_fmt = SYMBOL_FORMATS[cover_fmt]

        cover_raw_media = self.fragments.get(
            ftype="$417", fid=cover_resource.value["$165"]
        )
        if cover_raw_media is None:
            return None

        return (
            "jpeg" if cover_fmt == "jpg" else cover_fmt,
            cover_raw_media.value.tobytes(),
        )

    def fix_cover_image_data(self, cover_image_data):
        fmt = cover_image_data[0]
        data = orig_data = cover_image_data[1]

        if fmt.lower() in ["jpg", "jpeg"] and not data.startswith(b"\xff\xd8\xff\xe0"):
            try:
                with disable_debug_log():
                    cover = Image.open(io.BytesIO(data))
                    outfile = io.BytesIO()
                    cover.save(outfile, "jpeg", quality=90)
                    cover.close()

                data = outfile.getvalue()
            except Exception:
                data = orig_data

            if data.startswith(b"\xff\xd8\xff\xe0"):
                log.info(
                    "Changed cover image from %s to JPEG/JFIF for Kindle lockscreen"
                    % jpeg_type(orig_data)
                )
            else:
                log.error(
                    "Failed to change cover image from %s to JPEG/JFIF"
                    % jpeg_type(orig_data)
                )
                data = orig_data

        return (fmt, data)

    def set_cover_image_data(self, cover_image_data, update_cover_section=True):
        fmt = cover_image_data[0].lower()
        if fmt == "jpeg":
            fmt = "jpg"

        if fmt != "jpg":
            raise Exception(
                "Cannot set KFX cover image format to %s, must be JPEG" % fmt.upper()
            )

        cover_image = self.get_metadata_value("cover_image")
        if cover_image is None:
            cover_image = KFX_COVER_RESOURCE
            cover_image_symbol = self.create_local_symbol(cover_image)
            self.fragments.append(
                YJFragment(
                    ftype="$164",
                    fid=cover_image_symbol,
                    value=IonStruct(IS("$175"), cover_image_symbol),
                )
            )

        data = cover_image_data[1]
        cover_resource = self.update_image_resource_and_media(
            cover_image, data, fmt, update_cover_section
        )

        if "$214" in cover_resource:
            with disable_debug_log():
                cover_thumbnail = Image.open(io.BytesIO(data))
                cover_thumbnail.thumbnail((512, 512), Image.ANTIALIAS)
                outfile = io.BytesIO()
                cover_thumbnail.save(
                    outfile, "jpeg" if fmt == "jpg" else fmt, quality=90
                )
                cover_thumbnail.close()

            thumbnail_data = outfile.getvalue()

            thumbnail_resource = unannotated(cover_resource["$214"])
            self.update_image_resource_and_media(
                str(thumbnail_resource), thumbnail_data, fmt
            )

        return cover_image

    def update_image_resource_and_media(
        self, resource_name, data, fmt, update_cover_section=False
    ):
        cover_resource = self.fragments.get(ftype="$164", fid=resource_name).value

        cover_resource[IS("$161")] = IS(FORMAT_SYMBOLS[fmt])
        cover_resource[IS("$162")] = "image/" + fmt

        cover_resource.pop("$56", None)
        cover_resource.pop("$57", None)
        cover_resource.pop("$66", None)
        cover_resource.pop("$67", None)

        cover = Image.open(io.BytesIO(data))
        width, height = cover.size
        cover.close()

        orig_width = cover_resource.get("$422", 0)
        orig_height = cover_resource.get("$423", 0)

        cover_resource[IS("$422")] = width
        cover_resource[IS("$423")] = height

        if "$165" in cover_resource:
            self.fragments[
                YJFragmentKey(ftype="$417", fid=cover_resource["$165"])
            ].value = IonBLOB(data)
        else:
            location = "%s.%s" % (resource_name, fmt)
            cover_resource[IS("$165")] = location
            self.fragments.append(
                YJFragment(
                    ftype="$417",
                    fid=self.create_local_symbol(location),
                    value=IonBLOB(data),
                )
            )

        if update_cover_section and (width != orig_width or height != orig_height):
            section_updated = False
            if self.locate_cover_image_resource_from_content() == resource_name:
                section_names = self.ordered_section_names()
                if len(section_names) > 0:
                    cover_section = self.fragments.get(
                        ftype="$260", fid=section_names[0]
                    ).value
                    page_templates = cover_section["$141"]
                    page_template = (
                        page_templates[0] if len(page_templates) == 1 else {}
                    )
                    if (
                        page_template.get("$159") == "$270"
                        and page_template.get("$156") == "$326"
                        and page_template.get("$140") == "$320"
                        and page_template.get("$66", -1) == orig_width
                        and page_template.get("$67", -1) == orig_height
                    ):
                        page_template[IS("$66")] = width
                        page_template[IS("$67")] = height
                        section_updated = True

            if not section_updated:
                log.info("First page image dimensions were not updated")

        return cover_resource

    def locate_cover_image_resource_from_content(self, replace_pdf=False):
        section_names = self.ordered_section_names()
        if not section_names:
            return None

        cover_section = self.fragments.get(ftype="$260", fid=section_names[0]).value
        for page_template in cover_section["$141"]:
            story_name = page_template.get("$176")
            if story_name:
                break
        else:
            return None

        cover_story = self.fragments.get(ftype="$259", fid=story_name).value

        def scan_content_for_image(content):
            if content.get("$159") == "$271" and "$175" in content:
                return content["$175"]

            for subcontent in content.get("$146", {}):
                img = scan_content_for_image(subcontent)
                if img is not None:
                    return img

            return None

        resource_name = scan_content_for_image(cover_story)
        if resource_name is None:
            return None

        cover_resource = self.fragments.get(ftype="$164", fid=resource_name).value
        if cover_resource[IS("$161")] != "$565":
            return resource_name

        if not replace_pdf:
            return None

        location = cover_resource["$165"]
        raw_media = self.fragments[YJFragmentKey(ftype="$417", fid=location)].value
        page_num = cover_resource.get("$564", 0) + 1

        try:
            jpeg_data = convert_pdf_to_jpeg(raw_media, page_num)
        except Exception as e:
            log.error(
                "Exception during conversion of PDF '%s' page %d to JPEG: %s"
                % (location, page_num, repr(e))
            )
            return None

        return self.set_cover_image_data(
            ("jpeg", jpeg_data), update_cover_section=False
        )


def author_sort_name(author):
    PERSON_SUFFIXES = {
        "phd",
        "md",
        "ba",
        "ma",
        "dds",
        "msts",
        "sr",
        "senior",
        "jr",
        "junior",
        "ii",
        "iii",
        "iv",
    }

    al = author.split()

    if len(al) < 2:
        return author

    if len(al) > 2 and al[-1].replace(".", "").lower() in PERSON_SUFFIXES:
        if al[-2].endswith(","):
            al[-2] = al[-2][:-1]

        al = al[0:-2] + ["%s %s" % (al[-2], al[-1])]

    if "," in "".join(al):
        return author

    return al[-1] + ", " + " ".join(al[:-1])


def unsort_author_name(author):
    if ", " in author:
        last, sep, first = author.partition(", ")
        author = first + " " + last

    return author
