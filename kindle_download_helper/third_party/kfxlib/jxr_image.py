from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import math
import sys

from PIL import Image

from .jxr_misc import Deserializer, bytes_to_separated_hex
from .message_logging import log

if sys.version_info[0] == 2:
    str = type("")


__copyright__ = "2016-2022, John Howell <jhowell@acm.org>, based on pseudo-code in the ITU-T T.832 08/2016 specification with corrections"


DEBUG0 = False
DEBUG1 = False
DEBUG2 = False


DC = 0
LP = 1
HP = 2
Flex = 3

YONLY = 0
YUV420 = 1
YUV422 = 2
YUV444 = 3
YUVK = 4
NCOMPONENT = 6

INTERNAL_COLOR_NAME = {
    YONLY: "Y",
    YUV420: "YUV420",
    YUV422: "YUV422",
    YUV444: "YUV444",
    YUVK: "YUK",
    NCOMPONENT: "NCOMPONENT",
}

YONLY = 0
YUV420 = 1
YUV422 = 2
YUV444 = 3
CMYK = 4
CMYKDIRECT = 5
NCOMPONENT = 6
RGB = 7
RGBE = 8

OUTPUT_COLOR_NAME = {
    YONLY: "Y",
    YUV420: "YUV420",
    "YUV422": YUV422,
    YUV444: "YUV444",
    CMYK: "CMYK",
    CMYKDIRECT: "CMYK Direct",
    NCOMPONENT: "NCOMPONENT",
    RGB: "RGB",
    RGBE: "RGBE",
}


BD1WHITE1 = 0
BD8 = 1
BD16 = 2
BD16S = 3
BD16F = 4
BD32S = 6
BD32F = 7
BD5 = 8
BD10 = 9
BD565 = 10
BD1BLACK1 = 15

OUTPUT_BITDEPTH_NAME = {
    BD1WHITE1: "BD1WHITE1",
    BD8: "BD8",
    BD16: "BD16",
    BD16S: "BD16S",
    BD16F: "BD16F",
    BD32S: "BD32S",
    BD32F: "BD32F",
    BD5: "BD5",
    BD10: "BD10",
    BD565: "BD565",
    BD1BLACK1: "BD1BLACK1",
}

UNIFORM = 0
SEPARATE = 1
INDEPENDENT = 2

COMPONENT_MODE_NAMES = {
    UNIFORM: "UNIFORM",
    SEPARATE: "SEPARATE",
    INDEPENDENT: "INDEPENDENT",
}

ALL_BANDS = 0
NOFLEXBITS = 1
NOHIGHPASS = 2
DCONLY = 3

PRESENT_BAND_NAMES = {
    ALL_BANDS: "ALL_BANDS",
    NOFLEXBITS: "NOFLEXBITS",
    NOHIGHPASS: "NOHIGHPASS",
    DCONLY: "DCONLY",
}

PREDICT_FROM_LEFT = 0
PREDICT_FROM_TOP = 1
PREDICT_FROM_TOP_LEFT = 2
NO_PREDICTION = 3

PREDICT_NAME = {
    PREDICT_FROM_LEFT: "PREDICT_FROM_LEFT",
    PREDICT_FROM_TOP: "PREDICT_FROM_TOP",
    PREDICT_FROM_TOP_LEFT: "PREDICT_FROM_TOP_LEFT",
    NO_PREDICTION: "NO_PREDICTION",
}

XFRM_SUBORDINATE_NAME = {
    0: "TL",
    1: "BL",
    2: "TR",
    3: "BR",
    4: "RT",
    5: "RB",
    6: "LT",
    7: "LB",
}

NO_OVERLAP_FILTERING = 0
SECOND_LEVEL_OVERLAP_FILTERING = 1
FIRST_AND_SECOND_LEVEL_OVERLAP_FILTERING = 2

OVERLAP_MODE_NAME = {
    NO_OVERLAP_FILTERING: "NO_OVERLAP_FILTERING",
    SECOND_LEVEL_OVERLAP_FILTERING: "SECOND_LEVEL_OVERLAP_FILTERING",
    FIRST_AND_SECOND_LEVEL_OVERLAP_FILTERING: "FIRST_AND_SECOND_LEVEL_OVERLAP_FILTERING",
}

ICT4x4InvPermArr = [0, 8, 4, 13, 2, 15, 3, 14, 1, 12, 5, 9, 7, 11, 6, 10]
ICT4x4PermArr = [0, 8, 4, 6, 2, 10, 14, 12, 1, 11, 15, 13, 9, 3, 7, 5]

iHierScanOrder = [0, 4, 1, 5, 8, 12, 9, 13, 2, 6, 3, 7, 10, 14, 11, 15]

grgiZigzagInv4x4H = [None, 1, 4, 5, 2, 8, 6, 9, 3, 12, 10, 7, 13, 11, 14, 15]
grgiZigzagInv4x4V = [None, 4, 8, 5, 1, 12, 9, 6, 2, 13, 3, 15, 7, 10, 14, 11]

grgiZigzagInv4x4H_ = [None, 5, 10, 12, 1, 2, 8, 4, 6, 9, 3, 14, 13, 7, 11, 15]
grgiZigzagInv4x4V_ = [None, 10, 2, 12, 5, 9, 4, 8, 1, 13, 6, 15, 14, 3, 11, 7]

iTransposeFlex = [None, 5, 1, 6, 10, 12, 8, 14, 2, 4, 3, 7, 9, 13, 11, 15]

mb_pixel_map = [0, 1, 5, 4, 2, 3, 7, 6, 10, 11, 15, 14, 8, 9, 13, 12]


NumBlkCBPHPDelta1 = [[0, -1, 0, 1, 1]]

NumBlkCBPHPDelta2 = [[2, 2, 1, 1, -1, -2, -2, -2, -3]]

YX4 = [
    (0, 0),
    (0, 1),
    (0, 2),
    (0, 3),
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (2, 0),
    (2, 1),
    (2, 2),
    (2, 3),
    (3, 0),
    (3, 1),
    (3, 2),
    (3, 3),
]
XY4 = [
    (0, 0),
    (1, 0),
    (2, 0),
    (3, 0),
    (0, 1),
    (1, 1),
    (2, 1),
    (3, 1),
    (0, 2),
    (1, 2),
    (2, 2),
    (3, 2),
    (0, 3),
    (1, 3),
    (2, 3),
    (3, 3),
]

XY2 = [(0, 0), (1, 0), (0, 1), (1, 1)]
YX2 = [(0, 0), (0, 1), (1, 0), (1, 1)]

X4 = [(0, 0), (1, 0), (2, 0), (3, 0)]

Y4 = [(0, 0), (0, 1), (0, 2), (0, 3)]


def HBIN(stbl):
    btbl = {}
    for k, v in stbl.items():
        btbl[int("1" + k, 2)] = v
    return btbl


VAL_DC_YUV = HBIN(
    {"10": 0, "001": 1, "00001": 2, "0001": 3, "11": 4, "010": 5, "00000": 6, "011": 7}
)


NUM_CBPHP = [
    HBIN({"1": 0, "01": 1, "001": 2, "0000": 3, "0001": 4}),
    HBIN({"1": 0, "000": 1, "001": 2, "010": 3, "011": 4}),
]

NUM_BLKCBPHP1 = NUM_CBPHP

NUM_BLKCBPHP2 = [
    HBIN(
        {
            "010": 0,
            "00000": 1,
            "0010": 2,
            "00001": 3,
            "00010": 4,
            "1": 5,
            "011": 6,
            "00011": 7,
            "0011": 8,
        }
    ),
    HBIN(
        {
            "1": 0,
            "001": 1,
            "010": 2,
            "0001": 3,
            "000001": 4,
            "011": 5,
            "00001": 6,
            "0000000": 7,
            "0000001": 8,
        }
    ),
]

NumCBPHPDelta = [[0, -1, 0, 1, 1]]

FIRST_INDEX = [
    HBIN(
        {
            "00001": 0,
            "000001": 1,
            "0000000": 2,
            "0000001": 3,
            "00100": 4,
            "010": 5,
            "00101": 6,
            "1": 7,
            "00110": 8,
            "0001": 9,
            "00111": 10,
            "011": 11,
        }
    ),
    HBIN(
        {
            "0010": 0,
            "00010": 1,
            "000000": 2,
            "000001": 3,
            "0011": 4,
            "010": 5,
            "00011": 6,
            "11": 7,
            "011": 8,
            "100": 9,
            "00001": 10,
            "101": 11,
        }
    ),
    HBIN(
        {
            "11": 0,
            "001": 1,
            "0000000": 2,
            "0000001": 3,
            "00001": 4,
            "010": 5,
            "0000010": 6,
            "011": 7,
            "100": 8,
            "101": 9,
            "0000011": 10,
            "0001": 11,
        }
    ),
    HBIN(
        {
            "001": 0,
            "11": 1,
            "0000000": 2,
            "00001": 3,
            "00010": 4,
            "010": 5,
            "0000001": 6,
            "011": 7,
            "00011": 8,
            "100": 9,
            "000001": 10,
            "101": 11,
        }
    ),
    HBIN(
        {
            "010": 0,
            "1": 1,
            "0000001": 2,
            "0001": 3,
            "0000010": 4,
            "011": 5,
            "00000000": 6,
            "0010": 7,
            "0000011": 8,
            "0011": 9,
            "00000001": 10,
            "00001": 11,
        }
    ),
]

FirstIndexDelta = [
    [1, 1, 1, 1, 1, 0, 0, -1, 2, 1, 0, 0],
    [2, 2, -1, -1, -1, 0, -2, -1, 0, 0, -2, -1],
    [-1, 1, 0, 2, 0, 0, 0, 0, -2, 0, 1, 1],
    [0, 1, 0, 1, -2, 0, -1, -1, -2, -1, -2, -2],
]

Index1Delta = [[-1, 1, 1, 1, 0, 1], [-2, 0, 0, 2, 0, 0], [-1, -1, 0, 1, -2, 0]]

INDEX_A = [
    HBIN({"1": 0, "00000": 1, "001": 2, "00001": 3, "01": 4, "0001": 5}),
    HBIN({"01": 0, "0000": 1, "10": 2, "0001": 3, "11": 4, "001": 5}),
    HBIN({"0000": 0, "0001": 1, "01": 2, "10": 3, "11": 4, "001": 5}),
    HBIN({"00000": 0, "00001": 1, "01": 2, "1": 3, "0001": 4, "001": 5}),
]

INDEX_B = HBIN({"0": 0, "10": 2, "110": 1, "111": 3})

RUN_INDEX = HBIN({"1": 0, "01": 1, "001": 2, "0000": 3, "0001": 4})

RUN_VALUE = [
    None,
    None,
    HBIN({"1": 1, "0": 2}),
    HBIN({"1": 1, "01": 2, "00": 3}),
    HBIN({"1": 1, "01": 2, "001": 3, "000": 4}),
]

ABS_LEVEL_INDEX = [
    HBIN({"01": 0, "10": 1, "11": 2, "001": 3, "0001": 4, "00000": 5, "00001": 6}),
    HBIN({"1": 0, "01": 1, "001": 2, "0001": 3, "00001": 4, "000000": 5, "000001": 6}),
]

AbslevelIndexDelta = [[1, 0, -1, -1, -1, -1, -1]]

REF_CBPHP1 = HBIN({"00": 3, "01": 5, "100": 6, "101": 9, "110": 10, "111": 12})

NUM_CH_BLK = HBIN({"1": 0, "01": 1, "000": 2, "001": 3})

CHR_CBPHP = VAL_INC = CBPHP_CH_BLK = HBIN({"1": 0, "01": 1, "00": 2})

CBPLP_YUV1_444 = HBIN(
    {"0": 0, "100": 1, "1010": 2, "1011": 3, "1100": 4, "1101": 5, "1110": 6, "1111": 7}
)
CBPLP_YUV1_42x = HBIN({"0": 0, "10": 1, "110": 2, "111": 3})


