"""
This code is copied from https://github.com/apprenticeharper/DeDRM_tools and
recode to use amazon.ion instead of the DeDRM BinaryIonParser class. Added
support for converting a metadata file from DRMION format.
"""

import hashlib
import hmac
import os
import shutil
import zipfile
from io import BytesIO

from amazon.ion import simpleion
from amazon.ion.core import IonType
from amazon.ion.symbols import SymbolTableCatalog, shared_symbol_table

from .aescipher import aes_cbc_decrypt

pythonista_lzma = False
import lzma

SYM_NAMES = [
    "com.amazon.drm.Envelope@1.0",
    "com.amazon.drm.EnvelopeMetadata@1.0",
    "size",
    "page_size",
    "encryption_key",
    "encryption_transformation",
    "encryption_voucher",
    "signing_key",
    "signing_algorithm",
    "signing_voucher",
    "com.amazon.drm.EncryptedPage@1.0",
    "cipher_text",
    "cipher_iv",
    "com.amazon.drm.Signature@1.0",
    "data",
    "com.amazon.drm.EnvelopeIndexTable@1.0",
    "length",
    "offset",
    "algorithm",
    "encoded",
    "encryption_algorithm",
    "hashing_algorithm",
    "expires",
    "format",
    "id",
    "lock_parameters",
    "strategy",
    "com.amazon.drm.Key@1.0",
    "com.amazon.drm.KeySet@1.0",
    "com.amazon.drm.PIDv3@1.0",
    "com.amazon.drm.PlainTextPage@1.0",
    "com.amazon.drm.PlainText@1.0",
    "com.amazon.drm.PrivateKey@1.0",
    "com.amazon.drm.PublicKey@1.0",
    "com.amazon.drm.SecretKey@1.0",
    "com.amazon.drm.Voucher@1.0",
    "public_key",
    "private_key",
    "com.amazon.drm.KeyPair@1.0",
    "com.amazon.drm.ProtectedData@1.0",
    "doctype",
    "com.amazon.drm.EnvelopeIndexTableOffset@1.0",
    "enddoc",
    "license_type",
    "license",
    "watermark",
    "key",
    "value",
    "com.amazon.drm.License@1.0",
    "category",
    "metadata",
    "categorized_metadata",
    "com.amazon.drm.CategorizedMetadata@1.0",
    "com.amazon.drm.VoucherEnvelope@1.0",
    "mac",
    "voucher",
    "com.amazon.drm.ProtectedData@2.0",
    "com.amazon.drm.Envelope@2.0",
    "com.amazon.drm.EnvelopeMetadata@2.0",
    "com.amazon.drm.EncryptedPage@2.0",
    "com.amazon.drm.PlainText@2.0",
    "compression_algorithm",
    "com.amazon.drm.Compressed@1.0",
    "page_index_table",
    "com.amazon.drm.VoucherEnvelope@2.0",
    "com.amazon.drm.VoucherEnvelope@3.0",
]


# asserts must always raise exceptions for proper functioning
def _assert(test, msg="Exception"):
    if not test:
        raise Exception(msg)


def get_ion_parser(ion: bytes, single_value: bool = True, addprottable: bool = False):
    catalog = SymbolTableCatalog()
    if addprottable:
        table = shared_symbol_table("ProtectedData", 1, SYM_NAMES)
        catalog.register(table)

    return simpleion.loads(ion, catalog=catalog, single_value=single_value)


