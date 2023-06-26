from __future__ import absolute_import, division, print_function, unicode_literals

import struct

from .message_logging import log

__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEBUG = False


class Deserializer(object):
    def __init__(self, data):
        self.buffer = data
        self.offset = 0
        self.bits_remaining = self.remainder = 0

    def extract(self, size=None, upto=None, advance=True, check_remaining=True):
        if check_remaining and self.bits_remaining:
            raise Exception(
                "Deserializer: unexpected %d bit remaining" % self.bits_remaining
            )

        if size is None:
            size = len(self) if upto is None else (upto - self.offset)

        data = self.buffer[self.offset : self.offset + size]

        if len(data) < size or size < 0:
            raise Exception(
                "Deserializer: Insufficient data (need %d bytes, have %d bytes)"
                % (size, len(data))
            )

        if advance:
            self.offset += size

        return data

    def unpack(self, fmt, name="", advance=True):
        if self.bits_remaining:
            raise Exception(
                "Deserializer: unexpected %d bit remaining" % self.bits_remaining
            )

        result = struct.unpack_from(fmt, self.buffer, self.offset)[0]

        if DEBUG:
            log.info("%d: unpack(%s)=%s %s" % (self.offset, fmt, repr(result), name))

        if advance:
            self.offset += struct.calcsize(fmt)

        return result

    def unpack_bits(self, size, name=""):
        while self.bits_remaining < size:
            self.remainder = (self.remainder << 8) + ord(
                self.extract(1, check_remaining=False)
            )
            self.bits_remaining += 8

        self.bits_remaining -= size
        value = self.remainder >> self.bits_remaining

        if value > (1 << size) - 1:
            raise Exception()

        self.remainder = self.remainder & (0xFF >> (8 - self.bits_remaining))

        if DEBUG:
            log.info(
                "%d: unpack_bits(%d)=%u (%s) %s"
                % (self.offset, size, value, ("{0:0%sb}" % size).format(value), name)
            )

        return value

    def unpack_flag(self, name=""):
        return self.unpack_bits(1, name) == 1

    def push_bit(self, value):
        self.remainder &= (value & 1) << self.bits_remaining
        self.bits_remaining += 1

    def check_bit_field(self, size, name, expected_values, name_table={}):
        def value_name(v):
            return name_table.get(v, "%d" % v)

        value = self.unpack_bits(size, name)

        if value not in expected_values:
            msg = "%s value %s is unsupported (only %s allowed)" % (
                name,
                value_name(value),
                ", ".join([value_name(ev) for ev in expected_values]),
            )
            raise Exception(msg)

        return value

    def huff(self, table, name):
        k = 1
        while k <= 0xFF:
            k = (k << 1) + self.unpack_bits(1, name)
            v = table.get(k)
            if v is not None:
                return v

        raise Exception("decode using huffman table failed")

    def discard_remainder_bits(self):
        self.bits_remaining = self.remainder = 0

    def __len__(self):
        return len(self.buffer) - self.offset


def bytes_to_separated_hex(data, sep=" "):
    return sep.join("%02x" % ord(data[i : i + 1]) for i in range(len(data)))