class JXRImage(object):
    def __init__(self, data):
        self.data = data
        self.width = self.height = 0

    def decode(self):
        try:
            self.ds = Deserializer(self.data)

            self.coded_image()

            if len(self.ds):
                log.warning(
                    "%d of %d bytes remain after coded image"
                    % (len(self.ds), len(self.data))
                )

            for plane in self.planes:
                plane.SampleReconstruction()
                plane.OutputFormatting()

            im = self.construct_image()

        except Exception:
            if self.image_header_decoded and not DEBUG0:
                self.report_image_info()

            raise

        return im

    def coded_image(self):
        self.image_header_decoded = False
        self.planes = []

        self.image_header()
        self.image_header_decoded = True

        self.primary_plane = ImgPlane(self, False)
        self.planes.append(self.primary_plane)
        self.primary_plane.image_plane_header()
        self.NumBandsOfPrimary = self.primary_plane.NumBands

        if self.alpha_image_plane_flag:
            self.alpha_plane = ImgPlane(self, True)
            self.planes.append(self.alpha_plane)
            self.alpha_plane.image_plane_header()
        else:
            self.alpha_plane = None

        self.IndexOffsetTile = {}
        if self.index_table_present_flag:
            self.index_table_tiles()

        SubsequentBytes = self.vlw_esc("SubsequentBytes")
        if SubsequentBytes:
            iBytes = self.profile_level_info()
            if SubsequentBytes != iBytes:
                log.error(
                    "unexpected AdditionalBytes: SubsequentBytes(%d) != ProfileBytes(%d)"
                    % (SubsequentBytes, iBytes)
                )
                self.ds.extract(SubsequentBytes - iBytes)

        self.coded_tiles()

        for plane in self.planes:
            plane.Decode_cleanup()

        self.ds.discard_remainder_bits()

    def image_header(self):
        gdi_signature = self.ds.extract(8)
        if gdi_signature != b"WMPHOTO\x00":
            raise Exception(
                "GDI signature is incorrect: %s" % bytes_to_separated_hex(gdi_signature)
            )

        self.ds.check_bit_field(4, "codec_version", [1])
        self.hard_tiling_flag = self.ds.unpack_bits(1, "hard_tiling_flag")
        self.ds.check_bit_field(3, "codec_subversion", [1])

        self.tiling_flag = self.ds.unpack_bits(1, "tiling_flag")
        self.frequency_mode = self.ds.unpack_bits(1, "frequency_mode")
        self.spatial_xfrm_subordinate = self.ds.check_bit_field(
            3,
            "spatial_xfrm_subordinate (orientation)",
            XFRM_SUBORDINATE_NAME.keys(),
            XFRM_SUBORDINATE_NAME,
        )
        self.index_table_present_flag = self.ds.unpack_bits(
            1, "index_table_present_flag"
        )
        self.overlap_mode = self.ds.unpack_bits(2, "overlap_mode")

        self.short_header_flag = self.ds.unpack_bits(1, "short_header_flag")
        bh_fmt = "B" if self.short_header_flag else ">H"
        hl_fmt = ">H" if self.short_header_flag else ">L"

        self.long_word_flag = self.ds.unpack_bits(1, "long_word_flag")
        self.windowing_flag = self.ds.unpack_bits(1, "windowing_flag")
        self.trim_flexbits_flag = self.ds.unpack_bits(1, "trim_flexbits_flag")
        self.ds.check_bit_field(1, "reserved_d", [0])
        self.red_blue_not_swapped_flag = self.ds.unpack_bits(
            1, "red_blue_not_swapped_flag"
        )
        self.ds.check_bit_field(1, "premultiplied_alpha_flag", [0])
        self.alpha_image_plane_flag = self.ds.unpack_bits(1, "alpha_image_plane_flag")

        self.output_clr_fmt = self.ds.check_bit_field(
            4, "output_clr_fmt", OUTPUT_COLOR_NAME.keys(), OUTPUT_COLOR_NAME
        )
        self.output_bitdepth = self.ds.check_bit_field(
            4, "output_bitdepth", OUTPUT_BITDEPTH_NAME.keys(), OUTPUT_BITDEPTH_NAME
        )

        self.width = self.image_width = self.ds.unpack(hl_fmt, "image_width_minus1") + 1
        self.height = self.image_height = (
            self.ds.unpack(hl_fmt, "image_height_minus1") + 1
        )

        if self.tiling_flag:
            self.num_ver_tiles_minus1 = self.ds.unpack_bits(12, "num_ver_tiles_minus1")
            self.num_hor_tiles_minus1 = self.ds.unpack_bits(12, "num_hor_tiles_minus1")
        else:
            self.num_ver_tiles_minus1 = self.num_hor_tiles_minus1 = 0

        self.NumTileCols = self.num_ver_tiles_minus1 + 1
        self.NumTileRows = self.num_hor_tiles_minus1 + 1

        self.tile_width_in_mb = [
            self.ds.unpack(bh_fmt, "tile_width_in_mb")
            for i in range(self.num_ver_tiles_minus1)
        ]
        self.tile_height_in_mb = [
            self.ds.unpack(bh_fmt, "tile_height_in_mb")
            for i in range(self.num_hor_tiles_minus1)
        ]

        self.LeftMBIndexOfTile = [0]
        for mb in self.tile_width_in_mb:
            self.LeftMBIndexOfTile.append(self.LeftMBIndexOfTile[-1] + mb)

        self.TopMBIndexOfTile = [0]
        for mb in self.tile_height_in_mb:
            self.TopMBIndexOfTile.append(self.TopMBIndexOfTile[-1] + mb)

        if self.windowing_flag:
            self.ExtraPixelsTop = self.ds.unpack_bits(6, "ExtraPixelsTop")
            self.ExtraPixelsLeft = self.ds.unpack_bits(6, "ExtraPixelsLeft")
            self.ExtraPixelsBottom = self.ds.unpack_bits(6, "ExtraPixelsBottom")
            self.ExtraPixelsRight = self.ds.unpack_bits(6, "ExtraPixelsRight")
        else:
            self.ExtraPixelsTop = self.ExtraPixelsLeft = 0
            self.ExtraPixelsRight = 0x10 - (self.width & 0xF) if self.width & 0xF else 0
            self.ExtraPixelsBottom = (
                0x10 - (self.height & 0xF) if self.height & 0xF else 0
            )

        self.width += self.ExtraPixelsLeft + self.ExtraPixelsRight
        self.height += self.ExtraPixelsTop + self.ExtraPixelsBottom

        self.MBWidth = self.width // 16
        self.MBHeight = self.height // 16

        self.tile_width_in_mb.append(self.MBWidth - self.LeftMBIndexOfTile[-1])
        self.tile_height_in_mb.append(self.MBHeight - self.TopMBIndexOfTile[-1])

        self.LeftMBIndexOfTile.append(
            self.LeftMBIndexOfTile[-1] + self.tile_width_in_mb[-1]
        )
        self.TopMBIndexOfTile.append(
            self.TopMBIndexOfTile[-1] + self.tile_height_in_mb[-1]
        )

        if DEBUG0:
            self.report_image_info()

    def report_image_info(self):
        log.info(
            "ImageHeader: hard_tiling=%d tiling=%d frequency_mode=%d orient=%s index_table=%d overlap=%s short_hdr=%d long_word=%d"
            % (
                self.hard_tiling_flag,
                self.tiling_flag,
                self.frequency_mode,
                XFRM_SUBORDINATE_NAME[self.spatial_xfrm_subordinate],
                self.index_table_present_flag,
                OVERLAP_MODE_NAME[self.overlap_mode],
                self.short_header_flag,
                self.long_word_flag,
            )
        )
        log.info(
            "    windowing=%d trim_flexbits=%d alpha=%d output_color_fmt=%s output_bitdepth=%s size=%dx%d internal=%dx%d MB=%dx%d"
            % (
                self.windowing_flag,
                self.trim_flexbits_flag,
                self.alpha_image_plane_flag,
                OUTPUT_COLOR_NAME[self.output_clr_fmt],
                OUTPUT_BITDEPTH_NAME[self.output_bitdepth],
                self.image_width,
                self.image_height,
                self.width,
                self.height,
                self.MBWidth,
                self.MBHeight,
            )
        )
        log.info(
            "    tile_cols=%d tile_rows=%d margins_tlbr=%d %d %d %d"
            % (
                self.NumTileCols,
                self.NumTileRows,
                self.ExtraPixelsTop,
                self.ExtraPixelsLeft,
                self.ExtraPixelsBottom,
                self.ExtraPixelsRight,
            )
        )

        for plane in self.planes:
            plane.report_plane_info()

    def index_table_tiles(self):
        valueNumIndexTableEntries = self.NumTileRows * self.NumTileCols
        if self.frequency_mode:
            valueNumIndexTableEntries *= self.NumBandsOfPrimary

        self.ds.check_bit_field(16, "index_table_startcode", [1])

        for n in range(valueNumIndexTableEntries):
            self.IndexOffsetTile[n] = self.vlw_esc("IndexOffsetTile")

    def vlw_esc(self, name):
        first_byte = self.ds.unpack_bits(8, name + "-vlw_esc_first_byte")
        if first_byte < 0xFB:
            return (first_byte * 256) + self.ds.unpack_bits(8, "vlw_esc_16")
        elif first_byte == 0xFB:
            return self.ds.unpack_bits(32, "vlw_esc_32")
        elif first_byte == 0xFC:
            return self.ds.unpack_bits(64, "vlw_esc_64")
        else:
            return 0

    def profile_level_info(self):
        iBytes = 0
        while True:
            iBytes += 4
            self.ds.check_bit_field(8, "profile_idc", [44, 55, 66, 88, 111])
            self.ds.unpack_bits(8, "level_idc")
            self.ds.unpack_bits(15, "reserved_l")
            if self.ds.unpack_bits(1, "last_flag"):
                return iBytes

    def coded_tiles(self):
        first_tile_offset = self.ds.offset

        n = 0
        for Ty in range(self.NumTileRows):
            top_mb_index = self.TopMBIndexOfTile[Ty]
            height_mb = self.tile_height_in_mb[Ty]

            for Tx in range(self.NumTileCols):
                try:
                    left_mb_index = self.LeftMBIndexOfTile[Tx]
                    width_mb = self.tile_width_in_mb[Tx]

                    if DEBUG1:
                        log.info(
                            "processing tile %d: Tx=%d Ty=%d, MBx=%d-%d MBy=%d-%d"
                            % (
                                n,
                                Tx,
                                Ty,
                                left_mb_index,
                                left_mb_index + width_mb - 1,
                                top_mb_index,
                                top_mb_index + height_mb - 1,
                            )
                        )

                    for t, tile_type in enumerate(
                        [DCTile, LowpassTile, HighpassTile, FlexTile]
                        if self.frequency_mode
                        else [SpatialTile]
                    ):
                        if self.NumBandsOfPrimary > t:
                            if self.index_table_present_flag:
                                current_tile_offset = self.ds.offset - first_tile_offset
                                if self.IndexOffsetTile[n] != current_tile_offset:
                                    log.warning(
                                        "Tile %d index table offset (%d) != current offset (%d)"
                                        % (
                                            n,
                                            self.IndexOffsetTile[n],
                                            current_tile_offset,
                                        )
                                    )

                                    self.ds.offset = (
                                        first_tile_offset + self.IndexOffsetTile[n]
                                    )

                            tile = tile_type(self.ds)
                            tile.common_tile_header()

                            for plane in self.planes:
                                tile.tile_plane_header(plane)

                            for MBy in range(top_mb_index, top_mb_index + height_mb):
                                for MBx in range(
                                    left_mb_index, left_mb_index + width_mb
                                ):
                                    for plane in self.planes:
                                        if DEBUG1:
                                            log.info(
                                                "****************************\nprocessing %s tile MBx=%d MBy=%d"
                                                % (tile.tile_type, MBx, MBy)
                                            )

                                        try:
                                            tile.tile_MB(plane, plane.Mb[MBx][MBy])
                                        except Exception:
                                            log.info(
                                                "Error processing %s tile MBx=%d MBy=%d"
                                                % (tile.tile_type, MBx, MBy)
                                            )
                                            raise

                            tile.common_tile_finish()
                            n += 1
                except Exception:
                    log.info("Error processing tile %d Tx=%d Ty=%d" % (n, Tx, Ty))
                    raise

    def construct_image(self):
        if (self.output_clr_fmt == RGB and self.alpha_plane is not None) or (
            self.output_clr_fmt == NCOMPONENT and self.primary_plane.NumComponents == 4
        ):
            if self.output_bitdepth not in [BD8, BD16]:
                raise Exception(
                    "Bit depth %s is not supported for RGBA"
                    % (OUTPUT_BITDEPTH_NAME[self.output_bitdepth])
                )

            mode = "RGBA"

        elif self.output_clr_fmt == RGB or (
            self.output_clr_fmt == NCOMPONENT and self.primary_plane.NumComponents == 3
        ):
            if self.output_bitdepth not in [BD8, BD16]:
                raise Exception(
                    "Bit depth %s is not supported for RGB"
                    % (OUTPUT_BITDEPTH_NAME[self.output_bitdepth])
                )

            mode = "RGB"

        elif self.output_clr_fmt == YONLY or (
            self.output_clr_fmt == NCOMPONENT and self.primary_plane.NumComponents == 1
        ):
            if self.output_bitdepth not in [BD1BLACK1, BD1WHITE1, BD8, BD16]:
                raise Exception(
                    "Bit depth %s is not supported"
                    % (OUTPUT_BITDEPTH_NAME[self.output_bitdepth])
                )

            BITDEPTH_MODE = {BD8: "L", BD16: "I;16", BD1BLACK1: "1", BD1WHITE1: "1"}
            mode = BITDEPTH_MODE[self.output_bitdepth]

        else:
            raise Exception(
                "Color format %s with %d components is not supported"
                % (
                    OUTPUT_COLOR_NAME[self.output_clr_fmt],
                    self.primary_plane.NumComponents,
                )
            )

        im = Image.new(mode, (self.image_width, self.image_height))
        pixels = im.load()

        if mode == "RGBA":
            r_data = self.primary_plane.ImagePlane[0]
            g_data = self.primary_plane.ImagePlane[1]
            b_data = self.primary_plane.ImagePlane[2]
            a_data = (
                self.primary_plane.ImagePlane[3]
                if self.output_clr_fmt == NCOMPONENT
                else self.alpha_plane.ImagePlane[0]
            )

            for y in range(self.image_height):
                for x in range(self.image_width):
                    pixels[x, y] = (
                        (r_data[x][y], g_data[x][y], b_data[x][y], a_data[x][y])
                        if self.output_bitdepth == BD8
                        else (
                            r_data[x][y] >> 8,
                            g_data[x][y] >> 8,
                            b_data[x][y] >> 8,
                            a_data[x][y] >> 8,
                        )
                    )

        elif mode == "RGB":
            r_data = self.primary_plane.ImagePlane[0]
            g_data = self.primary_plane.ImagePlane[1]
            b_data = self.primary_plane.ImagePlane[2]

            for y in range(self.image_height):
                for x in range(self.image_width):
                    pixels[x, y] = (
                        (r_data[x][y], g_data[x][y], b_data[x][y])
                        if self.output_bitdepth == BD8
                        else (r_data[x][y] >> 8, g_data[x][y] >> 8, b_data[x][y] >> 8)
                    )

        elif mode == "1":
            y_data = self.primary_plane.ImagePlane[0]

            for y in range(self.image_height):
                for x in range(self.image_width):
                    pixels[x, y] = y_data[x][y] * 255

        else:
            y_data = self.primary_plane.ImagePlane[0]

            for y in range(self.image_height):
                for x in range(self.image_width):
                    pixels[x, y] = y_data[x][y]

        return im