class DrmIonVoucher:
    envelope = None
    version = None
    voucher = None
    drmkey = None
    license_type = "Unknown"

    encalgorithm = ""
    enctransformation = ""
    hashalgorithm = ""

    lockparams = None

    ciphertext = b""
    cipheriv = b""
    secretkey = b""

    def __init__(self, voucherenv, dsn, secret):
        self.dsn, self.secret = dsn, secret
        self.lockparams = []
        self.envelope = get_ion_parser(voucherenv, addprottable=True)

    def decrypt_voucher(self):
        shared = (
            "PIDv3" + self.encalgorithm + self.enctransformation + self.hashalgorithm
        )

        self.lockparams.sort()
        for param in self.lockparams:
            if param == "ACCOUNT_SECRET":
                shared += param + self.secret
            elif param == "CLIENT_ID":
                shared += param + self.dsn
            else:
                _assert(False, "Unknown lock parameter: %s" % param)

        sharedsecret = shared.encode("ASCII")
        key = hmac.new(sharedsecret, b"PIDv3", digestmod=hashlib.sha256).digest()
        b = aes_cbc_decrypt(key[:32], self.cipheriv[:16], self.ciphertext)

        self.drmkey = get_ion_parser(b, addprottable=True)
        _assert(
            len(self.drmkey) > 0
            and self.drmkey.ion_type == IonType.LIST
            and self.drmkey.ion_annotations[0].text == "com.amazon.drm.KeySet@1.0",
            "Expected KeySet, got %s" % self.drmkey.ion_annotations[0].text,
        )

        for item in self.drmkey:
            if item.ion_annotations[0].text != "com.amazon.drm.SecretKey@1.0":
                continue

            _assert(
                item["algorithm"] == "AES",
                "Unknown cipher algorithm: %s" % item["algorithm"],
            )
            _assert(item["format"] == "RAW", "Unknown key format: %s" % item["format"])

            self.secretkey = item["encoded"]

    def parse(self):
        _assert(len(self.envelope) > 0, "Envelope is empty")
        _assert(
            self.envelope.ion_type == IonType.STRUCT
            and self.envelope.ion_annotations[0].text.startswith(
                "com.amazon.drm.VoucherEnvelope@"
            ),
            "Unknown type encountered in envelope, expected VoucherEnvelope",
        )
        self.version = int(self.envelope.ion_annotations[0].text.split("@")[1][:-2])
        self.voucher = get_ion_parser(self.envelope["voucher"], addprottable=True)

        strategy_annotation_name = self.envelope["strategy"].ion_annotations[0].text
        _assert(
            strategy_annotation_name == "com.amazon.drm.PIDv3@1.0",
            "Unknown strategy: %s" % strategy_annotation_name,
        )

        strategy = self.envelope["strategy"]
        self.encalgorithm = strategy["encryption_algorithm"]
        self.enctransformation = strategy["encryption_transformation"]
        self.hashalgorithm = strategy["hashing_algorithm"]
        lockparams = strategy["lock_parameters"]
        _assert(
            lockparams.ion_type == IonType.LIST,
            "Expected string list for lock_parameters",
        )
        self.lockparams.extend(lockparams)

        self.parse_voucher()

    def parse_voucher(self):
        _assert(len(self.voucher) > 0, "Voucher is empty")
        _assert(
            self.voucher.ion_type == IonType.STRUCT
            and self.voucher.ion_annotations[0].text == "com.amazon.drm.Voucher@1.0",
            "Unknown type, expected Voucher",
        )

        self.cipheriv = self.voucher["cipher_iv"]
        self.ciphertext = self.voucher["cipher_text"]

        _assert(
            self.voucher["license"].ion_annotations[0].text
            == "com.amazon.drm.License@1.0",
            "Unknown license: %s" % self.voucher["license"].ion_annotations[0].text,
        )
        self.license_type = self.voucher["license"]["license_type"]

    def get_license_type(self):
        return self.license_type


class DrmIon:
    ion = None
    voucher = None
    vouchername = ""
    key = b""
    onvoucherrequired = None

    def __init__(self, ionstream, onvoucherrequired):
        self.ion = get_ion_parser(ionstream, addprottable=True, single_value=False)
        self.onvoucherrequired = onvoucherrequired

    def parse(self, outpages):
        _assert(len(self.ion) > 0, "DRMION envelope is empty")
        _assert(
            self.ion[0].ion_type == IonType.SYMBOL
            and self.ion[0].ion_annotations[0].text == "doctype",
            "Expected doctype symbol",
        )
        _assert(
            self.ion[1].ion_type == IonType.LIST
            and self.ion[1].ion_annotations[0].text
            in ["com.amazon.drm.Envelope@1.0", "com.amazon.drm.Envelope@2.0"],
            "Unknown type encountered in DRMION envelope, expected Envelope, got %s"
            % self.ion[1].ion_annotations[0].text,
        )

        for ion_list in self.ion:
            if not ion_list.ion_annotations[0].text in [
                "com.amazon.drm.Envelope@1.0",
                "com.amazon.drm.Envelope@2.0",
            ]:
                continue

            for item in ion_list:
                if item.ion_annotations[0].text in [
                    "com.amazon.drm.EnvelopeMetadata@1.0",
                    "com.amazon.drm.EnvelopeMetadata@2.0",
                ]:
                    if item.get("encryption_voucher") is None:
                        continue

                    if self.vouchername == "":
                        self.vouchername = item["encryption_voucher"]
                        self.voucher = self.onvoucherrequired(self.vouchername)
                        self.key = self.voucher.secretkey
                        _assert(
                            self.key is not None,
                            "Unable to obtain secret key from voucher",
                        )
                    else:
                        _assert(
                            self.vouchername == item["encryption_voucher"],
                            "Unexpected: Different vouchers required for same file?",
                        )

                elif item.ion_annotations[0].text in [
                    "com.amazon.drm.EncryptedPage@1.0",
                    "com.amazon.drm.EncryptedPage@2.0",
                ]:
                    decompress = False
                    decrypt = True
                    if item["cipher_text"].ion_annotations:
                        if (
                            item["cipher_text"].ion_annotations[0].text
                            == "com.amazon.drm.Compressed@1.0"
                        ):
                            decompress = True
                    ct = item["cipher_text"]
                    civ = item["cipher_iv"]
                    if ct is not None and civ is not None:
                        self.processpage(ct, civ, outpages, decompress, decrypt)

                elif item.ion_annotations[0].text in [
                    "com.amazon.drm.PlainText@1.0",
                    "com.amazon.drm.PlainText@2.0",
                ]:
                    decompress = False
                    decrypt = False
                    if (
                        item["data"].ion_annotations[0].text
                        == "com.amazon.drm.Compressed@1.0"
                    ):
                        decompress = True
                    self.processpage(item["data"], None, outpages, decompress, decrypt)

    def processpage(self, ct, civ, outpages, decompress, decrypt):
        if decrypt:
            msg = aes_cbc_decrypt(self.key[:16], civ[:16], ct)
        else:
            msg = ct

        if not decompress:
            outpages.write(msg)
            return

        _assert(msg[0] == 0, "LZMA UseFilter not supported")

        if pythonista_lzma:
            segment = lzma.decompress(msg[1:])
            msg = b""
            outpages.write(segment.getvalue())
            return 0

        decomp = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        while not decomp.eof:
            segment = decomp.decompress(msg[1:])
            msg = b""  # Contents were internally buffered after the first call
            outpages.write(segment)


