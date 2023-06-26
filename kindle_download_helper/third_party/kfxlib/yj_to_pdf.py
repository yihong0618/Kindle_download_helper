from __future__ import absolute_import, division, print_function, unicode_literals

import io

from PIL import Image

try:
    import PyPDF2
except ImportError:
    try:
        from . import PyPDF2
    except ImportError:
        PyPDF2 = None


from .ion import (
    IonAnnotation,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    ion_type,
)
from .message_logging import log
from .utilities import convert_jxr_to_tiff, disable_debug_log, list_symbols
from .yj_container import YJFragmentKey

__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


class ImageResource(object):
    def __init__(self, location, image_format, data):
        self.location = location
        self.image_format = image_format
        self.data = data


class KFX_PDF(object):
    def __init__(self, book):
        self.book = book

    def extract_pdf_resources(self):
        ordered_pdfs = self.get_ordered_images(["$565"])

        if len(ordered_pdfs) == 0:
            pdf_data = None
        elif len(ordered_pdfs) == 1:
            pdf_data = ordered_pdfs[0].data
        elif PyPDF2 is None:
            log.error("PyPDF2 package is missing. Unable to combine PDF resources")
            pdf_data = None
        else:
            try:
                merger = PyPDF2.PdfFileMerger()
                for single_pdf in ordered_pdfs:
                    merger.append(fileobj=io.BytesIO(single_pdf.data))

                merged_file = io.BytesIO()
                merger.write(merged_file)
                pdf_data = merged_file.getvalue()
                merged_file.close()
            except Exception as e:
                log.error(repr(e))
                pdf_data = None

            if pdf_data is not None:
                log.info(
                    "Combined %d PDF resources into a single file" % len(ordered_pdfs)
                )

        return pdf_data

    def convert_image_resources(self):
        ordered_images = self.get_ordered_images(
            ["$286", "$285", "$548", "$284"],
            include_unreferenced=False,
            allow_duplicates=True,
        )
        return convert_images_to_pdf_data(ordered_images)

    def get_ordered_images(
        self, formats, include_unreferenced=True, allow_duplicates=False
    ):
        image_resource_location = {}
        image_resources = {}

        for fragment in self.book.fragments.get_all("$164"):
            resource = fragment.value
            resource_format = resource.get("$161")
            if resource_format in formats:
                location = resource.get("$165")
                if location is not None and location not in image_resources:
                    raw_media = self.book.fragments.get(ftype="$417", fid=location)
                    if raw_media is not None:
                        image_resource_location[fragment.fid] = location
                        image_resources[location] = ImageResource(
                            location, resource_format, raw_media.value
                        )

        ordered_images = []
        unused_image_resource_ids = set(image_resources.keys())

        for fid in self.collect_image_references(allow_duplicates):
            location = image_resource_location.get(fid)
            image_resource = image_resources.get(location)
            if image_resource is not None:
                ordered_images.append(image_resource)
                unused_image_resource_ids.discard(location)

        if unused_image_resource_ids and include_unreferenced:
            log.error(
                "Found unreferenced resources: %s"
                % list_symbols(unused_image_resource_ids)
            )
            for fid in unused_image_resource_ids:
                ordered_images.append(image_resources[fid])

        return ordered_images

    def collect_image_references(self, allow_duplicates=False):
        processed_story_names = set()
        ordered_image_resources = []

        def collect_section_info(section_name):
            pending_story_names = []
            section_image_resources = set()

            def walk_content(data, content_key):
                data_type = ion_type(data)

                if data_type is IonAnnotation:
                    walk_content(data.value, content_key)

                elif data_type is IonList:
                    for i, fc in enumerate(data):
                        if (
                            content_key in {"$146", "$274"}
                            and self.book.is_kpf_prepub
                            and ion_type(fc) is IonSymbol
                        ):
                            fc = self.book.fragments[
                                YJFragmentKey(ftype="$608", fid=fc)
                            ]

                        walk_content(fc, content_key)

                elif data_type is IonSExp:
                    for fc in data:
                        walk_content(fc, content_key)

                elif data_type is IonStruct:
                    annot_type = data.get("$687")
                    typ = data.get("$159")

                    if typ == "$271":
                        resource_name = data.get("$175")
                        if (
                            resource_name is not None
                            and resource_name not in section_image_resources
                        ):
                            section_image_resources.add(resource_name)

                            if (
                                allow_duplicates
                                or resource_name not in ordered_image_resources
                            ):
                                ordered_image_resources.append(resource_name)

                    if "$141" in data:
                        for pt in data["$141"]:
                            if isinstance(pt, IonAnnotation):
                                pt = pt.value

                            walk_content(pt, "$141")

                    if "$683" in data:
                        walk_content(data["$683"], "$683")

                    if "$749" in data:
                        walk_content(
                            self.book.fragments[
                                YJFragmentKey(ftype="$259", fid=data["$749"])
                            ],
                            "$259",
                        )

                    if "$146" in data:
                        walk_content(data["$146"], "$274" if typ == "$274" else "$146")

                    if "$145" in data and annot_type not in ["$584", "$690"]:
                        fv = data["$145"]
                        if ion_type(fv) is not IonStruct:
                            walk_content(fv, "$145")

                    if "$176" in data and content_key != "$259":
                        fv = data["$176"]

                        if self.book.is_conditional_structure:
                            if fv not in pending_story_names:
                                pending_story_names.append(fv)
                        else:
                            if fv not in processed_story_names:
                                walk_content(
                                    self.book.fragments[
                                        YJFragmentKey(ftype="$259", fid=fv)
                                    ],
                                    "$259",
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
                            walk_content(fv, fk)

            walk_content(
                self.book.fragments[YJFragmentKey(ftype="$260", fid=section_name)],
                "$260",
            )

            for story_name in pending_story_names:
                if story_name not in processed_story_names:
                    walk_content(
                        self.book.fragments[
                            YJFragmentKey(ftype="$259", fid=story_name)
                        ],
                        "$259",
                    )
                    processed_story_names.add(story_name)

        for section_name in self.book.ordered_section_names():
            collect_section_info(section_name)

        return ordered_image_resources


def convert_images_to_pdf_data(ordered_images):
    if len(ordered_images) == 0:
        pdf_data = None
    else:
        image_list = []
        for image_resource in ordered_images:
            image_data = image_resource.data

            if image_resource.image_format == "$548":
                try:
                    image_data = convert_jxr_to_tiff(
                        image_data, image_resource.location
                    )
                except Exception as e:
                    log.error(
                        "Exception during conversion of JPEG-XR '%s' to TIFF: %s"
                        % (image_resource.location, repr(e))
                    )

            with disable_debug_log():
                image = Image.open(io.BytesIO(image_data))
                image = image.convert("RGB")
            image_list.append(image)

        first_image = image_list.pop(0)
        pdf_file = io.BytesIO()

        with disable_debug_log():
            first_image.save(pdf_file, "pdf", save_all=True, append_images=image_list)

            for image in image_list:
                image.close()

            first_image.close()

        pdf_data = pdf_file.getvalue()
        pdf_file.close()

    return pdf_data