class ImgPlane(object):
    def __init__(self, image, IsCurrPlaneAlphaFlag):
        self.image = image
        self.ds = image.ds
        self.IsCurrPlaneAlphaFlag = IsCurrPlaneAlphaFlag

    def image_plane_header(self):
        self.internal_clr_fmt = self.ds.check_bit_field(
            3, "internal_clr_fmt", INTERNAL_COLOR_NAME.keys(), INTERNAL_COLOR_NAME
        )
        self.scaled_flag = self.ds.unpack_bits(1, "scaled_flag")

        self.bands_present = self.ds.check_bit_field(
            4, "bands_present", PRESENT_BAND_NAMES.keys(), PRESENT_BAND_NAMES
        )

        self.lp_present = self.hp_present = self.flexbits_present = False

        self.dc = DCBand(self)
        self.NumBands = 1
        if self.bands_present != DCONLY:
            self.lp = LPBand(self)
            self.lp_present = True
            self.NumBands += 1
            if self.bands_present != NOHIGHPASS:
                self.hp = HPBand(self)
                self.hp_present = True
                self.NumBands += 1
                if self.bands_present != NOFLEXBITS:
                    self.flexbits_present = True
                    self.NumBands += 1

        if self.internal_clr_fmt == YONLY:
            self.NumComponents = 1
        elif self.internal_clr_fmt == YUVK:
            self.NumComponents = 4
        elif self.internal_clr_fmt in [YUV444, YUV420, YUV422]:
            self.NumComponents = 3
            if self.internal_clr_fmt in [YUV420, YUV422]:
                self.ds.unpack_bits(1, "reserved_e")
                self.chroma_centering_x = self.ds.unpack_bits(3, "chroma_centering_x")
            else:
                self.ds.unpack_bits(4, "reserved_f")

            if self.internal_clr_fmt == YUV420:
                self.ds.unpack_bits(1, "reserved_g_bit")
                self.chroma_centering_y = self.ds.unpack_bits(3, "chroma_centering_y")
            else:
                self.ds.unpack_bits(4, "reserved_h")
        elif self.internal_clr_fmt == NCOMPONENT:
            self.NumComponents = self.ds.unpack_bits(4, "NumComponents_minus1") + 1
            if self.NumComponents == 16:
                self.NumComponents = (
                    self.ds.unpack_bits(12, "NumComponents_extended_minus16") + 16
                )
            else:
                self.ds.unpack_bits(4, "reserved_h")

        self.ChromaPerBlk = (
            1
            if self.internal_clr_fmt == YUV420
            else (2 if self.internal_clr_fmt == YUV422 else 4)
        )
        self.NumLPCoeff = self.ChromaPerBlk * 4

        if self.image.output_bitdepth in [BD16, BD16S, BD32S]:
            self.shift_bits = self.ds.unpack_bits(8, "shift_bits")
        elif self.image.output_bitdepth == BD32F:
            self.len_mantissa = self.ds.unpack_bits(8, "len_mantissa")
            self.exp_bias = twos_complement_byte(self.ds.unpack_bits(8, "exp_bias"))

        self.dc_image_plane_uniform_flag = self.ds.unpack_bits(
            1, "dc_image_plane_uniform_flag"
        )
        if self.dc_image_plane_uniform_flag:
            self.dc.qp = QP(self.ds, self.NumComponents, 1, self.scaled_flag, DC)

        self.lp_image_plane_uniform_flag = self.hp_image_plane_uniform_flag = None

        if self.bands_present != DCONLY:
            self.ds.check_bit_field(1, "reserved_i_bit", [0])
            self.lp_image_plane_uniform_flag = self.ds.unpack_bits(
                1, "lp_image_plane_uniform_flag"
            )
            if self.lp_image_plane_uniform_flag:
                self.lp.qp = QP(self.ds, self.NumComponents, 1, self.scaled_flag, LP)

            if self.bands_present != NOHIGHPASS:
                self.ds.check_bit_field(1, "reserved_j_bit", [0])
                self.hp_image_plane_uniform_flag = self.ds.unpack_bits(
                    1, "hp_image_plane_uniform_flag"
                )
                if self.hp_image_plane_uniform_flag:
                    self.hp.qp = QP(
                        self.ds, self.NumComponents, 1, self.scaled_flag, HP
                    )

        image = self.image
        self.Mb = Array(image.MBWidth, image.MBHeight, None)

        for Tx in range(image.NumTileCols):
            first_MBx = image.LeftMBIndexOfTile[Tx]
            tile_mb_width = image.tile_width_in_mb[Tx]
            for Ty in range(image.NumTileRows):
                first_MBy = image.TopMBIndexOfTile[Ty]
                tile_mb_hight = image.tile_height_in_mb[Ty]

                for MBxt in range(tile_mb_width):
                    MBx = MBxt + first_MBx
                    for MByt in range(tile_mb_hight):
                        MBy = MByt + first_MBy
                        self.Mb[MBx][MBy] = MB(
                            MBx,
                            MBy,
                            MBxt,
                            MByt,
                            tile_mb_width,
                            self.NumComponents,
                            self.Mb[MBx - 1][MBy] if MBx > 0 else None,
                            self.Mb[MBx][MBy - 1] if MBy > 0 else None,
                        )

        self.image_data = Array(self.NumComponents, self.image.width, self.image.height)

        self.ds.discard_remainder_bits()

        if DEBUG0:
            self.report_plane_info()

        if self.internal_clr_fmt in [YUV420, YUV422]:
            raise Exception(
                "Color format %s is not supported"
                % (INTERNAL_COLOR_NAME[self.internal_clr_fmt])
            )

    def report_plane_info(self):
        log.info(
            "ImagePlane: internal_color_fmt=%s scaled_flag=%d bands_present=%s components=%d dc_uniform=%d lp_uniform=%s hp_uniform=%s"
            % (
                INTERNAL_COLOR_NAME[self.internal_clr_fmt],
                self.scaled_flag,
                PRESENT_BAND_NAMES[self.bands_present],
                self.NumComponents,
                self.dc_image_plane_uniform_flag,
                self.lp_image_plane_uniform_flag,
                self.hp_image_plane_uniform_flag,
            )
        )

    def decode_qp_index(self, iNumQP):
        BitsQPIndex = [0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4]
        return (
            self.ds.unpack_bits(BitsQPIndex[iNumQP], "QPIndex") + 1
            if self.ds.unpack_bits(1, "qpindex_nonzero_flag")
            else 0
        )

    def Decode_cleanup(self):
        for MBy in range(self.image.MBHeight):
            for MBx in range(self.image.MBWidth):
                self.Mb[MBx][MBy].cleanup()

    def SampleReconstruction(self):
        self.FirstLevelInverseTransform()

        if self.image.overlap_mode == FIRST_AND_SECOND_LEVEL_OVERLAP_FILTERING:
            self.FirstLevelOverlapFiltering()

        self.SecondLevelInverseTransform()
        self.SecondLevelCoefficientCombination()

        if self.image.overlap_mode in [
            FIRST_AND_SECOND_LEVEL_OVERLAP_FILTERING,
            SECOND_LEVEL_OVERLAP_FILTERING,
        ]:
            self.second_level_overlap_filtering()

    def FirstLevelInverseTransform(self):
        for i in range(self.NumComponents):
            for MBy in range(self.image.MBHeight):
                for MBx in range(self.image.MBWidth):
                    mbp = self.Mb[MBx][MBy].MBBuffer[i]

                    if DEBUG1:
                        log.info("MBBuffer2=")
                        for iy in range(16):
                            log.info(
                                ", ".join(
                                    ["%d" % mbp[iy * 16 + ix] for ix in range(16)]
                                )
                            )

                    DCLP0 = [mbp[j * 16] for j in range(16)]
                    if DEBUG1:
                        log.info(
                            "MB[%d,%d] DCLP0=%s"
                            % (MBx, MBy, ", ".join(["%d" % z for z in DCLP0]))
                        )

                    DCLP1 = strIDCT4x4Stage2(DCLP0)
                    if DEBUG1:
                        log.info(
                            "MB[%d,%d] DCLP1=%s"
                            % (MBx, MBy, ", ".join(["%d" % z for z in DCLP1]))
                        )

                    if i > 0 and self.scaled_flag:
                        DCLP1 = [v * 2 for v in DCLP1]

                    for j in range(16):
                        mbp[j * 16] = DCLP1[j]

    def FirstLevelOverlapFiltering(self):
        image = self.image

        LE1 = [(0, 0, 8), (0, 0, 12), (0, 1, 0), (0, 1, 4)]
        LE2 = [(0, 0, 9), (0, 0, 13), (0, 1, 1), (0, 1, 5)]

        TE1 = [(0, 0, 2), (0, 0, 3), (1, 0, 0), (1, 0, 1)]
        TE2 = [(0, 0, 6), (0, 0, 7), (1, 0, 4), (1, 0, 5)]

        RE1 = [(0, 0, 10), (0, 0, 14), (0, 1, 2), (0, 1, 6)]
        RE2 = [(0, 0, 11), (0, 0, 15), (0, 1, 3), (0, 1, 7)]

        BE1 = [(0, 0, 10), (0, 0, 11), (1, 0, 8), (1, 0, 9)]
        BE2 = [(0, 0, 14), (0, 0, 15), (1, 0, 12), (1, 0, 13)]

        TLC = [(0, 0, 0), (0, 0, 1), (0, 0, 4), (0, 0, 5)]
        TRC = [(0, 0, 2), (0, 0, 3), (0, 0, 6), (0, 0, 7)]
        BLC = [(0, 0, 8), (0, 0, 9), (0, 0, 12), (0, 0, 13)]
        BRC = [(0, 0, 10), (0, 0, 11), (0, 0, 14), (0, 0, 15)]

        FLC = [
            (0, 0, 10),
            (0, 0, 11),
            (1, 0, 8),
            (1, 0, 9),
            (0, 0, 14),
            (0, 0, 15),
            (1, 0, 12),
            (1, 0, 13),
            (0, 1, 2),
            (0, 1, 3),
            (1, 1, 0),
            (1, 1, 1),
            (0, 1, 6),
            (0, 1, 7),
            (1, 1, 4),
            (1, 1, 5),
        ]

        XYTRANSPOSE = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]

        def zzz(z):
            return XYTRANSPOSE[z] * 16

        def FirstLevelCallOverlapPostFilter4x4(x, y):
            if DEBUG1:
                log.info("FirstLevelCallOverlapPostFilter4x4 x=%d y=%d" % (x, y))
            arrayLocal = strPost4x4Stage2Split_alternate(
                [self.Mb[x + xx][y + yy].MBBuffer[i][zzz(zz)] for xx, yy, zz in FLC]
            )
            for xx, yy, zz in FLC:
                self.Mb[x + xx][y + yy].MBBuffer[i][zzz(zz)] = arrayLocal.pop(0)

        def OverlapPostFilter4_(x, y, xyz_list):
            if DEBUG1:
                log.info(
                    "OverlapPostFilter4_ x=%d y=%d xyz=%s" % (x, y, repr(xyz_list))
                )
            arrayLocal = OverlapPostFilter4(
                [
                    self.Mb[x + xx][y + yy].MBBuffer[i][zzz(zz)]
                    for xx, yy, zz in xyz_list
                ]
            )
            for xx, yy, zz in xyz_list:
                self.Mb[x + xx][y + yy].MBBuffer[i][zzz(zz)] = arrayLocal.pop(0)

        for i in range(self.NumComponents):
            for Tx in range(image.NumTileCols):
                for Ty in range(image.NumTileRows):
                    first_MBx = image.LeftMBIndexOfTile[Tx]
                    last_MBx = image.LeftMBIndexOfTile[Tx + 1] - 1
                    first_MBy = image.TopMBIndexOfTile[Ty]
                    last_MBy = image.TopMBIndexOfTile[Ty + 1] - 1
                    if DEBUG1:
                        log.info(
                            "tile i=%d x=%d y=%d MBx=%d-%d MBy=%d-%d"
                            % (i, Tx, Ty, first_MBx, last_MBx, first_MBy, last_MBy)
                        )

                    for y in range(first_MBy, last_MBy):
                        for x in range(first_MBx, last_MBx):
                            FirstLevelCallOverlapPostFilter4x4(x, y)

                    if Tx == 0 or image.hard_tiling_flag:
                        for y in range(first_MBy, last_MBy):
                            OverlapPostFilter4_(first_MBx, y, LE1)
                            OverlapPostFilter4_(first_MBx, y, LE2)

                    if Ty == 0 or image.hard_tiling_flag:
                        for x in range(first_MBx, last_MBx):
                            OverlapPostFilter4_(x, first_MBy, TE1)
                            OverlapPostFilter4_(x, first_MBy, TE2)

                    if Tx == image.NumTileCols - 1 or image.hard_tiling_flag:
                        for y in range(first_MBy, last_MBy):
                            OverlapPostFilter4_(last_MBx, y, RE1)
                            OverlapPostFilter4_(last_MBx, y, RE2)

                    if Ty == image.NumTileRows - 1 or image.hard_tiling_flag:
                        for x in range(first_MBx, last_MBx):
                            OverlapPostFilter4_(x, last_MBy, BE1)
                            OverlapPostFilter4_(x, last_MBy, BE2)

                    if (Tx == 0 and Ty == 0) or image.hard_tiling_flag:
                        OverlapPostFilter4_(first_MBx, first_MBy, TLC)

                    if (
                        Tx == image.NumTileCols - 1 and Ty == 0
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(last_MBx, first_MBy, TRC)

                    if (
                        Tx == 0 and Ty == image.NumTileRows - 1
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(first_MBx, last_MBy, BLC)

                    if (
                        Tx == image.NumTileCols - 1 and Ty == image.NumTileRows - 1
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(last_MBx, last_MBy, BRC)

                    if not image.hard_tiling_flag:
                        if Tx != image.NumTileCols - 1:
                            for y in range(first_MBy, last_MBy):
                                FirstLevelCallOverlapPostFilter4x4(last_MBx, y)

                        if Ty != image.NumTileRows - 1:
                            for x in range(first_MBx, last_MBx):
                                FirstLevelCallOverlapPostFilter4x4(x, last_MBy)

                        if Tx != image.NumTileCols - 1 and Ty != image.NumTileRows - 1:
                            FirstLevelCallOverlapPostFilter4x4(last_MBx, last_MBy)

                        if Tx == 0 and Ty != image.NumTileRows - 1:
                            OverlapPostFilter4_(first_MBx, last_MBy, LE1)
                            OverlapPostFilter4_(first_MBx, last_MBy, LE2)

                        if Tx != image.NumTileCols - 1 and Ty == 0:
                            OverlapPostFilter4_(last_MBx, first_MBy, TE1)
                            OverlapPostFilter4_(last_MBx, first_MBy, TE2)

                        if Tx == image.NumTileCols - 1 and Ty != image.NumTileRows - 1:
                            OverlapPostFilter4_(last_MBx, last_MBy, RE1)
                            OverlapPostFilter4_(last_MBx, last_MBy, RE2)

                        if Tx != image.NumTileCols - 1 and Ty == image.NumTileRows - 1:
                            OverlapPostFilter4_(last_MBx, last_MBy, BE1)
                            OverlapPostFilter4_(last_MBx, last_MBy, BE2)

    def SecondLevelInverseTransform(self):
        for i in range(self.NumComponents):
            for MBy in range(self.image.MBHeight):
                for MBx in range(self.image.MBWidth):
                    mbp = self.Mb[MBx][MBy].MBBuffer[i]

                    for j in range(0, 16):
                        coeff0 = [mbp[j * 16 + k] for k in range(16)]
                        if DEBUG1:
                            log.info(
                                "MB[%d,%d] COEF[%d]0=%s"
                                % (MBx, MBy, j, ", ".join(["%d" % z for z in coeff0]))
                            )

                        coeff1 = strIDCT4x4Stage1(coeff0)
                        if DEBUG1:
                            log.info(
                                "MB[%d,%d] COEF[%d]1=%s"
                                % (MBx, MBy, j, ", ".join(["%d" % z for z in coeff1]))
                            )

                        for k in range(16):
                            mbp[j * 16 + k] = coeff1[k]

    def SecondLevelCoefficientCombination(self):
        self.ImagePlane = Array(
            self.NumComponents, self.image.width, self.image.height, None
        )

        for i in range(self.NumComponents):
            ip = self.ImagePlane[i]
            for MBy in range(self.image.MBHeight):
                MByy = MBy << 4
                for MBx in range(self.image.MBWidth):
                    MBxx = MBx << 4
                    mbp = self.Mb[MBx][MBy].MBBuffer[i]

                    for by in range(4):
                        by_x4 = MByy + (by << 2)
                        by_x16 = by << 4
                        for bx in range(4):
                            bx_x4 = MBxx + (bx << 2)
                            bx_x64 = bx << 6

                            for py in range(4):
                                py_x4 = py << 2
                                for px in range(4):
                                    ip[bx_x4 + px][by_x4 + py] = mbp[
                                        by_x16 + bx_x64 + mb_pixel_map[px + py_x4]
                                    ]

        del self.Mb

    def second_level_overlap_filtering(self):
        def OverlapPostFilter4x4_(x, y, xy_list):
            arrayLocal = OverlapPostFilter4x4(
                [ip[x + xx][y + yy] for xx, yy in xy_list]
            )
            for xx, yy in xy_list:
                ip[x + xx][y + yy] = arrayLocal.pop(0)

        def OverlapPostFilter4_(x, y, xy_list):
            arrayLocal = OverlapPostFilter4([ip[x + xx][y + yy] for xx, yy in xy_list])
            for xx, yy in xy_list:
                ip[x + xx][y + yy] = arrayLocal.pop(0)

        image = self.image
        for i in range(self.NumComponents):
            ip = self.ImagePlane[i]

            for Tx in range(image.NumTileCols):
                for Ty in range(image.NumTileRows):
                    first_MBx = image.LeftMBIndexOfTile[Tx] * 16
                    next_MBx = image.LeftMBIndexOfTile[Tx + 1] * 16
                    first_MBy = image.TopMBIndexOfTile[Ty] * 16
                    next_MBy = image.TopMBIndexOfTile[Ty + 1] * 16

                    for x in range(first_MBx + 2, next_MBx - 2, 4):
                        for y in range(first_MBy + 2, next_MBy - 2, 4):
                            OverlapPostFilter4x4_(x, y, XY4)

                    if Tx == 0 or image.hard_tiling_flag:
                        for y in range(first_MBy + 2, next_MBy - 2, 4):
                            for xx in [0, 1]:
                                OverlapPostFilter4_(first_MBx + xx, y, Y4)

                    if Ty == 0 or image.hard_tiling_flag:
                        for x in range(first_MBx + 2, next_MBx - 2, 4):
                            for yy in [0, 1]:
                                OverlapPostFilter4_(x, first_MBy + yy, X4)

                    if Tx == image.NumTileCols - 1 or image.hard_tiling_flag:
                        for y in range(first_MBy + 2, next_MBy - 2, 4):
                            for xx in [-2, -1]:
                                OverlapPostFilter4_(next_MBx + xx, y, Y4)

                    if Ty == image.NumTileRows - 1 or image.hard_tiling_flag:
                        for x in range(first_MBx + 2, next_MBx - 2, 4):
                            for yy in [-2, -1]:
                                OverlapPostFilter4_(x, next_MBy + yy, X4)

                    if (Tx == 0 and Ty == 0) or image.hard_tiling_flag:
                        OverlapPostFilter4_(first_MBx, first_MBy, XY2)

                    if (
                        Tx == image.NumTileCols - 1 and Ty == 0
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(next_MBx - 2, first_MBy, XY2)

                    if (
                        Tx == 0 and Ty == image.NumTileRows - 1
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(first_MBx, next_MBy - 2, XY2)

                    if (
                        Tx == image.NumTileCols - 1 and Ty == image.NumTileRows - 1
                    ) or image.hard_tiling_flag:
                        OverlapPostFilter4_(next_MBx - 2, next_MBy - 2, XY2)

                    if not image.hard_tiling_flag:
                        if Tx != image.NumTileCols - 1:
                            for y in range(first_MBy + 2, next_MBy - 2, 4):
                                OverlapPostFilter4x4_(next_MBx - 2, y, XY4)

                        if Ty != image.NumTileRows - 1:
                            for x in range(first_MBx + 2, next_MBx - 2, 4):
                                OverlapPostFilter4x4_(x, next_MBy - 2, XY4)

                        if Tx != image.NumTileCols - 1 and Ty != image.NumTileRows - 1:
                            OverlapPostFilter4x4_(next_MBx - 2, next_MBy - 2, XY4)

                        if Tx == 0 and Ty != image.NumTileRows - 1:
                            for xx in range(2):
                                OverlapPostFilter4_(first_MBx + xx, next_MBy - 2, Y4)

                        if Tx != image.NumTileCols - 1 and Ty == 0:
                            for yy in range(2):
                                OverlapPostFilter4_(next_MBx - 2, first_MBy + yy, X4)

                        if Tx == image.NumTileCols - 1 and Ty != image.NumTileRows - 1:
                            for xx in [-2, -1]:
                                OverlapPostFilter4_(next_MBx + xx, next_MBy - 2, Y4)

                        if Tx != image.NumTileCols - 1 and Ty == image.NumTileRows - 1:
                            for yy in [-2, -1]:
                                OverlapPostFilter4_(next_MBx - 2, next_MBy + yy, X4)

    def OutputFormatting(self):
        self.ConvertInternalToOutputClrFmt()
        self.AddBias()
        self.ComputeScaling()
        self.PostscalingProcess()
        self.ClippingAndPackingStage()

    def ConvertInternalToOutputClrFmt(self):
        if self.IsCurrPlaneAlphaFlag:
            if self.internal_clr_fmt != YONLY:
                raise Exception("Color format of alpha plane must by YONLY")

        elif self.internal_clr_fmt == YONLY and self.image.output_clr_fmt == RGB:
            self.ImagePlane.append(Array(self.image.width, self.image.height, None))
            self.ImagePlane.append(Array(self.image.width, self.image.height, None))

            for y in range(self.image.height):
                for x in range(self.image.width):
                    self.ImagePlane[1][x][y] = self.ImagePlane[2][x][y] = (
                        self.ImagePlane[0][x][y]
                    )

            self.internal_clr_fmt == RGB
            self.NumComponents = 3

        elif self.internal_clr_fmt == YUV444 and self.image.output_clr_fmt == RGB:
            do_swap = (
                self.image.output_bitdepth in [BD5, BD565, BD10]
                and not self.image.red_blue_not_swapped_flag
            )
            for y in range(self.image.height):
                for x in range(self.image.width):
                    tempT = -self.ImagePlane[1][x][y]
                    Out1 = self.ImagePlane[0][x][y] - int(math.floor(tempT / 2))
                    Out0 = tempT + Out1 - int(math.ceil(self.ImagePlane[2][x][y] / 2))
                    Out2 = self.ImagePlane[2][x][y] + Out0

                    if do_swap:
                        Out0, Out2 = (Out2, Out0)

                    (
                        self.ImagePlane[0][x][y],
                        self.ImagePlane[1][x][y],
                        self.ImagePlane[2][x][y],
                    ) = (Out0, Out1, Out2)

            self.internal_clr_fmt == RGB

        elif (
            INTERNAL_COLOR_NAME[self.internal_clr_fmt]
            != OUTPUT_COLOR_NAME[self.image.output_clr_fmt]
        ):
            raise Exception(
                "Color format conversion from %s to %s is not supported"
                % (
                    INTERNAL_COLOR_NAME[self.internal_clr_fmt],
                    OUTPUT_COLOR_NAME[self.image.output_clr_fmt],
                )
            )

    def AddBias(self):
        if self.image.output_clr_fmt in [YUV422, YUV420, CMYK]:
            raise Exception(
                "AddBias not implemented for %s"
                % OUTPUT_COLOR_NAME[self.image.output_clr_fmt]
            )

        BITDEPTH_BIAS = {
            BD5: 1 << 4,
            BD565: 1 << 5,
            BD8: 1 << 7,
            BD10: 1 << 9,
            BD16: 1 << 15,
        }
        iBias = BITDEPTH_BIAS.get(self.image.output_bitdepth, 0) << (
            3 if self.scaled_flag else 0
        )

        if iBias:
            for i in range(self.NumComponents):
                ip = self.ImagePlane[i]
                for x in range(0, self.image.width):
                    ipx = ip[x]
                    for y in range(0, self.image.height):
                        ipx[y] += iBias

    def ComputeScaling(self):
        iScale = 0
        iRoundingFactor = 0
        if self.scaled_flag:
            iScale = 3
            if self.image.output_bitdepth in [
                BD5,
                BD565,
                BD8,
                BD10,
                BD16S,
                BD16F,
                BD32S,
                BD32F,
            ]:
                iRoundingFactor = 3
            elif self.image.output_bitdepth in [BD1WHITE1, BD1BLACK1, BD16]:
                iRoundingFactor = 4

        outputComponents = (
            3 if self.internal_clr_fmt in [RGB, RGBE, YUV444] else self.NumComponents
        )
        for i in range(outputComponents):
            jScale = (
                iScale + 1 if self.image.output_bitdepth == BD565 and i != 1 else iScale
            )
            ip = self.ImagePlane[i]

            if iRoundingFactor or jScale:
                if DEBUG1:
                    log.info(
                        "rounding factor = %d, scale = %d" % (iRoundingFactor, jScale)
                    )

                for y in range(self.image.height):
                    for x in range(self.image.width):
                        ip[x][y] = (ip[x][y] + iRoundingFactor) >> jScale

    def PostscalingProcess(self):
        if self.image.output_clr_fmt == RGBE:
            raise Exception("PostscalingProcess not implemented for RGBE")

        if self.image.output_clr_fmt in [RGB, YUV444]:
            if self.image.output_bitdepth in [BD32F, BD16F]:
                raise Exception(
                    "PostscalingProcess not implemented for %s with %s"
                    % (
                        OUTPUT_COLOR_NAME[self.image.output_clr_fmt],
                        OUTPUT_BITDEPTH_NAME[self.image.output_bitdepth],
                    )
                )

            if (
                self.image.output_bitdepth in [BD16, BD16S, BD32S]
                and self.shift_bits != 0
            ):
                for i in range(self.NumComponents):
                    for y in range(self.image.height):
                        for x in range(self.image.width):
                            self.ImagePlane[i][x][y] = (
                                self.ImagePlane[i][x][y] << self.shift_bits
                            )

    def ClippingAndPackingStage(self):
        CLIP_RANGE = {
            BD1BLACK1: (0, 1),
            BD1WHITE1: (0, 1),
            BD8: (0, 255),
            BD16: {0, 65535},
            BD16S: (-32768, 32767),
        }

        if self.image.output_bitdepth in CLIP_RANGE.keys():
            clip_low, clip_high = CLIP_RANGE[self.image.output_bitdepth]

            outputHeight = self.image.image_height
            outputWidth = self.image.image_width
            n = self.image.ExtraPixelsTop
            m = self.image.ExtraPixelsLeft

            for i in range(self.NumComponents):
                ip = self.ImagePlane[i]

                if m == 0 and n == 0:
                    for y in range(outputHeight):
                        for x in range(outputWidth):
                            v = ip[x][y]
                            if v < clip_low:
                                ip[x][y] = clip_low
                            if v > clip_high:
                                ip[x][y] = clip_high
                else:
                    for y in range(outputHeight):
                        for x in range(outputWidth):
                            ip[x][y] = Clip(ip[x + m][y + n], clip_low, clip_high)
        else:
            raise Exception(
                "Output bit depth %s is not supported"
                % (OUTPUT_BITDEPTH_NAME[self.image.output_bitdepth])
            )


class Tile(object):
    def __init__(self, ds):
        self.ds = ds

    def common_tile_header(self):
        self.ds.check_bit_field(24, "tile_startcode", [1])

        self.ds.unpack_bits(8, "arbitrary_byte")

    def common_tile_finish(self):
        self.ds.discard_remainder_bits()


class DCTile(Tile):
    tile_type = "DC"

    def tile_plane_header(self, plane):
        if not plane.dc_image_plane_uniform_flag:
            plane.dc.qp = QP(self.ds, plane.NumComponents, 1, plane.scaled_flag, DC)

    def tile_MB(self, plane, mb):
        plane.dc.MB_DC(mb)


class LowpassTile(Tile):
    tile_type = "lowpass"

    def tile_plane_header(self, plane):
        if plane.lp_present and not plane.lp_image_plane_uniform_flag:
            if self.ds.unpack_bits(1, "use_dc_qp_flag"):
                plane.lp.qp = plane.dc.qp
            else:
                plane.lp.qp = QP(
                    self.ds,
                    plane.NumComponents,
                    self.ds.unpack_bits(4, "lp.NumQPs_minus1") + 1,
                    plane.scaled_flag,
                    LP,
                )

    def tile_MB(self, plane, mb):
        self.tile_MB_QP(plane, mb)
        self.tile_MB_2(plane, mb)

    def tile_MB_QP(self, plane, mb):
        if plane.lp_present:
            if plane.lp.qp.NumQPs > 1 and plane.lp.qp is not plane.dc.qp:
                mb.MBQPIndexLP = plane.lp.qp.IndexQPs = plane.decode_qp_index(
                    plane.lp.qp.NumQPs
                )

    def tile_MB_2(self, plane, mb):
        if plane.lp_present:
            plane.lp.MB_LP(mb)


class HighpassTile(Tile):
    tile_type = "highpass"

    def tile_plane_header(self, plane):
        if plane.hp_present and not plane.hp_image_plane_uniform_flag:
            if self.ds.unpack_bits(1, "use_lp_qp_flag"):
                plane.hp.qp = plane.lp.qp
            else:
                plane.hp.qp = QP(
                    self.ds,
                    plane.NumComponents,
                    self.ds.unpack_bits(4, "hp.NumQPs_minus1") + 1,
                    plane.scaled_flag,
                    HP,
                )

    def tile_MB(self, plane, mb):
        self.tile_MB_QP(plane, mb)
        self.tile_MB_2(plane, mb)

    def tile_MB_QP(self, plane, mb):
        if plane.hp_present:
            if plane.hp.qp.NumQPs > 1 and plane.hp.qp is not plane.lp.qp:
                plane.hp.qp.IndexQPs = plane.decode_qp_index(plane.hp.qp.NumQPs)

    def tile_MB_2(self, plane, mb):
        if plane.hp_present:
            plane.hp.MB_CBPHP(mb)
            plane.hp.MB_HP_FLEX(mb, do_hp=True)


class FlexTile(Tile):
    tile_type = "flexbits"

    def tile_plane_header(self, plane):
        if plane.flexbits_present and not plane.IsCurrPlaneAlphaFlag:
            self.trim_flexbits = (
                self.ds.unpack_bits(4, "trim_flexbits")
                if plane.image.trim_flexbits_flag
                else 0
            )

    def tile_MB(self, plane, mb):
        if plane.flexbits_present:
            plane.hp.MB_HP_FLEX(mb, do_flex=True, iTrimFlexBits=self.trim_flexbits)


class SpatialTile(DCTile, LowpassTile, HighpassTile, FlexTile):
    tile_type = "spatial"

    def tile_plane_header(self, plane):
        FlexTile.tile_plane_header(self, plane)
        DCTile.tile_plane_header(self, plane)
        LowpassTile.tile_plane_header(self, plane)
        HighpassTile.tile_plane_header(self, plane)

    def tile_MB(self, plane, mb):
        LowpassTile.tile_MB_QP(self, plane, mb)
        HighpassTile.tile_MB_QP(self, plane, mb)

        DCTile.tile_MB(self, plane, mb)
        LowpassTile.tile_MB_2(self, plane, mb)

        if plane.flexbits_present:
            plane.hp.MB_CBPHP(mb)
            plane.hp.MB_HP_FLEX(
                mb, do_hp=True, do_flex=True, iTrimFlexBits=self.trim_flexbits
            )
        else:
            HighpassTile.tile_MB_2(self, plane, mb)


class MB(object):
    def __init__(
        self, MBx, MBy, MBxt, MByt, tile_width_mb, NumComponents, leftMB, topMB
    ):
        self.MBx = MBx
        self.MBy = MBy

        self.MBxt = MBxt
        self.MByt = MByt

        self.leftMB = leftMB
        self.topMB = topMB

        self.IsMBLeftEdgeofTileFlag = MBxt == 0
        self.IsMBTopEdgeofTileFlag = MByt == 0
        self.InitializeContext = (
            self.IsMBLeftEdgeofTileFlag and self.IsMBTopEdgeofTileFlag
        )
        self.ResetTotals = (MBxt % 16) == 0
        self.ResetContext = self.ResetTotals or MBxt == tile_width_mb - 1

        self.MBDCMode = self.MBLPMode = self.MBHPMode = None
        self.HPInputVLC = Array(NumComponents, 16, 16, 0)
        self.HPInputFlex = Array(NumComponents, 16, 16, 0)

        self.MbDCLP = Array(NumComponents, 16, 0)

        self.MBCBPHP = Array(NumComponents, None)

        self.ModelBitsMBHP = Array(2, None)

        self.MBQPIndexLP = 0

        self.MBBuffer = Array(NumComponents, 16 * 16, 0)

    def cleanup(self):
        del self.HPInputVLC
        del self.HPInputFlex
        del self.MbDCLP
        del self.MBCBPHP
        del self.ModelBitsMBHP
        del self.MBQPIndexLP


class FreqBand(object):
    def __init__(self, plane):
        self.plane = plane
        self.ds = self.plane.ds

        self.image_plane_uniform_flag = 0
        self.qp = None
        self.qp_index = collections.defaultdict(lambda: 0)

    def decode_block(self, bChroma, iLocation):
        def decode_first_index():
            if self.iBand == LP:
                sAdaptVLC = self.DecFirstIndLPChr if bChroma else self.DecFirstIndLPLum
            elif self.iBand == HP:
                sAdaptVLC = self.DecFirstIndHPChr if bChroma else self.DecFirstIndHPLum

            first_index = self.ds.huff(FIRST_INDEX[sAdaptVLC.TableIndex], "FIRST_INDEX")

            sAdaptVLC.DiscrimVal1 += FirstIndexDelta[sAdaptVLC.DeltaTableIndex][
                first_index
            ]
            sAdaptVLC.DiscrimVal2 += FirstIndexDelta[sAdaptVLC.Delta2TableIndex][
                first_index
            ]

            if DEBUG2:
                log.info(
                    "first_index=%02x using table %d"
                    % (first_index, sAdaptVLC.TableIndex)
                )

            return (
                first_index & 0x01,
                (first_index >> 1) & 0x01,
                (first_index >> 2) & 0x01,
                first_index >> 3,
            )

        def decode_index(iLocation, iContext):
            if self.iBand == LP:
                if bChroma:
                    sAdaptVLC = self.DecIndLPChr1 if iContext else self.DecIndLPChr0
                else:
                    sAdaptVLC = self.DecIndLPLum1 if iContext else self.DecIndLPLum0
            elif self.iBand == HP:
                if bChroma:
                    sAdaptVLC = self.DecIndHPChr1 if iContext else self.DecIndHPChr0
                else:
                    sAdaptVLC = self.DecIndHPLum1 if iContext else self.DecIndHPLum0

            if iLocation < 15:
                iIndex = self.ds.huff(INDEX_A[sAdaptVLC.TableIndex], "INDEX_A")
                sAdaptVLC.DiscrimVal1 += Index1Delta[sAdaptVLC.DeltaTableIndex][iIndex]
                sAdaptVLC.DiscrimVal2 += Index1Delta[sAdaptVLC.Delta2TableIndex][iIndex]
            elif iLocation == 15:
                iIndex = self.ds.huff(INDEX_B, "INDEX_B")
            else:
                iIndex = self.ds.unpack_bits(1, "index_c_flag")

            return (iIndex & 0x01, (iIndex >> 1) & 0x01, iIndex >> 2)

        def decode_run(iMaxRun):
            iRunBinx = [10, 10, 5, 5, 5, 5, 0, 0, 0, 0]
            iRunFixedLength = [0, 0, 1, 1, 3, 0, 0, 1, 1, 2, 0, 0, 0, 0, 1]
            iRemap = [1, 2, 3, 5, 7, 1, 2, 3, 5, 7, 1, 2, 3, 4, 5]

            if iMaxRun < 1 or iMaxRun > 14:
                raise Exception("decode_run passed invalid iMaxRun=%d" % iMaxRun)

            if iMaxRun < 5:
                iRun = (
                    self.ds.huff(RUN_VALUE[iMaxRun], "RUN_VALUE") if iMaxRun != 1 else 1
                )
            else:
                iIndex = self.ds.huff(RUN_INDEX, "RUN_INDEX") + iRunBinx[iMaxRun - 5]
                iFixed = iRunFixedLength[iIndex]
                iRun = iRemap[iIndex]
                if iFixed:
                    iRun += self.ds.unpack_bits(iFixed, "run_ref")

            if iRun < 1 or iRun > iMaxRun:
                raise Exception("decode_run %d not in range 1-%d" % (iRun, iMaxRun))

            return iRun

        if DEBUG2:
            log.info("decode_block")

        if iLocation < 0 or iLocation > 15:
            raise Exception(
                "decode_block start location %d not in range 0-15" % iLocation
            )

        (
            run_is_zero,
            level_is_not_1,
            next_is_immediate,
            next_after_run,
        ) = decode_first_index()
        iContext = run_is_zero & next_is_immediate

        level_sign_flag = self.ds.unpack_bits(1, "level_sign_flag")
        level = signed_value(
            self.decode_abs_level(bChroma, iContext) if level_is_not_1 else 1,
            level_sign_flag,
        )

        run = 0 if run_is_zero else decode_run(15 - iLocation)
        block = [(run, level)]
        iLoc = iLocation + run + 1

        while next_is_immediate or next_after_run:
            run = 0 if next_is_immediate else decode_run(15 - iLoc)
            iLoc += run + 1
            if iLoc > 16:
                raise Exception(
                    "decode_block decoded location %d not in range 0-15" % iLoc
                )

            level_is_not_1, next_is_immediate, next_after_run = decode_index(
                iLoc, iContext
            )
            iContext &= next_is_immediate

            level_sign_flag = self.ds.unpack_bits(1, "level_sign_flag")
            level = signed_value(
                self.decode_abs_level(bChroma, iContext) if level_is_not_1 else 1,
                level_sign_flag,
            )

            block.append((run, level))

        if DEBUG2:
            log.info("decode_block[Loc %d] = %s" % (iLocation, repr(block)))

        return block

    def decode_abs_level(self, bChroma, iContext):
        if self.iBand == DC:
            sAdaptVLC = self.AbsLevelIndDCChr if bChroma else self.AbsLevelIndDCLum
        elif self.iBand == LP:
            sAdaptVLC = self.AbsLevelIndLP1 if iContext else self.AbsLevelIndLP0
        elif self.iBand == HP:
            sAdaptVLC = self.AbsLevelIndHP1 if iContext else self.AbsLevelIndHP0

        iRemap = [2, 3, 4, 6, 10, 14]
        iFixedLen = [0, 0, 1, 2, 2, 2]

        table_index = sAdaptVLC.TableIndex
        abs_level_index = self.ds.huff(
            ABS_LEVEL_INDEX[sAdaptVLC.TableIndex], "ABS_LEVEL_INDEX"
        )
        sAdaptVLC.DiscrimVal1 += AbslevelIndexDelta[0][abs_level_index]

        if abs_level_index < 6:
            iFixed = iFixedLen[abs_level_index]
            iLevel = iRemap[abs_level_index]

            if iFixed > 0:
                iLevel += self.ds.unpack_bits(iFixed, "level_ref")

        else:
            iFixed = self.ds.unpack_bits(4, "fixed_num") + 4
            if iFixed == 19:
                iFixed += self.ds.unpack_bits(2, "fixed_num_ext")
                if iFixed == 22:
                    iFixed += self.ds.unpack_bits(3, "fixed_num_ext2")

            iLevel = 2 + (1 << iFixed) + self.ds.unpack_bits(iFixed, "level_ref")

        if DEBUG2:
            log.info(
                "decode_abs_level chroma=%d context=%d tbl_idx=%d level_index=%d fixed=%d value=%d"
                % (bChroma, iContext, table_index, abs_level_index, iFixed, iLevel)
            )

        return iLevel

    def UpdateModelMB(self, iLapMean, Model):
        iModelWeight = 70
        iWeight0 = [240, 12, 1]
        iWeight1 = [
            [0, 240, 120, 80, 60, 48, 40, 34, 30, 27, 24, 22, 20, 18, 17, 16],
            [0, 12, 6, 4, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1],
            [0, 16, 8, 5, 4, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1],
        ]

        iLapMean[0] *= iWeight0[self.iBand]

        iLapMean[1] *= iWeight1[self.iBand][self.plane.NumComponents - 1]
        if self.iBand == HP:
            iLapMean[1] >>= 4

        iNumModels = 1 if self.plane.internal_clr_fmt == YONLY else 2
        for j in range(iNumModels):
            iMS = Model.MState[j]
            iDelta = (iLapMean[j] - iModelWeight) >> 2
            if iDelta <= -8:
                iDelta += 4
                if iDelta < -16:
                    iDelta = -16
                iMS += iDelta
                if iMS < -8:
                    if Model.MBits[j] == 0:
                        iMS = -8
                    else:
                        iMS = 0
                        Model.MBits[j] -= 1
            elif iDelta >= 8:
                iDelta -= 4
                if iDelta > 15:
                    iDelta = 15
                iMS += iDelta
                if iMS > 8:
                    if Model.MBits[j] >= 15:
                        Model.MBits[j] = 15
                        iMS = 8
                    else:
                        iMS = 0
                        Model.MBits[j] += 1

            Model.MState[j] = iMS

    def sign_optional(self, value):
        return (
            0
            if value == 0
            else (-value if self.ds.unpack_bits(1, "optional_sign_flag") else value)
        )


class DCBand(FreqBand):
    iBand = DC

    def __init__(self, plane):
        FreqBand.__init__(self, plane)

        self.ModelDC = Model()
        self.AbsLevelIndDCLum = AdaptiveVLC()
        self.AbsLevelIndDCChr = AdaptiveVLC()

    def MB_DC(self, mb):
        if mb.InitializeContext:
            self.InitializeDCVLC()
            self.ModelDC.InitializeModelMB(self.iBand)

        plane = self.plane
        DCInput = Array(plane.NumComponents, None)
        iLapMean = [0, 0]
        if plane.internal_clr_fmt in [YONLY, YUVK, NCOMPONENT]:
            for iComponent in range(plane.NumComponents):
                chroma = chroma_component(iComponent)

                bAbsLevel = self.ds.unpack_bits(1, "bAbsLevel")
                if bAbsLevel:
                    iLapMean[chroma] = iLapMean[chroma] + 1

                DCInput[iComponent] = self.decode_DC(
                    self.ModelDC.MBits[chroma], False, bAbsLevel
                )
                if DEBUG1:
                    log.info("DCInput[%d]=%d" % (iComponent, DCInput[iComponent]))

        else:
            val_dc_yuv = self.ds.huff(VAL_DC_YUV, "VAL_DC_YUV")

            for iComponent, mask in [(0, 4), (1, 2), (2, 1)]:
                chroma = chroma_component(iComponent)

                bAbsLevel = (val_dc_yuv & mask) != 0
                if bAbsLevel:
                    iLapMean[chroma] = iLapMean[chroma] + 1

                DCInput[iComponent] = self.decode_DC(
                    self.ModelDC.MBits[chroma], chroma, bAbsLevel
                )
                if DEBUG1:
                    log.info("DCInput[%d]=%d" % (iComponent, DCInput[iComponent]))

        self.UpdateModelMB(iLapMean, self.ModelDC)

        if mb.ResetContext:
            self.AdaptDC()

        for i in range(plane.NumComponents):
            mb.MbDCLP[i][0] = DCInput[i]

        if mb.IsMBLeftEdgeofTileFlag and mb.IsMBTopEdgeofTileFlag:
            mb.MBDCMode = NO_PREDICTION
        elif mb.IsMBLeftEdgeofTileFlag and not mb.IsMBTopEdgeofTileFlag:
            mb.MBDCMode = PREDICT_FROM_TOP
        elif (not mb.IsMBLeftEdgeofTileFlag) and mb.IsMBTopEdgeofTileFlag:
            mb.MBDCMode = PREDICT_FROM_LEFT
        else:
            iLeft = mb.leftMB.MbDCLP[0][0]
            iTop = mb.topMB.MbDCLP[0][0]
            iTopLeft = mb.topMB.leftMB.MbDCLP[0][0]

            if plane.internal_clr_fmt in [YONLY, NCOMPONENT]:
                iStrHor = abs(iTopLeft - iLeft)
                iStrVer = abs(iTopLeft - iTop)
            else:
                iLeftU = mb.leftMB.MbDCLP[1][0]
                iTopU = mb.topMB.MbDCLP[1][0]
                iTopLeftU = mb.topMB.leftMB.MbDCLP[1][0]
                iLeftV = mb.leftMB.MbDCLP[2][0]
                iTopV = mb.topMB.MbDCLP[2][0]
                iTopLeftV = mb.topMB.leftMB.MbDCLP[2][0]

                iScale = 2
                iStrHor = (
                    abs(iTopLeft - iLeft) * iScale
                    + abs(iTopLeftU - iLeftU)
                    + abs(iTopLeftV - iLeftV)
                )
                iStrVer = (
                    abs(iTopLeft - iTop) * iScale
                    + abs(iTopLeftU - iTopU)
                    + abs(iTopLeftV - iTopV)
                )

            iOrWt = 4
            if iStrHor * iOrWt < iStrVer:
                mb.MBDCMode = PREDICT_FROM_TOP
            elif iStrVer * iOrWt < iStrHor:
                mb.MBDCMode = PREDICT_FROM_LEFT
            else:
                mb.MBDCMode = PREDICT_FROM_TOP_LEFT

        for iComponent in range(plane.NumComponents):
            if mb.MBDCMode == PREDICT_FROM_LEFT:
                mb.MbDCLP[iComponent][0] += mb.leftMB.MbDCLP[iComponent][0]
            elif mb.MBDCMode == PREDICT_FROM_TOP:
                mb.MbDCLP[iComponent][0] += mb.topMB.MbDCLP[iComponent][0]
            elif mb.MBDCMode == PREDICT_FROM_TOP_LEFT:
                mb.MbDCLP[iComponent][0] += (
                    mb.topMB.MbDCLP[iComponent][0] + mb.leftMB.MbDCLP[iComponent][0]
                ) >> 1

            if DEBUG1:
                log.info(
                    "MBDCMode=%s updated DCInput[%d]=%d"
                    % (
                        value_name(mb.MBDCMode, PREDICT_NAME),
                        iComponent,
                        mb.MbDCLP[iComponent][0],
                    )
                )

        for iComponent in range(plane.NumComponents):
            mb.MBBuffer[iComponent][16 * ICT4x4InvPermArr[0]] = mb.MbDCLP[iComponent][
                0
            ] * self.qp.ScalingFactor(iComponent)

    def decode_DC(self, iModelBits, bChroma, bAbsLevel):
        iDC = self.decode_abs_level(bChroma, 0) - 1 if bAbsLevel else 0

        if iModelBits:
            iDC = (iDC << iModelBits) | self.ds.unpack_bits(iModelBits, "iDC")

        iDC = self.sign_optional(iDC)

        return iDC

    def InitializeDCVLC(self):
        self.AbsLevelIndDCLum.InitializeVLCTable1()
        self.AbsLevelIndDCChr.InitializeVLCTable1()

    def AdaptDC(self):
        self.AbsLevelIndDCLum.AdaptVLCTable1()
        self.AbsLevelIndDCChr.AdaptVLCTable1()


class LPBand(FreqBand):
    iBand = LP

    def __init__(self, plane):
        FreqBand.__init__(self, plane)

        self.ModelLP = Model()

        self.DecFirstIndLPLum = AdaptiveVLC()
        self.DecIndLPLum0 = AdaptiveVLC()
        self.DecIndLPLum1 = AdaptiveVLC()
        self.DecFirstIndLPChr = AdaptiveVLC()
        self.DecIndLPChr0 = AdaptiveVLC()
        self.DecIndLPChr1 = AdaptiveVLC()
        self.AbsLevelIndLP0 = AdaptiveVLC()
        self.AbsLevelIndLP1 = AdaptiveVLC()

    def MB_LP(self, mb):
        if mb.InitializeContext:
            self.InitializeCountCBPLP()
            self.InitializeLPVLC()
            self.LowpassScan = AdaptiveScan(grgiZigzagInv4x4H)
            self.ModelLP.InitializeModelMB(self.iBand)

        if mb.ResetTotals:
            self.LowpassScan.ResetTotals()

        iLapMean = [0, 0]
        plane = self.plane

        iFullPlanes = plane.NumComponents

        if plane.internal_clr_fmt == YUV444:
            iMax = iFullPlanes * 4 - 5
            if self.CountZeroCBPLP <= 0 or self.CountMaxCBPLP < 0:
                cbplp_yuv1 = self.ds.huff(CBPLP_YUV1_444, "CBPLP_YUV1")
                iCBPLP = (
                    iMax - cbplp_yuv1
                    if self.CountMaxCBPLP < self.CountZeroCBPLP
                    else cbplp_yuv1
                )
            else:
                iCBPLP = self.ds.unpack_bits(iFullPlanes, "CBPLP_YUV2")

            self.UpdateCountCBPLP(iCBPLP, iMax)
        else:
            iCBPLP = 0
            for n in range(plane.NumComponents):
                cbplp_ch_bit = self.ds.unpack_bits(1, "cbplp_ch_bit")
                iCBPLP |= cbplp_ch_bit << n

        LPInput = Array(plane.NumComponents, 16, 0)

        for n in range(iFullPlanes):
            iIndex = chroma_component(n)
            if (iCBPLP >> n) & 1:
                iLocation = 1

                block = self.decode_block(iIndex, iLocation)
                if DEBUG1:
                    log.info("decode_block[LP Loc %d] = %s" % (iLocation, repr(block)))

                iLapMean[iIndex] += len(block)

                i = 1
                for run, level in block:
                    i += run
                    self.AdaptiveLPScan(n, i, level, LPInput)
                    i += 1

            if DEBUG1:
                log.info("LPInput0[%d]=%s" % (n, repr(LPInput[n][1:])))
                log.info(
                    "ModelLP MBits[%d]=%d MState[%d]=%d"
                    % (
                        iIndex,
                        self.ModelLP.MBits[iIndex],
                        iIndex,
                        self.ModelLP.MState[iIndex],
                    )
                )

            iModelBits = self.ModelLP.MBits[iIndex]
            if iModelBits:
                for k in range(1, 16):
                    LPInput[n][k] = self.refine_LP(LPInput[n][k], iModelBits)

                if DEBUG1:
                    log.info("LPInput1[%d]=%s" % (n, repr(LPInput[n][1:])))

        self.UpdateModelMB(iLapMean, self.ModelLP)

        if mb.ResetContext:
            self.AdaptLP()

        for i in range(plane.NumComponents):
            for j in range(1, 16):
                mb.MbDCLP[i][j] = LPInput[i][j]

        if mb.MBDCMode == PREDICT_FROM_LEFT and mb.MBQPIndexLP == mb.leftMB.MBQPIndexLP:
            mb.MBLPMode = PREDICT_FROM_LEFT
        elif mb.MBDCMode == PREDICT_FROM_TOP and mb.MBQPIndexLP == mb.topMB.MBQPIndexLP:
            mb.MBLPMode = PREDICT_FROM_TOP
        else:
            mb.MBLPMode = NO_PREDICTION

        if DEBUG1:
            log.info("MBLPMode=%d" % mb.MBLPMode)

        for i in range(plane.NumComponents):
            if mb.MBLPMode == PREDICT_FROM_LEFT:
                for j in [1, 2, 3]:
                    mb.MbDCLP[i][j] += mb.leftMB.MbDCLP[i][j]
            elif mb.MBLPMode == PREDICT_FROM_TOP:
                for j in [4, 8, 12]:
                    mb.MbDCLP[i][j] += mb.topMB.MbDCLP[i][j]

        for i in range(plane.NumComponents):
            pSrc = mb.MBBuffer[i]
            scaling_factor = self.qp.ScalingFactor(i)

            for j in range(1, 16):
                pSrc[16 * ICT4x4InvPermArr[j]] = mb.MbDCLP[i][j] * scaling_factor

    def AdaptiveLPScan(self, n, i, iValue, LPInput):
        LPInput[n][self.LowpassScan.Translate(i)] = iValue
        self.LowpassScan.Adapt(i)

    def refine_LP(self, iCoeff, iModelBits):
        coeff_ref = self.ds.unpack_bits(iModelBits, "lp_coeff_ref")

        if iCoeff > 0:
            iCoeff = (iCoeff << iModelBits) + coeff_ref
        elif iCoeff < 0:
            iCoeff = (iCoeff << iModelBits) - coeff_ref
        else:
            iCoeff = self.sign_optional(coeff_ref)

        return iCoeff

    def UpdateCountCBPLP(self, iCBPLP, iMax):
        self.CountZeroCBPLP += 1 - (4 if iCBPLP == 0 else 0)
        self.CountZeroCBPLP = Clip(self.CountZeroCBPLP, -8, 7)
        self.CountMaxCBPLP += 1 - (4 if iCBPLP == iMax else 0)
        self.CountMaxCBPLP = Clip(self.CountMaxCBPLP, -8, 7)

    def InitializeCountCBPLP(self):
        self.CountZeroCBPLP = self.CountMaxCBPLP = 1

    def InitializeLPVLC(self):
        self.DecFirstIndLPLum.InitializeVLCTable2()
        self.DecIndLPLum0.InitializeVLCTable2()
        self.DecIndLPLum1.InitializeVLCTable2()
        self.DecFirstIndLPChr.InitializeVLCTable2()
        self.DecIndLPChr0.InitializeVLCTable2()
        self.DecIndLPChr1.InitializeVLCTable2()
        self.AbsLevelIndLP0.InitializeVLCTable1()
        self.AbsLevelIndLP1.InitializeVLCTable1()

    def AdaptLP(self):
        self.DecFirstIndLPLum.AdaptVLCTable2(4)
        self.DecIndLPLum0.AdaptVLCTable2(3)
        self.DecIndLPLum1.AdaptVLCTable2(3)
        self.DecFirstIndLPChr.AdaptVLCTable2(4)
        self.DecIndLPChr0.AdaptVLCTable2(3)
        self.DecIndLPChr1.AdaptVLCTable2(3)
        self.AbsLevelIndLP0.AdaptVLCTable1()
        self.AbsLevelIndLP1.AdaptVLCTable1()


class HPBand(FreqBand):
    iBand = HP

    def __init__(self, plane):
        FreqBand.__init__(self, plane)

        self.ModelHP = Model()

        self.DecNumCBPHP = AdaptiveVLC()
        self.DecNumBlkCBPHP = AdaptiveVLC()
        self.DecFirstIndHPLum = AdaptiveVLC()
        self.DecIndHPLum0 = AdaptiveVLC()
        self.DecIndHPLum1 = AdaptiveVLC()
        self.DecFirstIndHPChr = AdaptiveVLC()
        self.DecIndHPChr0 = AdaptiveVLC()
        self.DecIndHPChr1 = AdaptiveVLC()
        self.AbsLevelIndHP0 = AdaptiveVLC()
        self.AbsLevelIndHP1 = AdaptiveVLC()

        self.CBPHPModelHP = CBPHPModel()

    def MB_CBPHP(self, mb):
        self.mb = mb

        iFLC = [0, 2, 1, 2, 2, 0]
        iOff = [0, 4, 2, 8, 12, 1]
        iOut = [0, 15, 3, 12, 1, 2, 4, 8, 5, 6, 9, 10, 7, 11, 13, 14]
        iDiffCBPHP = Array(self.plane.NumComponents, 0)

        if self.plane.internal_clr_fmt in [YONLY, NCOMPONENT, YUVK]:
            NumBlkCBPHPDelta = NumBlkCBPHPDelta1
            NUM_BLKCBPHP = NUM_BLKCBPHP1
        else:
            NumBlkCBPHPDelta = NumBlkCBPHPDelta2
            NUM_BLKCBPHP = NUM_BLKCBPHP2

        if mb.InitializeContext:
            self.InitializeCBPHPVLC()

        for iComponent in range(
            self.plane.NumComponents
            if self.plane.internal_clr_fmt in [YUVK, NCOMPONENT]
            else 1
        ):
            sAdaptVLC = self.DecNumCBPHP
            num_cbphp = self.ds.huff(NUM_CBPHP[sAdaptVLC.TableIndex], "NUM_CBPHP")
            sAdaptVLC.DiscrimVal1 += NumCBPHPDelta[sAdaptVLC.DeltaTableIndex][num_cbphp]
            iCBPHP = self.refine_CBPHP(num_cbphp)

            for iBlock in range(4):
                if iCBPHP & (1 << iBlock):
                    sAdaptVLC = self.DecNumBlkCBPHP
                    num_blkcbphp = self.ds.huff(
                        NUM_BLKCBPHP[sAdaptVLC.TableIndex], "NUM_BLKCBPHP"
                    )
                    sAdaptVLC.DiscrimVal1 += NumBlkCBPHPDelta[
                        sAdaptVLC.DeltaTableIndex
                    ][num_blkcbphp]
                    iVal = num_blkcbphp + 1
                    iBlkCBPHP = 0

                    if iVal >= 6:
                        iBlkCBPHP = 0x10 * (self.ds.huff(CHR_CBPHP, "CHR_CBPHP") + 1)
                        if iVal >= 9:
                            iVal += self.ds.huff(VAL_INC, "VAL_INC")

                        iVal -= 6

                    iCode = iOff[iVal]
                    if iFLC[iVal]:
                        iCode += self.ds.unpack_bits(iFLC[iVal], "cbphp_iCode")

                    iBlkCBPHP += iOut[iCode]

                    if self.plane.internal_clr_fmt == YUV444:
                        iDiffCBPHP[0] |= (iBlkCBPHP & 0x0F) << (iBlock * 4)
                        for k in range(2):
                            if (iBlkCBPHP >> (k + 4)) & 0x01:
                                iCBPHPChr = self.refine_CBPHP(
                                    self.ds.huff(NUM_CH_BLK, "NUM_CH_BLK") + 1
                                )
                                iDiffCBPHP[k + 1] |= iCBPHPChr << (iBlock * 4)
                    else:
                        iDiffCBPHP[iComponent] |= iBlkCBPHP << (iBlock * 4)

        if mb.InitializeContext:
            self.InitializeCBPHPModel()

        for iComponent in range(self.plane.NumComponents):
            mb.MBCBPHP[iComponent] = self.PredCBPHP444(iComponent, iDiffCBPHP, mb)

    def refine_CBPHP(self, iNum):
        if iNum == 2:
            iRef = self.ds.huff(REF_CBPHP1, "REF_CBPHP1")
        elif iNum == 1:
            iRef = 1 << self.ds.unpack_bits(2, "iRef_scale")
        elif iNum == 3:
            iRef = 0x0F ^ (1 << self.ds.unpack_bits(2, "iRef_scale_2"))
        elif iNum == 4:
            iRef = 0x0F
        else:
            iRef = 0

        return iRef

    def InitializeCBPHPVLC(self):
        self.DecNumCBPHP.InitializeVLCTable1()
        self.DecNumBlkCBPHP.InitializeVLCTable1()

    def PredCBPHP444(self, iComponent, iDiffCBPHP, mb):
        chroma_flag = 1 if iComponent > 0 else 0
        iCBPHP = iDiffCBPHP[iComponent]
        state = self.CBPHPModelHP.CBPHPState[chroma_flag]

        if state == 0:
            if self.mb.IsMBLeftEdgeofTileFlag:
                if self.mb.IsMBTopEdgeofTileFlag:
                    iCBPHP ^= 1
                else:
                    iCBPHP ^= (mb.topMB.MBCBPHP[iComponent] >> 10) & 1
            else:
                iCBPHP ^= (mb.leftMB.MBCBPHP[iComponent] >> 5) & 1

            iCBPHP ^= 0x02 & (iCBPHP << 1)
            iCBPHP ^= 0x10 & (iCBPHP << 3)
            iCBPHP ^= 0x20 & (iCBPHP << 1)
            iCBPHP ^= (iCBPHP & 0x33) << 2
            iCBPHP ^= (iCBPHP & 0x00CC) << 6
            iCBPHP ^= (iCBPHP & 0x3300) << 2

        elif state == 2:
            iCBPHP ^= 0x0000FFFF

        self.UpdateCBPHPModel(chroma_flag, Numones(iCBPHP))

        if DEBUG1:
            log.info(
                "PredCBPHP444[%d]: CBPHPState[%d]=%d iDiffCBPHP=%d CBPHP=%04x "
                % (iComponent, chroma_flag, state, iDiffCBPHP[iComponent], iCBPHP)
            )

        return iCBPHP

    def InitializeCBPHPModel(self):
        self.CBPHPModelHP.CBPHPState[0] = self.CBPHPModelHP.CBPHPState[1] = 0
        self.CBPHPModelHP.CountOnes[0] = self.CBPHPModelHP.CountOnes[1] = -4
        self.CBPHPModelHP.CountZeroes[0] = self.CBPHPModelHP.CountZeroes[1] = 4

    def UpdateCBPHPModel(self, i, iNOrig):
        iNDiff = 3
        self.CBPHPModelHP.CountOnes[i] += iNOrig - iNDiff
        self.CBPHPModelHP.CountOnes[i] = Clip(self.CBPHPModelHP.CountOnes[i], -16, 15)

        self.CBPHPModelHP.CountZeroes[i] += (16 - iNOrig) - iNDiff
        self.CBPHPModelHP.CountZeroes[i] = Clip(
            self.CBPHPModelHP.CountZeroes[i], -16, 15
        )

        if self.CBPHPModelHP.CountOnes[i] < 0:
            if self.CBPHPModelHP.CountOnes[i] < self.CBPHPModelHP.CountZeroes[i]:
                self.CBPHPModelHP.CBPHPState[i] = 1
            else:
                self.CBPHPModelHP.CBPHPState[i] = 2
        elif self.CBPHPModelHP.CountZeroes[i] < 0:
            self.CBPHPModelHP.CBPHPState[i] = 2
        else:
            self.CBPHPModelHP.CBPHPState[i] = 0

    def MB_HP_FLEX(self, mb, do_hp=False, do_flex=False, iTrimFlexBits=0):
        plane = self.plane

        if DEBUG2:
            log.info(
                "MB_HP_FLEX do_hp=%s do_flex=%s iTrimFlexBits=%d"
                % (do_hp, do_flex, iTrimFlexBits)
            )

        if do_hp:
            if mb.InitializeContext:
                self.InitializeHPVLC()
                self.InitializeAdaptiveScanHP()
                self.ModelHP.InitializeModelMB(self.iBand)

            if mb.ResetTotals:
                self.ResetTotalsAdaptiveScanHP()

            mb.MBHPMode = self.CalcHPPredMode(mb)
            adaptive_scan = (
                self.HighpassVerScan
                if mb.MBHPMode == PREDICT_FROM_TOP
                else self.HighpassHorScan
            )

            iLapMean = [0, 0]

        for iComponent in range(plane.NumComponents):
            iIndex = chroma_component(iComponent)

            if do_flex:
                iModelBits = (
                    self.ModelHP.MBits[iIndex] if do_hp else mb.ModelBitsMBHP[iIndex]
                )

            if do_hp:
                iCBPHP = mb.MBCBPHP[iComponent]

            for iBlock in iHierScanOrder:
                if do_hp:
                    iNumNonZero = self.decode_block_adaptive(
                        iCBPHP & 1, iIndex != 0, iComponent, iBlock, adaptive_scan, mb
                    )

                if do_flex and plane.flexbits_present:
                    self.block_flexbits(
                        iComponent, iBlock, iModelBits, iTrimFlexBits, mb
                    )

                if do_hp:
                    iLapMean[iIndex] += iNumNonZero
                    iCBPHP >>= 1

        if do_hp:
            mb.ModelBitsMBHP[0] = self.ModelHP.MBits[0]
            mb.ModelBitsMBHP[1] = self.ModelHP.MBits[1]

            self.UpdateModelMB(iLapMean, self.ModelHP)

            if mb.ResetContext:
                self.AdaptHP()

        if DEBUG2:
            if do_hp:
                log.info("HPInputVLC=%s" % repr(mb.HPInputVLC))
            if do_flex:
                log.info("HPInputFlex=%s" % repr(mb.HPInputFlex))

        if (do_hp and not plane.flexbits_present) or do_flex:
            self.HPTransformCoefficientDecoding(mb)

    def HPTransformCoefficientDecoding(self, mb):
        plane = self.plane

        for iComponent in range(plane.NumComponents):
            iIndex = 0 if iComponent == 0 else 1
            scaling_factor = self.qp.ScalingFactor(iComponent)

            for blkIndex in range(16):
                for j in range(1, 16):
                    mb.MBBuffer[iComponent][16 * blkIndex + j] = (
                        (
                            mb.HPInputVLC[iComponent][blkIndex][j]
                            << mb.ModelBitsMBHP[iIndex]
                        )
                        + mb.HPInputFlex[iComponent][blkIndex][j]
                    ) * scaling_factor

            if DEBUG1:
                log.info("MBBuffer0[%d]=" % iComponent)
                for blkIndex in range(16):
                    log.info(
                        ", ".join(
                            [
                                "%d" % mb.MBBuffer[iComponent][blkIndex * 16 + j]
                                for j in range(16)
                            ]
                        )
                    )

        for iComponent in range(plane.NumComponents):
            pSrc = mb.MBBuffer[iComponent]

            if mb.MBHPMode == PREDICT_FROM_TOP:
                for blkId in [1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15]:
                    for k in [2, 10, 9]:
                        pSrc[16 * blkId + k] += pSrc[16 * (blkId - 1) + k]

            elif mb.MBHPMode == PREDICT_FROM_LEFT:
                for blkId in range(4, 16):
                    for k in [1, 5, 6]:
                        pSrc[16 * blkId + k] += pSrc[16 * (blkId - 4) + k]

            if DEBUG1:
                log.info("MBBuffer1[%d]=" % iComponent)
                for iy in range(16):
                    log.info(
                        ", ".join(
                            [
                                "%d" % mb.MBBuffer[iComponent][iy * 16 + ix]
                                for ix in range(16)
                            ]
                        )
                    )

    def CalcHPPredMode(self, mb):
        iStrengthHor = (
            abs(mb.MbDCLP[0][1]) + abs(mb.MbDCLP[0][2]) + abs(mb.MbDCLP[0][3])
        )
        iStrengthVer = (
            abs(mb.MbDCLP[0][4]) + abs(mb.MbDCLP[0][8]) + abs(mb.MbDCLP[0][12])
        )

        if self.plane.internal_clr_fmt not in [YONLY, NCOMPONENT]:
            for i in range(1, 3):
                iStrengthHor += abs(mb.MbDCLP[i][1])
                iStrengthVer += abs(mb.MbDCLP[i][4])

        iOrientationWeight = 4
        if iStrengthHor * iOrientationWeight < iStrengthVer:
            MBHPMode = PREDICT_FROM_TOP
        elif iStrengthVer * iOrientationWeight < iStrengthHor:
            MBHPMode = PREDICT_FROM_LEFT
        else:
            MBHPMode = NO_PREDICTION

        if DEBUG1:
            log.info(
                "CalcHPPredMode: iStrengthHor=%d iStrengthVer=%d result=%s     coeff=%s"
                % (
                    iStrengthHor,
                    iStrengthVer,
                    PREDICT_NAME[MBHPMode],
                    ", ".join([str(mb.MbDCLP[0][i]) for i in range(16)]),
                )
            )

        return MBHPMode

    def decode_block_adaptive(
        self, bNoSkip, bChroma, iComponent, iBlock, adaptive_scan, mb
    ):
        if DEBUG2:
            log.info("decode_block_adaptive")

        iNumNonZero = 0

        if bNoSkip:
            if DEBUG1:
                log.info("scan_order = %s" % repr(adaptive_scan.order))
                log.info("scan_totals = %s" % repr(adaptive_scan.totals))

            iLocation = 1
            block = self.decode_block(bChroma, iLocation)
            if DEBUG1:
                log.info(
                    "decode_block_HP[%d,%d] = %s" % (iComponent, iBlock, repr(block))
                )

            while block:
                run, level = block.pop(0)
                iLocation += run

                if iLocation < 1 or iLocation > 15:
                    raise Exception(
                        "decode_block_adaptive iLocation=%d (out of range 1-15"
                        % iLocation
                    )
                    return 0

                if DEBUG2:
                    log.info(
                        "AdaptiveHPScan i=%d block=%d loc=%d k=%d value=%d"
                        % (
                            iComponent,
                            iBlock,
                            iLocation,
                            adaptive_scan.Translate(iLocation),
                            level,
                        )
                    )

                mb.HPInputVLC[iComponent][iBlock][
                    adaptive_scan.Translate(iLocation)
                ] = level
                adaptive_scan.Adapt(iLocation)

                iLocation += 1
                iNumNonZero += 1

        if DEBUG2:
            log.info("decode_block_adaptive return %d" % iNumNonZero)

        return iNumNonZero

    def block_flexbits(self, iComponent, iBlock, iModelBits, iTrimFlexBits, mb):
        iFlexBitsLeft = iModelBits - iTrimFlexBits
        if iFlexBitsLeft > 0:
            if DEBUG1:
                log.info(
                    "block_flexbits block=%d modelbits=%d trim=%d bitsleft=%d"
                    % (iBlock, iModelBits, iTrimFlexBits, iFlexBitsLeft)
                )

            for n in iTransposeFlex[1:]:
                flex_ref = self.ds.unpack_bits(iFlexBitsLeft, "flex_ref")
                iVLCCoeff = mb.HPInputVLC[iComponent][iBlock][n]

                if iVLCCoeff > 0:
                    iFlexCoeff = flex_ref
                elif iVLCCoeff < 0:
                    iFlexCoeff = -flex_ref
                else:
                    iFlexCoeff = self.sign_optional(flex_ref)

                if DEBUG2:
                    log.info(
                        "decode_flex %d FlexBits=%d VLCCoeff=%d flex_ref=%d => FlexCoeff=%d"
                        % (n, iFlexBitsLeft, iVLCCoeff, flex_ref, iFlexCoeff)
                    )

                mb.HPInputFlex[iComponent][iBlock][n] = iFlexCoeff << iTrimFlexBits

    def AdaptHP(self):
        self.DecFirstIndHPLum.AdaptVLCTable2(4)
        self.DecIndHPLum0.AdaptVLCTable2(3)
        self.DecIndHPLum1.AdaptVLCTable2(3)
        self.DecFirstIndHPChr.AdaptVLCTable2(4)
        self.DecIndHPChr0.AdaptVLCTable2(3)
        self.DecIndHPChr1.AdaptVLCTable2(3)
        self.AbsLevelIndHP0.AdaptVLCTable1()
        self.AbsLevelIndHP1.AdaptVLCTable1()
        self.DecNumCBPHP.AdaptVLCTable1()
        self.DecNumBlkCBPHP.AdaptVLCTable1()

    def InitializeHPVLC(self):
        self.DecFirstIndHPLum.InitializeVLCTable2()
        self.DecIndHPLum0.InitializeVLCTable2()
        self.DecIndHPLum1.InitializeVLCTable2()
        self.DecFirstIndHPChr.InitializeVLCTable2()
        self.DecIndHPChr0.InitializeVLCTable2()
        self.DecIndHPChr1.InitializeVLCTable2()
        self.AbsLevelIndHP0.InitializeVLCTable1()
        self.AbsLevelIndHP1.InitializeVLCTable1()

    def InitializeAdaptiveScanHP(self):
        self.HighpassHorScan = AdaptiveScan(grgiZigzagInv4x4H_)
        self.HighpassVerScan = AdaptiveScan(grgiZigzagInv4x4V_)

    def ResetTotalsAdaptiveScanHP(self):
        self.HighpassHorScan.ResetTotals()
        self.HighpassVerScan.ResetTotals()


class AdaptiveScan(object):
    ScanTotals = [None, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 8, 6, 4]

    def __init__(self, order):
        self.order = order[:]
        self.ResetTotals()

    def ResetTotals(self):
        self.totals = AdaptiveScan.ScanTotals[:]

    def Translate(self, i):
        return self.order[i]

    def Adapt(self, i):
        self.totals[i] += 1

        if i > 1 and self.totals[i] > self.totals[i - 1]:
            self.order[i], self.order[i - 1] = (self.order[i - 1], self.order[i])
            self.totals[i], self.totals[i - 1] = (self.totals[i - 1], self.totals[i])


class AdaptiveVLC(object):
    def __init__(self):
        pass

    def InitializeVLCTable1(self):
        self.TableIndex = self.DeltaTableIndex = self.DiscrimVal1 = 0

    def AdaptVLCTable1(self):
        iMaxTableIndex = 1
        cLowerBound = -8
        cUpperBound = 8
        if self.DiscrimVal1 < cLowerBound and self.TableIndex != 0:
            self.TableIndex -= 1
            self.DiscrimVal1 = 0
        elif self.DiscrimVal1 > cUpperBound and self.TableIndex != iMaxTableIndex:
            self.TableIndex += 1
            self.DiscrimVal1 = 0
        else:
            self.DiscrimVal1 = Clip(self.DiscrimVal1, -64, 64)

    def InitializeVLCTable2(self):
        self.DeltaTableIndex = self.DiscrimVal1 = self.DiscrimVal2 = 0
        self.TableIndex = self.Delta2TableIndex = 1

    def AdaptVLCTable2(self, iMaxTableIndex):
        bChange = False
        iDiscrimLow = self.DiscrimVal1
        iDiscrimHigh = self.DiscrimVal2
        cLowerBound = -8
        cUpperBound = 8

        if iDiscrimLow < cLowerBound and self.TableIndex != 0:
            self.TableIndex -= 1
            bChange = True
        elif iDiscrimHigh > cUpperBound and self.TableIndex != iMaxTableIndex:
            self.TableIndex += 1
            bChange = True

        if bChange:
            self.DiscrimVal1 = self.DiscrimVal2 = 0
            if self.TableIndex == iMaxTableIndex:
                self.DeltaTableIndex = self.Delta2TableIndex = self.TableIndex - 1
            elif self.TableIndex == 0:
                self.DeltaTableIndex = self.Delta2TableIndex = self.TableIndex
            else:
                self.DeltaTableIndex = self.TableIndex - 1
                self.Delta2TableIndex = self.TableIndex
        else:
            self.DiscrimVal1 = Clip(self.DiscrimVal1, -64, 64)
            self.DiscrimVal2 = Clip(self.DiscrimVal2, -64, 64)


class CBPHPModel(object):
    def __init__(self):
        self.CBPHPState = [None, None]
        self.CountOnes = [None, None]
        self.CountZeroes = [None, None]


class Model(object):
    def __init__(self):
        pass

    def InitializeModelMB(self, iBand):
        bits = (2 - iBand) * 4

        self.MState = [0, 0]
        self.MBits = [bits, bits]


class QP(object):
    def __init__(self, ds, NumComponents, NumQPs, scaled_flag, band):
        def QuantMap(iQP, iComponent):
            if iQP == 0:
                ScalingFactor = 1

            elif not scaled_flag:
                iNotScaledShift = -2
                if iQP < 32:
                    iMan = (iQP + 3) >> 2
                    iExp = 0
                elif iQP < 48:
                    iMan = (16 + (iQP & 15) + 1) >> 1
                    iExp = (iQP >> 4) + iNotScaledShift
                else:
                    iMan = 16 + (iQP & 15)
                    iExp = ((iQP >> 4) - 1) + iNotScaledShift

                ScalingFactor = iMan << iExp

            else:
                iScaledShift = 0 if iComponent > 0 and band in [DC, LP] else 1

                if iQP < 16:
                    iMan = iQP
                    iExp = iScaledShift
                else:
                    iMan = 16 + (iQP & 15)
                    iExp = ((iQP >> 4) - 1) + iScaledShift

                ScalingFactor = iMan << iExp

                if DEBUG2:
                    log.info(
                        "QuantMap: iQ=%d band=%d iComponent=%d iScaledShift=%d ScalingFactor=%d"
                        % (iQP, band, iComponent, iScaledShift, ScalingFactor)
                    )

            if ScalingFactor < 1:
                raise Exception("QuantMap: ScalingFactor %s" % ScalingFactor)

            return ScalingFactor

        if DEBUG1 and NumQPs > 1:
            log.info("***NumQPs=%d" % NumQPs)

        self.NumQPs = NumQPs
        self.IndexQPs = 0
        self.QuantScalingFactor = Array(NumComponents, NumQPs, None)

        for j in range(NumQPs):
            component_mode = (
                ds.check_bit_field(
                    2,
                    "component_mode",
                    COMPONENT_MODE_NAMES.keys(),
                    COMPONENT_MODE_NAMES,
                )
                if NumComponents != 1
                else UNIFORM
            )

            if component_mode == UNIFORM:
                quant = ds.unpack_bits(8, "QP_uniform")
                for iComponent in range(NumComponents):
                    self.QuantScalingFactor[iComponent][j] = QuantMap(quant, iComponent)

            elif component_mode == SEPARATE:
                self.QuantScalingFactor[0][j] = QuantMap(
                    ds.unpack_bits(8, "QP_separate_luma"), 0
                )
                quant_chroma = ds.unpack_bits(8, "QP_separate_chroma")
                for iComponent in range(1, NumComponents):
                    self.QuantScalingFactor[iComponent][j] = QuantMap(
                        quant_chroma, iComponent
                    )

            elif component_mode == INDEPENDENT:
                for iComponent in range(NumComponents):
                    self.QuantScalingFactor[iComponent][j] = QuantMap(
                        ds.unpack_bits(8, "QP_independent"), iComponent
                    )

    def ScalingFactor(self, iComponent):
        return self.QuantScalingFactor[iComponent][self.IndexQPs]


def chroma_component(iComponent):
    return 0 if iComponent == 0 else 1


def value_name(v, name_table):
    return name_table.get(v, str(v))


def signed_value(value, sign_flag):
    return -value if sign_flag else value


def twos_complement_byte(value):
    return value if value & 0x80 == 0 else value - 256


def Numones(x):
    value = 0

    while x != 0:
        value += x & 1
        x >>= 1

    return value


def Clip(x, iLow, iHigh):
    if x < iLow:
        return iLow

    if x > iHigh:
        return iHigh

    return x


def Array(*args):
    if len(args) == 2:
        init = args[1]
        return [init] * args[0]

    return [Array(*args[1:]) for i in range(args[0])]


def strIDCT4x4Stage1(iCoeff):
    iCoeff[0], iCoeff[1], iCoeff[2], iCoeff[3] = strDCT2x2up(
        [iCoeff[0], iCoeff[1], iCoeff[2], iCoeff[3]]
    )

    iCoeff[5], iCoeff[4], iCoeff[7], iCoeff[6] = invOdd(
        [iCoeff[5], iCoeff[4], iCoeff[7], iCoeff[6]]
    )

    iCoeff[10], iCoeff[8], iCoeff[11], iCoeff[9] = invOdd(
        [iCoeff[10], iCoeff[8], iCoeff[11], iCoeff[9]]
    )

    iCoeff[15], iCoeff[14], iCoeff[13], iCoeff[12] = invOddOdd(
        [iCoeff[15], iCoeff[14], iCoeff[13], iCoeff[12]]
    )

    return fourbutterfly(
        iCoeff, [[0, 4, 8, 12], [1, 5, 9, 13], [2, 6, 10, 14], [3, 7, 11, 15]]
    )


def strIDCT4x4Stage2(iCoeff):
    iCoeff[2], iCoeff[3], iCoeff[6], iCoeff[7] = invOdd(
        [iCoeff[2], iCoeff[3], iCoeff[6], iCoeff[7]]
    )

    iCoeff[8], iCoeff[12], iCoeff[9], iCoeff[13] = invOdd(
        [iCoeff[8], iCoeff[12], iCoeff[9], iCoeff[13]]
    )

    iCoeff[10], iCoeff[14], iCoeff[11], iCoeff[15] = invOddOdd(
        [iCoeff[10], iCoeff[14], iCoeff[11], iCoeff[15]]
    )

    iCoeff[0], iCoeff[4], iCoeff[1], iCoeff[5] = strDCT2x2up(
        [iCoeff[0], iCoeff[4], iCoeff[1], iCoeff[5]]
    )

    return fourbutterfly(
        iCoeff, [[0, 12, 3, 15], [4, 8, 7, 11], [1, 13, 2, 14], [5, 9, 6, 10]]
    )


def strPost4x4Stage2Split_alternate(iCoeff):
    (
        p0m96,
        p0m32,
        p0p32,
        p0p96,
        p0m80,
        p0m16,
        p0p48,
        p0p112,
        p1m128,
        p1m64,
        p1p0,
        p1p64,
        p1m112,
        p1m48,
        p1p16,
        p1p80,
    ) = iCoeff

    p0m96, p0p96, p1m112, p1p80 = strDCT2x2dn([p0m96, p0p96, p1m112, p1p80])
    p0m32, p0p32, p1m48, p1p16 = strDCT2x2dn([p0m32, p0p32, p1m48, p1p16])
    p0m80, p0p112, p1m128, p1p64 = strDCT2x2dn([p0m80, p0p112, p1m128, p1p64])
    p0m16, p0p48, p1m64, p1p0 = strDCT2x2dn([p0m16, p0p48, p1m64, p1p0])

    p1p0, p1p64, p1p16, p1p80 = invOddOddPost([p1p0, p1p64, p1p16, p1p80])

    p0p48, p0p32 = irotate1(p0p48, p0p32)
    p0p112, p0p96 = irotate1(p0p112, p0p96)
    p1m64, p1m128 = irotate1(p1m64, p1m128)
    p1m48, p1m112 = irotate1(p1m48, p1m112)

    p0m96, p1p80 = strHSTdec1_alternate(p0m96, p1p80)
    p0m32, p1p16 = strHSTdec1_alternate(p0m32, p1p16)
    p0m80, p1p64 = strHSTdec1_alternate(p0m80, p1p64)
    p0m16, p1p0 = strHSTdec1_alternate(p0m16, p1p0)

    p0m96, p1m112, p0p96, p1p80 = strHSTdec(p0m96, p1m112, p0p96, p1p80)
    p0m32, p1m48, p0p32, p1p16 = strHSTdec(p0m32, p1m48, p0p32, p1p16)
    p0m80, p1m128, p0p112, p1p64 = strHSTdec(p0m80, p1m128, p0p112, p1p64)
    p0m16, p1m64, p0p48, p1p0 = strHSTdec(p0m16, p1m64, p0p48, p1p0)

    return [
        p0m96,
        p0m32,
        p0p32,
        p0p96,
        p0m80,
        p0m16,
        p0p48,
        p0p112,
        p1m128,
        p1m64,
        p1p0,
        p1p64,
        p1m112,
        p1m48,
        p1p16,
        p1p80,
    ]


def invOdd(iCoeff):
    a, b, c, d = iCoeff

    b += d
    a -= c
    d -= (b) >> 1
    c += (a + 1) >> 1

    a, b = irotate2(a, b)
    c, d = irotate2(c, d)

    c -= (b + 1) >> 1
    d = ((a + 1) >> 1) - d
    b += c
    a -= d

    return [a, b, c, d]


def invOddOdd(iCoeff):
    a, b, c, d = iCoeff

    d += a
    c -= b
    t1 = d >> 1
    a -= t1
    t2 = c >> 1
    b += t2

    a -= (b * 3 + 3) >> 3
    b += (a * 3 + 3) >> 2
    a -= (b * 3 + 4) >> 3

    b -= t2
    a += t1
    c += b
    d -= a

    return [a, -b, -c, d]


def irotate1(a, b):
    a -= (b + 1) >> 1
    b += (a + 1) >> 1
    return [a, b]


def irotate2(a, b):
    a -= (b * 3 + 4) >> 3
    b += (a * 3 + 4) >> 3
    return [a, b]


def fourbutterfly(iCoeff, order):
    for o in order:
        iCoeff[o[0]], iCoeff[o[1]], iCoeff[o[2]], iCoeff[o[3]] = strDCT2x2dn(
            [iCoeff[o[0]], iCoeff[o[1]], iCoeff[o[2]], iCoeff[o[3]]]
        )

    return iCoeff


def strDCT2x2up(iCoeff):
    a, b, C, d = iCoeff

    a += d
    b -= C
    t = (a - b + 1) >> 1
    c = t - d
    d = t - C
    a -= d
    b += c

    return [a, b, c, d]


def strDCT2x2dn(iCoeff):
    a, b, C, d = iCoeff

    a += d
    b -= C
    t = (a - b) >> 1
    c = t - d
    d = t - C
    a -= d
    b += c

    return (a, b, c, d)


def invOddOddPost(iCoeff):
    a, b, c, d = iCoeff

    d += a
    c -= b
    t1 = d >> 1
    a -= t1
    t2 = c >> 1
    b += t2

    a -= (b * 3 + 6) >> 3
    b += (a * 3 + 2) >> 2
    a -= (b * 3 + 4) >> 3

    b -= t2
    a += t1
    c += b
    d -= a

    return [a, b, c, d]


def strHSTdec1_alternate(a, d):
    a += d
    d = (a >> 1) - d
    a += (d * 3 + 0) >> 3
    d += (a * 3 + 0) >> 4

    d += a >> 7
    d -= a >> 10

    return [a, d]


def strHSTdec(a, b, c, d):
    b -= c
    a += (d * 3 + 4) >> 3

    d -= b >> 1
    c = ((a - b) >> 1) - c

    return [a - c, b + d, d, c]


def OverlapPostFilter4x4(iCoeff):
    iCoeff[0], iCoeff[3], iCoeff[12], iCoeff[15] = T2x2h(
        [iCoeff[0], iCoeff[3], iCoeff[12], iCoeff[15]], 0
    )
    iCoeff[1], iCoeff[2], iCoeff[13], iCoeff[14] = T2x2h(
        [iCoeff[1], iCoeff[2], iCoeff[13], iCoeff[14]], 0
    )
    iCoeff[4], iCoeff[7], iCoeff[8], iCoeff[11] = T2x2h(
        [iCoeff[4], iCoeff[7], iCoeff[8], iCoeff[11]], 0
    )
    iCoeff[5], iCoeff[6], iCoeff[9], iCoeff[10] = T2x2h(
        [iCoeff[5], iCoeff[6], iCoeff[9], iCoeff[10]], 0
    )

    iCoeff[13], iCoeff[12] = InvRotate(iCoeff[13], iCoeff[12])
    iCoeff[9], iCoeff[8] = InvRotate(iCoeff[9], iCoeff[8])
    iCoeff[7], iCoeff[3] = InvRotate(iCoeff[7], iCoeff[3])
    iCoeff[6], iCoeff[2] = InvRotate(iCoeff[6], iCoeff[2])

    iCoeff[10], iCoeff[11], iCoeff[14], iCoeff[15] = InvToddoddPOST(
        [iCoeff[10], iCoeff[11], iCoeff[14], iCoeff[15]]
    )

    iCoeff[0], iCoeff[15] = InvScale(iCoeff[0], iCoeff[15])
    iCoeff[1], iCoeff[14] = InvScale(iCoeff[1], iCoeff[14])
    iCoeff[4], iCoeff[11] = InvScale(iCoeff[4], iCoeff[11])
    iCoeff[5], iCoeff[10] = InvScale(iCoeff[5], iCoeff[10])

    iCoeff[0], iCoeff[3], iCoeff[12], iCoeff[15] = T2x2hPOST(
        [iCoeff[0], iCoeff[3], iCoeff[12], iCoeff[15]]
    )
    iCoeff[1], iCoeff[2], iCoeff[13], iCoeff[14] = T2x2hPOST(
        [iCoeff[1], iCoeff[2], iCoeff[13], iCoeff[14]]
    )
    iCoeff[4], iCoeff[7], iCoeff[8], iCoeff[11] = T2x2hPOST(
        [iCoeff[4], iCoeff[7], iCoeff[8], iCoeff[11]]
    )
    iCoeff[5], iCoeff[6], iCoeff[9], iCoeff[10] = T2x2hPOST(
        [iCoeff[5], iCoeff[6], iCoeff[9], iCoeff[10]]
    )
    return iCoeff


def T2x2h(iCoeff, valRound):
    iCoeff[0] += iCoeff[3]
    iCoeff[1] -= iCoeff[2]
    valT1 = (iCoeff[0] - iCoeff[1] + valRound) >> 1
    valT2 = iCoeff[2]
    iCoeff[2] = valT1 - iCoeff[3]
    iCoeff[3] = valT1 - valT2
    iCoeff[0] -= iCoeff[3]
    iCoeff[1] += iCoeff[2]
    return iCoeff


def T2x2hPOST(iCoeff):
    iCoeff[1] -= iCoeff[2]
    iCoeff[0] += (iCoeff[3] * 3 + 4) >> 3
    iCoeff[3] -= iCoeff[1] >> 1
    iCoeff[2] = ((iCoeff[0] - iCoeff[1]) >> 1) - iCoeff[2]
    iCoeff[2], iCoeff[3] = (iCoeff[3], iCoeff[2])
    iCoeff[0] -= iCoeff[3]
    iCoeff[1] += iCoeff[2]
    return iCoeff


def OverlapPostFilter4(iCoeff):
    iCoeff[0] += iCoeff[3]
    iCoeff[1] += iCoeff[2]
    iCoeff[3] -= (iCoeff[0] + 1) >> 1
    iCoeff[2] -= (iCoeff[1] + 1) >> 1
    iCoeff[0], iCoeff[3] = InvScale(iCoeff[0], iCoeff[3])
    iCoeff[1], iCoeff[2] = InvScale(iCoeff[1], iCoeff[2])
    iCoeff[0] += (iCoeff[3] * 3 + 4) >> 3
    iCoeff[1] += (iCoeff[2] * 3 + 4) >> 3
    iCoeff[3] -= iCoeff[0] >> 1
    iCoeff[2] -= iCoeff[1] >> 1
    iCoeff[0] += iCoeff[3]
    iCoeff[1] += iCoeff[2]
    iCoeff[3] = -iCoeff[3]
    iCoeff[2] = -iCoeff[2]
    iCoeff[2], iCoeff[3] = InvRotate(iCoeff[2], iCoeff[3])
    iCoeff[3] += (iCoeff[0] + 1) >> 1
    iCoeff[2] += (iCoeff[1] + 1) >> 1
    iCoeff[0] -= iCoeff[3]
    iCoeff[1] -= iCoeff[2]
    return iCoeff


def InvScale(iCoeff0, iCoeff1):
    iCoeff0 += iCoeff1
    iCoeff1 = (iCoeff0 >> 1) - iCoeff1
    iCoeff0 += (iCoeff1 * 3 + 0) >> 3
    iCoeff1 += (iCoeff0 * 3 + 0) >> 4
    iCoeff1 += iCoeff0 >> 7
    iCoeff1 -= iCoeff0 >> 10
    return (iCoeff0, iCoeff1)


def InvRotate(iCoeff0, iCoeff1):
    iCoeff0 -= (iCoeff1 + 1) >> 1
    iCoeff1 += (iCoeff0 + 1) >> 1
    return (iCoeff0, iCoeff1)


def InvToddoddPOST(iCoeff):
    iCoeff[3] += iCoeff[0]
    iCoeff[2] -= iCoeff[1]
    valT1 = iCoeff[3] >> 1
    valT2 = iCoeff[2] >> 1
    iCoeff[0] -= valT1
    iCoeff[1] += valT2
    iCoeff[0] -= (iCoeff[1] * 3 + 6) >> 3
    iCoeff[1] += (iCoeff[0] * 3 + 2) >> 2
    iCoeff[0] -= (iCoeff[1] * 3 + 4) >> 3
    iCoeff[1] -= valT2
    iCoeff[0] += valT1
    iCoeff[2] += iCoeff[1]
    iCoeff[3] -= iCoeff[0]
    return iCoeff