class KFXZipBook:
    def __init__(self, infile, dsn):
        self.infile = infile
        self.dsn = dsn
        self.voucher = None
        self.decrypted = {}

    def getPIDMetaInfo(self):
        return (None, None)

    def processBook(self):
        with zipfile.ZipFile(self.infile, "r") as zf:
            for filename in zf.namelist():
                with zf.open(filename) as fh:
                    data = fh.read(8)
                    if data != b"\xeaDRMION\xee":
                        continue
                    data += fh.read()
                    if self.voucher is None:
                        self.decrypt_voucher()
                    print("Decrypting KFX DRMION: {0}".format(filename))
                    outfile = BytesIO()
                    DrmIon(data[8:-8], lambda name: self.voucher).parse(outfile)
                    outfile = outfile.getvalue()
                    if len(outfile) > 0:
                        self.decrypted[filename] = outfile
                    else:
                        print(
                            "Decrypting KFX DRMION {0} results in a length of Zero. Skip file.".format(
                                filename
                            )
                        )

        if not self.decrypted:
            print("The .kfx-zip archive does not contain an encrypted DRMION file")

    def decrypt_voucher(self):
        with zipfile.ZipFile(self.infile, "r") as zf:
            for info in zf.infolist():
                with zf.open(info.filename) as fh:
                    data = fh.read(4)
                    if data != b"\xe0\x01\x00\xea":
                        continue

                    data += fh.read()
                    if b"ProtectedData" in data:
                        break  # found DRM voucher
            else:
                raise Exception(
                    "The .kfx-zip archive contains an encrypted DRMION file without a DRM voucher"
                )

        print("Decrypting KFX DRM voucher: {0}".format(info.filename))

        for pid in [""] + [self.dsn]:
            for dsn_len, secret_len in [
                (0, 0),
                (16, 0),
                (16, 40),
                (32, 40),
                (40, 0),
                (40, 40),
            ]:
                if len(pid) == dsn_len + secret_len:
                    break  # split pid into DSN and account secret
                else:
                    continue

            try:
                voucher = DrmIonVoucher(data, pid[:dsn_len], pid[dsn_len:])
                voucher.parse()
                voucher.decrypt_voucher()
                break
            except:
                pass
        else:
            raise Exception("Failed to decrypt KFX DRM voucher with any key")

        print("KFX DRM voucher successfully decrypted")

        license_type = voucher.get_license_type()
        if license_type != "Purchase":
            raise Exception(
                (
                    "This book is licensed as {0}. "
                    "These tools are intended for use on purchased books."
                ).format(license_type)
            )

        self.voucher = voucher

    def getBookTitle(self):
        return os.path.splitext(os.path.split(self.infile)[1])[0]

    def getBookExtension(self):
        return ".kfx-zip"

    def getBookType(self):
        return "KFX-ZIP"

    def cleanup(self):
        pass

    def getFile(self, outpath):
        if not self.decrypted:
            shutil.copyfile(self.infile, outpath)
        else:
            with zipfile.ZipFile(self.infile, "r") as zif:
                with zipfile.ZipFile(outpath, "w") as zof:
                    for info in zif.infolist():
                        zof.writestr(
                            info,
                            self.decrypted.get(info.filename, zif.read(info.filename)),
                        )
