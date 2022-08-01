""""
Most of code from DeDRM_tools I changed some.
Because most of us China download books are .azw3 or .azw
And its mobi, so to make `kindle_download_helper` easy to use
I dedrm all the downloads here
And I think its only for China now, if you are not using amazon.cn
Please find another way to dedrm, this repo will not answer any issue of it
Or you can fork it and change the code.
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# mobidedrm.py
# Copyright © 2008 The Dark Reverser
# Portions © 2008–2020 Apprentice Harper et al.


__license__ = "GPL v3"
__version__ = "1.0"

# This is a python script. You need a Python interpreter to run it.
# For example, ActiveState Python, which exists for windows.


import struct
import binascii


class DrmException(Exception):
    pass


# Implementation of Pukall Cipher 1
def PC1(key, src, decryption=True):
    # if we can get it from alfcrypto, use that
    # use slow python version, since Pukall_Cipher didn't load
    sum1 = 0
    sum2 = 0
    keyXorVal = 0
    if len(key) != 16:
        DrmException("PC1: Bad key length")
    wkey = []
    for i in range(8):
        wkey.append(key[i * 2] << 8 | key[i * 2 + 1])
    dst = b""
    for i in range(len(src)):
        temp1 = 0
        byteXorVal = 0
        for j in range(8):
            temp1 ^= wkey[j]
            sum2 = (sum2 + j) * 20021 + sum1
            sum1 = (temp1 * 346) & 0xFFFF
            sum2 = (sum2 + sum1) & 0xFFFF
            temp1 = (temp1 * 20021 + 1) & 0xFFFF
            byteXorVal ^= temp1 ^ sum2
        curByte = src[i]
        if not decryption:
            keyXorVal = curByte * 257
        curByte = ((curByte ^ (byteXorVal >> 8)) ^ byteXorVal) & 0xFF
        if decryption:
            keyXorVal = curByte * 257
        for j in range(8):
            wkey[j] ^= keyXorVal
        dst += bytes([curByte])
    return dst


# accepts unicode returns unicode
def check_sum_pid(s):
    letters = "ABCDEFGHIJKLMNPQRSTUVWXYZ123456789"
    crc = (~binascii.crc32(s.encode("utf-8"), -1)) & 0xFFFFFFFF
    crc = crc ^ (crc >> 16)
    res = s
    l = len(letters)
    for i in (0, 1):
        b = crc & 0xFF
        pos = (b // l) ^ (b % l)
        res += letters[pos % l]
        crc >>= 8
    return res


# expects bytearray
def get_size_of_trailing_data_entries(ptr, size, flags):
    def get_size_of_trailing_data_entry(ptr, size):
        bitpos, result = 0, 0
        if size <= 0:
            return result
        while True:
            v = ptr[size - 1]
            result |= (v & 0x7F) << bitpos
            bitpos += 7
            size -= 1
            if (v & 0x80) != 0 or (bitpos >= 28) or (size == 0):
                return result

    num = 0
    testflags = flags >> 1
    while testflags:
        if testflags & 1:
            num += get_size_of_trailing_data_entry(ptr, size - num)
        testflags >>= 1
    # Check the low bit to see if there's multibyte data present.
    # if multibyte data is included in the encryped data, we'll
    # have already cleared this flag.
    if flags & 1:
        num += (ptr[size - num - 1] & 0x3) + 1
    return num


class MobiBook:
    def __init__(self, infile):
        print(
            "MobiDeDrm v{0:s}.\nCopyright © 2008-2020 The Dark Reverser, Apprentice Harper et al.".format(
                __version__
            )
        )
        # initial sanity check on file
        with open(infile, "rb") as f:
            self.data_file = f.read()
        self.mobi_data = ""
        self.header = self.data_file[0:78]
        if (
            self.header[0x3C : 0x3C + 8] != b"BOOKMOBI"
            and self.header[0x3C : 0x3C + 8] != b"TEXtREAd"
        ):
            raise DrmException("Invalid file format")
        self.magic = self.header[0x3C : 0x3C + 8]
        self.crypto_type = -1

        # build up section offset and flag info
        (self.num_sections,) = struct.unpack(">H", self.header[76:78])
        self.sections = []
        for i in range(self.num_sections):
            offset, a1, a2, a3, a4 = struct.unpack(
                ">LBBBB", self.data_file[78 + i * 8 : 78 + i * 8 + 8]
            )
            flags, val = a1, a2 << 16 | a3 << 8 | a4
            self.sections.append((offset, flags, val))

        # parse information from section 0
        self.sect = self.load_section(0)
        (self.records,) = struct.unpack(">H", self.sect[0x8 : 0x8 + 2])
        (self.compression,) = struct.unpack(">H", self.sect[0x0 : 0x0 + 2])

        # det default values before PalmDoc test
        self.print_replica = False
        self.extra_data_flags = 0
        self.meta_array = {}
        self.mobi_length = 0
        self.mobi_codepage = 1252
        self.mobi_version = -1

        if self.magic == b"TEXtREAd":
            print("PalmDoc format book detected.")
            return

        (self.mobi_length,) = struct.unpack(">L", self.sect[0x14:0x18])
        (self.mobi_codepage,) = struct.unpack(">L", self.sect[0x1C:0x20])
        (self.mobi_version,) = struct.unpack(">L", self.sect[0x68:0x6C])
        # print "MOBI header version {0:d}, header length {1:d}".format(self.mobi_version, self.mobi_length)
        if (self.mobi_length >= 0xE4) and (self.mobi_version >= 5):
            (self.extra_data_flags,) = struct.unpack(">H", self.sect[0xF2:0xF4])
            # print "Extra Data Flags: {0:d}".format(self.extra_data_flags)
        if self.compression != 17480:
            # multibyte utf8 data is included in the encryption for PalmDoc compression
            # so clear that byte so that we leave it to be decrypted.
            self.extra_data_flags &= 0xFFFE

        # if exth region exists parse it for metadata array
        try:
            (exth_flag,) = struct.unpack(">L", self.sect[0x80:0x84])
            exth = b""
            if exth_flag & 0x40:
                exth = self.sect[16 + self.mobi_length :]
            if (len(exth) >= 12) and (exth[:4] == b"EXTH"):
                (nitems,) = struct.unpack(">I", exth[8:12])
                pos = 12
                for i in range(nitems):
                    type, size = struct.unpack(">II", exth[pos : pos + 8])
                    content = exth[pos + 8 : pos + size]
                    self.meta_array[type] = content
                    # reset the text to speech flag and clipping limit, if present
                    if type == 401 and size == 9:
                        # set clipping limit to 100%
                        self.patch_section(0, b"\144", 16 + self.mobi_length + pos + 8)
                    elif type == 404 and size == 9:
                        # make sure text to speech is enabled
                        self.patch_section(0, b"\0", 16 + self.mobi_length + pos + 8)
                    # print type, size, content, content.encode('hex')
                    pos += size
        except Exception as e:
            print("Cannot set meta_array: Error: {:s}".format(e.args[0]))

    def load_section(self, section):
        if section + 1 == self.num_sections:
            endoff = len(self.data_file)
        else:
            endoff = self.sections[section + 1][0]
        off = self.sections[section][0]
        return self.data_file[off:endoff]

    # returns unicode
    def get_book_title(self):
        codec_map = {
            1252: "windows-1252",
            65001: "utf-8",
        }
        title = b""
        codec = "windows-1252"
        if self.magic == b"BOOKMOBI":
            if 503 in self.meta_array:
                title = self.meta_array[503]
            else:
                toff, tlen = struct.unpack(">II", self.sect[0x54:0x5C])
                tend = toff + tlen
                title = self.sect[toff:tend]
            if self.mobi_codepage in codec_map.keys():
                codec = codec_map[self.mobi_codepage]
        if title == b"":
            title = self.header[:32]
            title = title.split(b"\0")[0]
        return title.decode(codec)

    def get_pid_meta_info(self):
        rec209 = b""
        token = b""
        if 209 in self.meta_array:
            rec209 = self.meta_array[209]
            data = rec209
            # The 209 data comes in five byte groups. Interpret the last four bytes
            # of each group as a big endian unsigned integer to get a key value
            # if that key exists in the meta_array, append its contents to the token
            for i in range(0, len(data), 5):
                (val,) = struct.unpack(">I", data[i + 1 : i + 5])
                sval = self.meta_array.get(val, b"")
                token += sval
        return rec209, token

    # new must be byte array
    def patch(self, off, new):
        self.data_file = self.data_file[:off] + new + self.data_file[off + len(new) :]

    # new must be byte array
    def patch_section(self, section, new, in_off=0):
        if section + 1 == self.num_sections:
            endoff = len(self.data_file)
        else:
            endoff = self.sections[section + 1][0]
        off = self.sections[section][0]
        assert off + in_off + len(new) <= endoff
        self.patch(off + in_off, new)

    # pids in pidlist must be unicode, returned key is byte array, pid is unicode
    def parse_drm(self, data, count, pidlist):
        found_key = None
        keyvec1 = b"\x72\x38\x33\xB0\xB4\xF2\xE3\xCA\xDF\x09\x01\xD6\xE2\xE0\x3F\x96"
        for pid in pidlist:
            bigpid = pid.encode("utf-8").ljust(16, b"\0")
            temp_key = PC1(keyvec1, bigpid, False)
            temp_key_sum = sum(temp_key) & 0xFF
            found_key = None
            for i in range(count):
                verification, size, type, cksum, cookie = struct.unpack(
                    ">LLLBxxx32s", data[i * 0x30 : i * 0x30 + 0x30]
                )
                if cksum == temp_key_sum:
                    cookie = PC1(temp_key, cookie)
                    ver, flags, finalkey, expiry, expiry2 = struct.unpack(
                        ">LL16sLL", cookie
                    )
                    if verification == ver and (flags & 0x1F) == 1:
                        found_key = finalkey
                        break
            if found_key != None:
                break
        if not found_key:
            # Then try the default encoding that doesn't require a PID
            pid = "00000000"
            temp_key = keyvec1
            temp_key_sum = sum(temp_key) & 0xFF
            for i in range(count):
                verification, size, type, cksum, cookie = struct.unpack(
                    ">LLLBxxx32s", data[i * 0x30 : i * 0x30 + 0x30]
                )
                if cksum == temp_key_sum:
                    cookie = PC1(temp_key, cookie)
                    ver, flags, finalkey, expiry, expiry2 = struct.unpack(
                        ">LL16sLL", cookie
                    )
                    if verification == ver:
                        found_key = finalkey
                        break
        return [found_key, pid]

    def make_drm_file(self, pid_list, outpath):
        self.process_book(pid_list)
        with open(outpath, "wb") as f:
            f.write(self.mobi_data)

    def get_book_extension(self):
        if self.print_replica:
            return ".azw4"
        if self.mobi_version >= 8:
            return ".azw3"
        return ".mobi"

    # pids in pidlist may be unicode or bytearrays or bytes
    def process_book(self, pidlist):
        (crypto_type,) = struct.unpack(">H", self.sect[0xC : 0xC + 2])
        print("Crypto Type is: {0:d}".format(crypto_type))
        self.crypto_type = crypto_type
        if crypto_type == 0:
            print("This book is not encrypted.")
            # we must still check for Print Replica
            self.print_replica = self.load_section(1)[0:4] == "%MOP"
            self.mobi_data = self.data_file
            return
        if crypto_type != 2 and crypto_type != 1:
            raise DrmException(
                "Cannot decode unknown Mobipocket encryption type {0:d}".format(
                    crypto_type
                )
            )
        if 406 in self.meta_array:
            data406 = self.meta_array[406]
            (val406,) = struct.unpack(">Q", data406)
            if val406 != 0:
                raise DrmException("Cannot decode library or rented ebooks.")

        goodpids = []
        # print("DEBUG ==== pidlist = ", pidlist)
        for pid in pidlist:
            if isinstance(pid, (bytearray, bytes)):
                pid = pid.decode("utf-8")
            if len(pid) == 10:
                if check_sum_pid(pid[0:-2]) != pid:
                    print(
                        "Warning: PID {0} has incorrect checksum, should have been {1}".format(
                            pid, check_sum_pid(pid[0:-2])
                        )
                    )
                goodpids.append(pid[0:-2])
            elif len(pid) == 8:
                goodpids.append(pid)
            else:
                print("Warning: PID {0} has wrong number of digits".format(pid))

        if self.crypto_type == 1:
            t1_keyvec = b"QDCVEPMU675RUBSZ"
            if self.magic == b"TEXtREAd":
                bookkey_data = self.sect[0x0E : 0x0E + 16]
            elif self.mobi_version < 0:
                bookkey_data = self.sect[0x90 : 0x90 + 16]
            else:
                bookkey_data = self.sect[self.mobi_length + 16 : self.mobi_length + 32]
            pid = "00000000"
            found_key = PC1(t1_keyvec, bookkey_data)
        else:
            # calculate the keys
            drm_ptr, drm_count, drm_size, drm_flags = struct.unpack(
                ">LLLL", self.sect[0xA8 : 0xA8 + 16]
            )
            if drm_count == 0:
                raise DrmException(
                    "Encryption not initialised. Must be opened with Mobipocket Reader first."
                )
            found_key, pid = self.parse_drm(
                self.sect[drm_ptr : drm_ptr + drm_size], drm_count, goodpids
            )
            if not found_key:
                raise DrmException(
                    "No key found in {0:d} PIDs tried.".format(len(goodpids))
                )
            # kill the drm keys
            self.patch_section(0, b"\0" * drm_size, drm_ptr)
            # kill the drm pointers
            self.patch_section(0, b"\xff" * 4 + b"\0" * 12, 0xA8)

        if pid == "00000000":
            print("File has default encryption, no specific key needed.")
        else:
            print("File is encoded with PID {0}.".format(check_sum_pid(pid)))

        # clear the crypto type
        self.patch_section(0, b"\0" * 2, 0xC)

        # decrypt sections
        print("Decrypting. Please wait . . .", end=" ")
        mobidataList = []
        mobidataList.append(self.data_file[: self.sections[1][0]])
        for i in range(1, self.records + 1):
            data = self.load_section(i)
            extra_size = get_size_of_trailing_data_entries(
                data, len(data), self.extra_data_flags
            )
            if i % 100 == 0:
                print(".", end=" ")
            # print "record %d, extra_size %d" %(i,extra_size)
            decoded_data = PC1(found_key, data[0 : len(data) - extra_size])
            if i == 1:
                self.print_replica = decoded_data[0:4] == "%MOP"
            mobidataList.append(decoded_data)
            if extra_size > 0:
                mobidataList.append(data[-extra_size:])
        if self.num_sections > self.records + 1:
            mobidataList.append(self.data_file[self.sections[self.records + 1][0] :])
        self.mobi_data = b"".join(mobidataList)
        print("done")
        return
