from __future__ import absolute_import, division, print_function, unicode_literals

import io
import posixpath
import re

from PIL import Image

from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import (
    EXTS_OF_MIMETYPE,
    RESOURCE_TYPE_OF_EXT,
    convert_jxr_to_tiff,
    convert_pdf_to_jpeg,
    disable_debug_log,
    font_file_ext,
    image_file_ext,
    root_filename,
    urlrelpath,
)
from .yj_structure import SYMBOL_FORMATS

if IS_PYTHON2:
    from .python_transition import repr, urllib
else:
    import urllib.parse


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


USE_HIGHEST_RESOLUTION_IMAGE_VARIANT = True
FIX_PDF = True
FIX_JPEG_XR = True
JXR_TO_JPEG_QUALITY = 90
MIN_JPEG_QUALITY = 80
MAX_JPEG_QUALITY = 100
TILE_SIZE_REPORT_PERCENTAGE = 10


class Obj(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class KFX_EPUB_Resources(object):
    def get_external_resource(self, resource_name, ignore_variants=False):
        resource_obj = self.resource_cache.get(resource_name)
        if resource_obj is not None:
            return resource_obj

        resource = self.get_fragment(ftype="$164", fid=resource_name)

        if resource.pop("$175", "") != resource_name:
            raise Exception("Name of resource %s is incorrect" % resource_name)

        format = resource.pop("$161", None)

        if format in SYMBOL_FORMATS:
            extension = "." + SYMBOL_FORMATS[format]
        elif format is not None:
            log.error("Resource %s has unknown format: %s" % (resource_name, format))
            extension = ".bin"

        fixed_height = resource.pop("$67", None)
        fixed_width = resource.pop("$66", None)

        resource_height = resource.pop("$423", None) or fixed_height
        resource_width = resource.pop("$422", None) or fixed_width

        if "$636" in resource:
            tile_height = resource.pop("$638")
            tile_width = resource.pop("$637")
            tile_padding = resource.pop("$797", 0)

            with disable_debug_log():
                full_image = Image.new("RGB", (resource_width, resource_height))
                separate_tiles_size = tile_count = 0

                col = resource.pop("$636")
                for y, row in enumerate(col):
                    top_padding = 0 if y == 0 else tile_padding
                    bottom_padding = (
                        resource_height - tile_height * len(col)
                        if y == len(col) - 1
                        else tile_padding
                    )

                    for x, location in enumerate(row):
                        left_padding = 0 if x == 0 else tile_padding
                        right_padding = (
                            resource_width - tile_width * len(row)
                            if x == len(row) - 1
                            else tile_padding
                        )

                        tile_raw_media = self.locate_raw_media(location)
                        if tile_raw_media is not None:
                            tile_count += 1
                            separate_tiles_size += len(tile_raw_media)
                            tile = Image.open(io.BytesIO(tile_raw_media))
                            twidth, theight = tile.size
                            if (
                                twidth != tile_width + left_padding + right_padding
                                or theight != tile_height + top_padding + bottom_padding
                            ):
                                log.error(
                                    "Resource %s tile %d, %d size (%d, %d) does not have expected padding %d of (%d, %d) for %s"
                                    % (
                                        resource_name,
                                        x,
                                        y,
                                        twidth,
                                        theight,
                                        tile_padding,
                                        tile_width,
                                        tile_height,
                                        resource_name,
                                    )
                                )

                            crop = (
                                left_padding,
                                top_padding,
                                tile_width + left_padding,
                                tile_height + top_padding,
                            )
                            tile = tile.crop(crop)
                            full_image.paste(tile, (x * tile_width, y * tile_height))
                            tile.close()

                if full_image.size != (resource_width, resource_height):
                    log.error(
                        "Resource %s combined tiled image size is (%d, %d) but should be (%d, %d) for %s"
                        % (
                            resource_name,
                            full_image.size[0],
                            full_image.size[1],
                            resource_width,
                            resource_height,
                            resource_name,
                        )
                    )

                min_quality = MIN_JPEG_QUALITY
                max_quality = MAX_JPEG_QUALITY
                best_size_diff = best_quality = raw_media = None
                while True:
                    quality = (max_quality + min_quality) // 2
                    outfile = io.BytesIO()
                    full_image.save(
                        outfile,
                        "jpeg" if extension == ".jpg" else extension[1:],
                        quality=quality,
                    )
                    test_raw_media = outfile.getvalue()
                    outfile.close()

                    size_diff = abs(separate_tiles_size - len(test_raw_media))
                    if best_size_diff is None or size_diff < best_size_diff:
                        best_size_diff = size_diff
                        best_quality = quality
                        raw_media = test_raw_media

                    if separate_tiles_size > len(test_raw_media):
                        min_quality = quality + 1
                    else:
                        max_quality = quality - 1

                    if max_quality < min_quality:
                        break

                if (
                    best_size_diff * 100
                ) // separate_tiles_size > TILE_SIZE_REPORT_PERCENTAGE or True:
                    log.warning(
                        "Image resource %s has %d tiles with total size %d combined into image of size %d quality %d"
                        % (
                            resource_name,
                            tile_count,
                            separate_tiles_size,
                            len(raw_media),
                            best_quality,
                        )
                    )

            location = location.partition("-tile")[0]
        else:
            location = resource.pop("$165")
            search_path = resource.pop("$166", location)
            if search_path != location:
                log.error(
                    "Image resource %s has location %s != search_path %s"
                    % (resource_name, location, search_path)
                )

            raw_media = self.locate_raw_media(location)

        mime = resource.pop("$162", None)

        if mime in EXTS_OF_MIMETYPE:
            if extension == ".pobject" or extension == ".bin":
                if mime == "figure":
                    extension = image_file_ext(raw_media)
                else:
                    extension = EXTS_OF_MIMETYPE[mime][0]
        elif mime is not None:
            log.error(
                "Resource %s has unknown mime type: %s" % (resource_name, repr(mime))
            )

        location_fn = location

        location_fn = resource.pop(
            "yj.conversion.source_resource_filename", location_fn
        )
        location_fn = resource.pop("yj.authoring.source_file_name", location_fn)

        if (extension == ".pobject" or extension == ".bin") and "." in location_fn:
            extension = "." + location_fn.rpartition(".")[2]

        if not location_fn.endswith(extension):
            location_fn = location_fn.partition(".")[0] + extension

        resource.pop("$597", None)
        resource.pop("$57", None)
        resource.pop("$56", None)
        resource.pop("$499", None)
        resource.pop("$500", None)
        resource.pop("$137", None)
        resource.pop("$136", None)
        referred_resources = resource.pop("$167", [])

        if "$214" in resource:
            self.process_external_resource(resource.pop("$214"), save=False)

        if FIX_JPEG_XR and (format == "$548") and (raw_media is not None):
            try:
                tiff_data = convert_jxr_to_tiff(raw_media, location_fn)
            except Exception as e:
                log.error(
                    "Exception during conversion of JPEG-XR '%s' to TIFF: %s"
                    % (location_fn, repr(e))
                )
            else:
                with disable_debug_log():
                    img = Image.open(io.BytesIO(tiff_data))
                    ofmt, extension = (
                        ("PNG", ".png") if img.mode == "RGBA" else ("JPEG", ".jpg")
                    )
                    outfile = io.BytesIO()
                    img.save(outfile, ofmt, quality=JXR_TO_JPEG_QUALITY)
                    img.close()

                raw_media = outfile.getvalue()
                outfile.close()
                location_fn = location_fn.rpartition(".")[0] + extension

        suffix = ""
        if (
            FIX_PDF
            and format == "$565"
            and raw_media is not None
            and "$564" in resource
        ):
            page_num = resource["$564"] + 1
            try:
                jpeg_data = convert_pdf_to_jpeg(
                    raw_media, page_num, reported_errors=self.reported_pdf_errors
                )
            except Exception as e:
                log.error(
                    'Exception during conversion of PDF "%s" page %d to JPEG: %s'
                    % (location_fn, page_num, repr(e))
                )
            else:
                raw_media = jpeg_data
                extension = ".jpg"
                location_fn = location_fn.rpartition(".")[0] + extension
                suffix = "-page%d" % page_num
                resource.pop("$564")

        filename = self.resource_location_filename(
            location_fn, suffix, self.epub.IMAGE_FILEPATH
        )

        if not ignore_variants:
            for rr in resource.pop("$635", []):
                variant = self.get_external_resource(rr, ignore_variants=True)

                if (
                    USE_HIGHEST_RESOLUTION_IMAGE_VARIANT
                    and variant is not None
                    and variant.width > resource_width
                    and variant.height > resource_height
                ):
                    if self.DEBUG:
                        log.info(
                            "Replacing image %s (%dx%d) with variant %s (%dx%d)"
                            % (
                                filename,
                                resource_width,
                                resource_height,
                                variant.filename,
                                variant.width,
                                variant.height,
                            )
                        )

                    raw_media, filename, resource_width, resource_height = (
                        variant.raw_media,
                        variant.filename,
                        variant.width,
                        variant.height,
                    )

        if "$564" in resource:
            filename += "#page=%d" % (resource.pop("$564") + 1)

        self.check_empty(resource, "resource %s" % resource_name)

        resource_obj = self.resource_cache[resource_name] = Obj(
            raw_media=raw_media,
            filename=filename,
            extension=extension,
            format=format,
            mime=mime,
            location=location,
            width=resource_width,
            height=resource_height,
            referred_resources=referred_resources,
            manifest_entry=None,
        )

        return resource_obj

    def process_external_resource(
        self,
        resource_name,
        save=True,
        process_referred=False,
        save_referred=False,
        is_plugin=False,
        is_referred=False,
    ):
        resource_obj = self.get_external_resource(resource_name)

        if (
            save
            and self.save_resources
            and resource_obj.raw_media
            is not None
            is resource_obj.manifest_entry
            is None
        ):
            filename = (
                root_filename(resource_obj.location)
                if is_referred
                else resource_obj.filename
            )
            filename, fragment_sep, fragment = filename.partition("#")
            base_filename = filename
            cnt = 0
            while filename in self.epub.oebps_files:
                if (
                    self.epub.oebps_files[filename].binary_data
                    == resource_obj.raw_media
                ):
                    resource_obj.manifest_entry = self.epub.manifest_files[filename]
                    break

                if is_referred and cnt == 0:
                    log.error(
                        "Multiple referred resources exist with location %s"
                        % resource_obj.location
                    )

                fn, ext = posixpath.splitext(base_filename)
                filename = "%s_%d%s" % (fn, cnt, ext)
                cnt += 1
            else:
                resource_obj.manifest_entry = self.epub.manifest_resource(
                    filename,
                    data=resource_obj.raw_media,
                    height=resource_obj.height,
                    width=resource_obj.width,
                    mimetype=resource_obj.mime if is_referred else None,
                )

            resource_obj.filename = filename + fragment_sep + fragment
            resource_obj.is_saved = True

        if process_referred or save_referred:
            for rr in resource_obj.referred_resources:
                self.process_external_resource(rr, save=save_referred, is_referred=True)

        if is_referred:
            pass
        elif is_plugin and resource_obj.format not in ["$287", "$284"]:
            log.error(
                "Unexpected plugin resource format %s for %s"
                % (resource_obj.format, resource_name)
            )
        elif (not is_plugin) and resource_obj.extension == ".pobject":
            log.error(
                "Unexpected non-plugin resource format %s for %s"
                % (resource_obj.extension, resource_name)
            )

        return resource_obj

    def locate_raw_media(self, location, report_missing=True):
        try:
            raw_media = self.book_data["$417"][location]
            self.used_raw_media.add(location)
        except Exception:
            if report_missing:
                log.error("Missing bcRawMedia %s" % location)

            raw_media = None

        return raw_media

    def resource_location_filename(self, location, suffix, filepath_template):
        if (location, suffix) in self.location_filenames:
            return self.location_filenames[(location, suffix)]

        if location.startswith("/"):
            location = "_" + location[1:]

        safe_location = re.sub(r"[^A-Za-z0-9_/.-]", "_", location)
        safe_location = safe_location.replace("//", "/x/")

        path, sep, name = safe_location.rpartition("/")
        path += sep

        root, sep, ext = name.rpartition(".")
        ext = sep + ext
        resource_type = RESOURCE_TYPE_OF_EXT.get(ext, "resource")

        unique_part = self.unique_part_of_local_symbol(root)
        root = self.prefix_unique_part_of_symbol(unique_part, resource_type)

        for prefix in ["resource/", filepath_template[1:].partition("/")[0] + "/"]:
            if path.startswith(prefix):
                path = path[len(prefix) :]

        safe_filename = filepath_template % ("%s%s%s%s" % (path, root, suffix, ext))

        unique_count = 0
        oebps_files_lower = set([n.lower() for n in self.epub.oebps_files.keys()])

        while safe_filename.lower() in oebps_files_lower:
            safe_filename = filepath_template % (
                "%s%s%s-%d%s" % (path, root, suffix, unique_count, ext)
            )
            unique_count += 1

        self.location_filenames[(location, suffix)] = safe_filename
        return safe_filename

    def process_fonts(self):
        fonts = self.book_data.pop("$262", {})
        raw_fonts = self.book_data.pop("$418", {})
        raw_media = self.book_data.get("$417", {})
        used_fonts = {}

        for font in fonts.values():
            location = font.pop("$165")

            if location in used_fonts:
                font["src"] = 'url("%s")' % urllib.parse.quote(
                    urlrelpath(
                        used_fonts[location], ref_from=self.epub.STYLES_CSS_FILEPATH
                    )
                )
            elif location in raw_fonts or (
                self.book.is_kpf_prepub and location in raw_media
            ):
                raw_font = raw_fonts.pop(location, None) or raw_media.pop(location)

                filename = location
                if "." not in filename:
                    ext = font_file_ext(raw_font)
                    if not ext:
                        log.error(
                            "Font %s has unknown type (possibly obfuscated)" % filename
                        )
                        ext = ".font"

                    filename = "%s%s" % (filename, ext)

                filename = self.resource_location_filename(
                    filename, "", self.epub.FONT_FILEPATH
                )

                if filename not in self.epub.oebps_files:
                    self.epub.manifest_resource(filename, data=raw_font)

                font["src"] = 'url("%s")' % urlrelpath(
                    urllib.parse.quote(filename), ref_from=self.epub.STYLES_CSS_FILEPATH
                )
                used_fonts[location] = filename
            else:
                log.error("Missing bcRawFont %s" % location)

            for prop in ["$15", "$12", "$13"]:
                if prop in font and font[prop] == "$350":
                    font.pop(prop)

            self.fix_font_name(font["$11"], add=True)
            self.font_faces.append(self.convert_yj_properties(font))

        for location in raw_fonts:
            log.warning("Unused font file: %s" % location)
            filename = self.resource_location_filename(
                location, "", self.epub.FONT_FILEPATH
            )
            self.epub.manifest_resource(filename, data=raw_fonts[location])

    def uri_reference(
        self, uri, save=True, save_referred=None, manifest_external_refs=False
    ):
        purl = urllib.parse.urlparse(uri)

        if purl.scheme == "kfx":
            return self.process_external_resource(
                urllib.parse.unquote(purl.netloc + purl.path),
                is_plugin=None,
                save=save,
                save_referred=save_referred,
            ).filename

        if purl.scheme in ["navto", "navt"]:
            anchor = self.navto_anchor.get(
                (
                    urllib.parse.unquote(purl.netloc),
                    float(purl.fragment) if purl.fragment else 0.0,
                )
            )
            if anchor is not None:
                return self.anchor_as_uri(anchor)
            else:
                log.error("Failed to locate anchor for %s" % uri)
                return "/MISSING_NAVTO#%s_%s" % (
                    urllib.parse.unquote(purl.netloc),
                    purl.fragment,
                )

        if purl.scheme in ["http", "https"]:
            if manifest_external_refs:
                self.epub.manifest_resource(uri, external=True, report_dupe=False)

            return uri

        if purl.scheme != "mailto":
            log.error("Unexpected URI scheme: %s" % uri)

        return uri

    def unique_file_id(self, filename):
        if filename in self.file_ids:
            return self.file_ids[filename]

        id = re.sub(r"[^A-Za-z0-9.-]", "_", filename.rpartition("/")[2][:64])

        if not re.match(r"^[A-Za-z]", id[0]):
            id = "id_" + id

        if id in self.file_ids.values():
            base_id = id
            unique_count = 0
            while id in self.file_ids.values():
                id = "%s_%d" % (base_id, unique_count)
                unique_count += 1

        self.file_ids[filename] = id
        return id
