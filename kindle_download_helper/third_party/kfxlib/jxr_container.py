from __future__ import absolute_import, division, print_function, unicode_literals

import sys
import uuid

from .jxr_image import JXRImage
from .jxr_misc import Deserializer, bytes_to_separated_hex
from .message_logging import log

if sys.version_info[0] == 2:
    str = type("")


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


FIELD_TYPE_LEN = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 1,
    7: 1,
    8: 2,
    9: 4,
    10: 8,
    11: 4,
    12: 8,
}

LEN_FMT = {
    1: "B",
    2: "s",
    3: "<H",
    4: "<L",
    6: "b",
    7: "s",
    8: "<h",
    9: "<l",
    11: "<f",
    12: "<d",
}

SUPPORTED_PIXEL_FORMATS = {
    "24c3dd6f-034e-fe4b-b185-3d77768dc905": "BlackWhite",
    "24c3dd6f-034e-fe4b-b185-3d77768dc908": "8bppGray",
    "24c3dd6f-034e-fe4b-b185-3d77768dc90b": "16bppGray",
    "24c3dd6f-034e-fe4b-b185-3d77768dc90c": "24bppBGR",
    "24c3dd6f-034e-fe4b-b185-3d77768dc90d": "24bppRGB",
    "24c3dd6f-034e-fe4b-b185-3d77768dc90f": "32bppRGBA",
    "24c3dd6f-034e-fe4b-b185-3d77768dc920": "24bpp3Channels",
    "24c3dd6f-034e-fe4b-b185-3d77768dc921": "32bpp4Channels",
}


class JXRContainer(object):
    def __init__(self, data):
        header = Deserializer(data)

        tif_signature = header.extract(4)
        if tif_signature != b"\x49\x49\xbc\x01":
            raise Exception(
                "TIF signature is incorrect: %s" % bytes_to_separated_hex(tif_signature)
            )

        ifd_offset = header.unpack("<L", "ifd_offset")
        header.extract(ifd_offset - header.offset)

        pixel_format = ""
        self.image_width = self.image_height = image_offset = image_byte_count = (
            self.image_data
        ) = None

        num_entries = header.unpack("<H", "num_entries")

        def field_value():
            return Deserializer(field_data).unpack(LEN_FMT[field_type], "field_value")

        for i in range(num_entries):
            field_tag = header.unpack("<H", "field_tag")
            field_type = header.unpack("<H", "field_type")
            field_count = header.unpack("<L", "field_count")

            field_data_len = FIELD_TYPE_LEN[field_type] * field_count
            if field_data_len <= 4:
                field_data = header.extract(field_data_len)
                header.extract(4 - field_data_len)
            else:
                field_data_or_offset = header.unpack("<L", "field_data_or_offset")
                field_data = data[
                    field_data_or_offset : field_data_or_offset + field_data_len
                ]

            if field_tag == 0xBC01:
                pixel_format = str(uuid.UUID(bytes=field_data))
            elif field_tag == 0xBC80:
                self.image_width = field_value()
            elif field_tag == 0xBC81:
                self.image_height = field_value()
            elif field_tag == 0xBCC0:
                image_offset = field_value()
            elif field_tag == 0xBCC1:
                image_byte_count = field_value()

        if not (
            pixel_format
            and self.image_width
            and self.image_height
            and image_offset
            and (image_byte_count is not None)
        ):
            raise Exception(
                "Missing required TIFF field tag: pixel_format=%s width=%s height=%s offset=%s byte-count=%s"
                % (
                    pixel_format,
                    self.image_width,
                    self.image_height,
                    image_offset,
                    image_byte_count,
                )
            )

        if pixel_format not in SUPPORTED_PIXEL_FORMATS:
            log.warning("Unsupported pixel format: %s" % pixel_format)

        ifd_offset = header.unpack("<L", "ifd_offset")
        if ifd_offset != 0:
            raise Exception(
                "File contains multiple images - only a single image is supported"
            )

        if image_byte_count > 0:
            self.image_data = data[image_offset : image_offset + image_byte_count]

            if len(self.image_data) < image_byte_count:
                log.warning(
                    "File is truncated (missing %d bytes of image data)"
                    % (image_byte_count - len(self.image_data))
                )
        else:
            self.image_data = data[image_offset:]

    def unpack_image(self):
        jxr_image = JXRImage(self.image_data)

        im = jxr_image.decode()

        if (
            jxr_image.image_width != self.image_width
            or jxr_image.image_height != self.image_height
        ):
            log.warning(
                "Expected image size %dx%d but found %dx%d"
                % (
                    self.image_width,
                    self.image_height,
                    jxr_image.image_width,
                    jxr_image.image_height,
                )
            )

        return im
