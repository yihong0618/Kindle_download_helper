#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# kgenpids.py
# Copyright © 2008-2020 Apprentice Harper et al.

__license__ = "GPL v3"
__version__ = "3.0"

import binascii
import hashlib
import traceback
from struct import pack

global charMap1
global charMap3
global charMap4


charMap1 = b"n5Pr6St7Uv8Wx9YzAb0Cd1Ef2Gh3Jk4M"
charMap3 = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
charMap4 = b"ABCDEFGHIJKLMNPQRSTUVWXYZ123456789"


# crypto digestroutines
def MD5(message):
    ctx = hashlib.md5()
    ctx.update(message)
    return ctx.digest()


def SHA1(message):
    ctx = hashlib.sha1()
    ctx.update(message)
    return ctx.digest()


# Encode the bytes in data with the characters in map
# data and map should be byte arrays
def encode(data, map):
    result = b""
    for char in data:
        value = char
        Q = (value ^ 0x80) // len(map)
        R = value % len(map)
        result += bytes([map[Q]])
        result += bytes([map[R]])
    return result


# Hash the bytes in data and then encode the digest with the characters in map
def encode_hash(data, map):
    return encode(MD5(data), map)


# Returns two bit at offset from a bit field
def getTwoBitsFromBitField(bitField, offset):
    byteNumber = offset // 4
    bitPosition = 6 - 2 * (offset % 4)
    return bitField[byteNumber] >> bitPosition & 3


# Returns the six bits at offset from a bit field
def getSixBitsFromBitField(bitField, offset):
    offset *= 3
    value = (
        (getTwoBitsFromBitField(bitField, offset) << 4)
        + (getTwoBitsFromBitField(bitField, offset + 1) << 2)
        + getTwoBitsFromBitField(bitField, offset + 2)
    )
    return value


# 8 bits to six bits encoding from hash to generate PID string
def encodePID(hash):
    global charMap3
    PID = b""
    for position in range(0, 8):
        PID += bytes([charMap3[getSixBitsFromBitField(hash, position)]])
    return PID


# Encryption table used to generate the device PID
def generatePidEncryptionTable():
    table = []
    for counter1 in range(0, 0x100):
        value = counter1
        for counter2 in range(0, 8):
            if value & 1 == 0:
                value = value >> 1
            else:
                value = value >> 1
                value = value ^ 0xEDB88320
        table.append(value)
    return table


# Seed value used to generate the device PID
def generatePidSeed(table, dsn):
    value = 0
    for counter in range(0, 4):
        index = (dsn[counter] ^ value) & 0xFF
        value = (value >> 8) ^ table[index]
    return value


# Generate the device PID
def generatedevice_pid(table, dsn, nbRoll):
    global charMap4
    seed = generatePidSeed(table, dsn)
    pidAscii = b""
    pid = [
        (seed >> 24) & 0xFF,
        (seed >> 16) & 0xFF,
        (seed >> 8) & 0xFF,
        (seed) & 0xFF,
        (seed >> 24) & 0xFF,
        (seed >> 16) & 0xFF,
        (seed >> 8) & 0xFF,
        (seed) & 0xFF,
    ]
    index = 0
    for counter in range(0, nbRoll):
        pid[index] = pid[index] ^ dsn[counter]
        index = (index + 1) % 8
    for counter in range(0, 8):
        index = ((((pid[counter] >> 5) & 3) ^ pid[counter]) & 0x1F) + (
            pid[counter] >> 7
        )
        pidAscii += bytes([charMap4[index]])
    return pidAscii


def crc32(s):
    return (~binascii.crc32(s, -1)) & 0xFFFFFFFF


# convert from 8 digit PID to 10 digit PID with checksum
def check_sum_pid(s):
    global charMap4
    crc = crc32(s)
    crc = crc ^ (crc >> 16)
    res = s
    l = len(charMap4)
    for i in (0, 1):
        b = crc & 0xFF
        pos = (b // l) ^ (b % l)
        res += bytes([charMap4[pos % l]])
        crc >>= 8
    return res


# old kindle serial number to fixed pid
def pid_from_serial(s, l):
    global charMap4
    crc = crc32(s)
    arr1 = [0] * l
    for i in range(len(s)):
        arr1[i % l] ^= s[i]
    crc_bytes = [crc >> 24 & 0xFF, crc >> 16 & 0xFF, crc >> 8 & 0xFF, crc & 0xFF]
    for i in range(l):
        arr1[i] ^= crc_bytes[i & 3]
    pid = b""
    for i in range(l):
        b = arr1[i] & 0xFF
        pid += bytes([charMap4[(b >> 7) + ((b >> 5 & 3) ^ (b & 0x1F))]])
    return pid


# Parse the EXTH header records and use the Kindle serial number to calculate the book pid.
def get_kindle_pids(rec209, token, serialnum):
    if isinstance(serialnum, str):
        serialnum = serialnum.encode("utf-8")

    if rec209 is None:
        return [serialnum]

    pids = []

    # Compute book PID
    pid_hash = SHA1(serialnum + rec209 + token)
    book_pid = encodePID(pid_hash)
    book_pid = check_sum_pid(book_pid)
    pids.append(book_pid)

    # compute fixed pid for old pre 2.5 firmware update pid as well
    kindle_pid = pid_from_serial(serialnum, 7) + b"*"
    kindle_pid = check_sum_pid(kindle_pid)
    pids.append(kindle_pid)

    return pids


# parse the Kindleinfo file to calculate the book pid.
keynames = [
    "kindle.account.tokens",
    "kindle.cookie.item",
    "eulaVersionAccepted",
    "login_date",
    "kindle.token.item",
    "login",
    "kindle.key.item",
    "kindle.name.info",
    "kindle.device.info",
    "MazamaRandomNumber",
]


def get_k4_pids(rec209, token, kindleDatabase):
    global charMap1
    pids = []

    try:
        # Get the kindle account token, if present
        kindle_account_token = bytearray.fromhex(
            (kindleDatabase[1])["kindle.account.tokens"]
        )

    except KeyError:
        kindle_account_token = b""
        pass

    try:
        # Get the DSN token, if present
        DSN = bytearray.fromhex((kindleDatabase[1])["DSN"])
        print("Got DSN key from database {0}".format(kindleDatabase[0]))
    except KeyError:
        # See if we have the info to generate the DSN
        try:
            # Get the Mazama Random number
            MazamaRandomNumber = bytearray.fromhex(
                (kindleDatabase[1])["MazamaRandomNumber"]
            )
            # print "Got MazamaRandomNumber from database {0}".format(kindleDatabase[0])

            try:
                # Get the SerialNumber token, if present
                IDString = bytearray.fromhex((kindleDatabase[1])["SerialNumber"])
                print("Got SerialNumber from database {0}".format(kindleDatabase[0]))
            except KeyError:
                # Get the IDString we added
                IDString = bytearray.fromhex((kindleDatabase[1])["IDString"])

            try:
                # Get the UsernameHash token, if present
                encodedUsername = bytearray.fromhex((kindleDatabase[1])["UsernameHash"])
                print("Got UsernameHash from database {0}".format(kindleDatabase[0]))
            except KeyError:
                # Get the UserName we added
                UserName = bytearray.fromhex((kindleDatabase[1])["UserName"])
                # encode it
                encodedUsername = encode_hash(UserName, charMap1)
                # print "encodedUsername",encodedUsername.encode('hex')
        except KeyError:
            print("Keys not found in the database {0}.".format(kindleDatabase[0]))
            return pids

        # Get the ID string used
        encodedIDString = encode_hash(IDString, charMap1)
        # print "encodedIDString",encodedIDString.encode('hex')

        # concat, hash and encode to calculate the DSN
        DSN = encode(
            SHA1(MazamaRandomNumber + encodedIDString + encodedUsername), charMap1
        )
        # print "DSN",DSN.encode('hex')
        pass

    if rec209 is None:
        pids.append(DSN + kindle_account_token)
        return pids

    # Compute the device PID (for which I can tell, is used for nothing).
    table = generatePidEncryptionTable()
    device_pid = generatedevice_pid(table, DSN, 4)
    device_pid = check_sum_pid(device_pid)
    pids.append(device_pid)

    # book pid
    pid_hash = SHA1(DSN + kindle_account_token + rec209 + token)
    book_pid = encodePID(pid_hash)
    book_pid = check_sum_pid(book_pid)
    pids.append(book_pid)

    # variant 1
    pid_hash = SHA1(kindle_account_token + rec209 + token)
    book_pid = encodePID(pid_hash)
    book_pid = check_sum_pid(book_pid)
    pids.append(book_pid)

    # variant 2
    pid_hash = SHA1(DSN + rec209 + token)
    book_pid = encodePID(pid_hash)
    book_pid = check_sum_pid(book_pid)
    pids.append(book_pid)

    return pids


def get_pid_list(md1, md2, serials=[], kDatabases=[]):
    pidlst = []

    if kDatabases is None:
        kDatabases = []
    if serials is None:
        serials = []

    for kDatabase in kDatabases:
        try:
            pidlst.extend(map(bytes, get_k4_pids(md1, md2, kDatabase)))
        except Exception as e:
            print(
                "Error getting PIDs from database {0}: {1}".format(
                    kDatabase[0], e.args[0]
                )
            )
            traceback.print_exc()

    for serialnum in serials:
        try:
            pidlst.extend(map(bytes, get_kindle_pids(md1, md2, serialnum)))
        except Exception as e:
            print(
                "Error getting PIDs from serial number {0}: {1}".format(
                    serialnum, e.args[0]
                )
            )
            traceback.print_exc()
    return pidlst
