from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import datetime
import decimal
import math
import re

from .message_logging import log
from .python_transition import IS_PYTHON2, bytes_to_hex
from .utilities import sha1, type_name

if IS_PYTHON2:
    from .python_transition import repr, str
else:
    long = int


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


LARGE_DATA_SIZE = 256
MAX_ASCII_DATA_SIZE = 10000


IonBool = bool
IonDecimal = decimal.Decimal
IonFloat = float
IonInt = int
IonList = list
IonNull = type(None)
IonString = str


def ion_type(value):
    t = type(value)
    if t in ION_TYPES:
        return t

    if isinstance(value, IonAnnotation):
        return IonAnnotation

    if isinstance(value, IonList) and not isinstance(value, IonSExp):
        return IonList

    if isinstance(value, long):
        return IonInt

    raise Exception("Data has non-Ion type %s: %s" % (type_name(value), repr(value)))


def isstring(value):
    return isinstance(value, str) and not isinstance(value, IonSymbol)


class IonAnnotation(object):
    def __init__(self, annotations, value):
        self.annotations = (
            annotations
            if isinstance(annotations, IonAnnots)
            else IonAnnots(annotations)
        )

        if isinstance(value, IonAnnotation):
            raise Exception("IonAnnotation cannot be annotated")

        self.value = value

    def __repr__(self):
        return "%s %s" % (repr(self.annotations), repr(self.value))

    def __str__(self):
        return repr(self.annotations)

    def is_single(self):
        return len(self.annotations) == 1

    def has_annotation(self, annotation):
        return annotation in self.annotations

    def is_annotation(self, annotation):
        return self.is_single() and self.annotations[0] == annotation

    def get_annotation(self):
        if not self.is_single():
            raise Exception(
                "get_annotation expected single annotation, found %s"
                % repr(self.annotations)
            )

        return self.annotations[0]

    def verify_annotation(self, annotation):
        if not self.is_annotation(annotation):
            raise Exception(
                "Expected annotation %s, found %s"
                % (repr(annotation), repr(self.annotations))
            )

        return self


class IonAnnots(tuple):
    def __new__(cls, annotations):
        annots = tuple.__new__(cls, annotations)

        if len(annots) == 0:
            raise Exception("IonAnnotation cannot be empty")

        for a in annots:
            if not isinstance(a, IonSymbol):
                raise Exception("IonAnnotation must be IonSymbol: %s" % repr(a))

        return annots

    def __repr__(self):
        return " ".join(["%s::" % repr(a) for a in self])


class IonBLOB(bytes):
    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, (IonBLOB, bytes)):
            raise Exception("IonBLOB __eq__: comparing with %s" % type_name(other))

        return bytes(self) == bytes(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        raise Exception("IonBLOB __lt__ not implemented")

    def __le__(self, other):
        raise Exception("IonBLOB __le__ not implemented")

    def __gt__(self, other):
        raise Exception("IonBLOB __gt__ not implemented")

    def __ge__(self, other):
        raise Exception("IonBLOB __ge__ not implemented")

    def __repr__(self):
        return "*** %d byte BLOB %s ***" % (len(self), bytes_to_hex(sha1(self)))

    def ascii_data(self):
        if len(self) > MAX_ASCII_DATA_SIZE:
            return None

        try:
            data = self.decode("ascii")
        except UnicodeDecodeError:
            return None

        for c in data:
            o = ord(c)
            if (o < 32 and o not in [9, 10, 13]) or o >= 127:
                return None

        return data

    def is_large(self):
        return len(self) >= LARGE_DATA_SIZE and self.ascii_data() is None

    def tobytes(self):
        return bytes(self)


class IonCLOB(bytes):
    def tobytes(self):
        return bytes(self)


class IonNop(object):
    pass


class IonSExp(list):
    def __repr__(self):
        return "(%s)" % (", ".join([repr(v) for v in self]))

    def tolist(self):
        return list(self)


class IonStruct(collections.OrderedDict):
    def __init__(self, *args):
        if len(args) == 1:
            collections.OrderedDict.__init__(self, args[0])
            return

        collections.OrderedDict.__init__(self)
        if len(args) % 2 != 0:
            raise Exception("IonStruct created with %d arguments" % len(args))

        for i in range(0, len(args), 2):
            self[args[i]] = args[i + 1]

    def __repr__(self):
        return "{%s}" % (
            ", ".join(["%s: %s" % (repr(k), repr(v)) for k, v in self.items()])
        )

    def todict(self):
        return collections.OrderedDict(self)


class IonSymbol(str):
    def __repr__(self):
        if re.match(r"^[\u0021-\u007e]+$", self):
            return str(self)

        return "`%s`" % self

    def tostring(self):
        return str(self)


IS = IonSymbol


class IonTimestamp(datetime.datetime):
    def __repr__(self):
        value = self

        if isinstance(value.tzinfo, IonTimestampTZ):
            format = value.tzinfo.format()
            format = format.replace(
                "%f", ("%06d" % value.microsecond)[: value.tzinfo.fraction_len()]
            )

            if value.year < 1900:
                format = format.replace("%Y", "%04d" % value.year)
                value = value.replace(year=1900)

            return value.strftime(format) + (
                value.tzname() if value.tzinfo.present() else ""
            )

        return value.isoformat()


ION_TIMESTAMP_Y = "%YT"
ION_TIMESTAMP_YM = "%Y-%mT"
ION_TIMESTAMP_YMD = "%Y-%m-%d"
ION_TIMESTAMP_YMDHM = "%Y-%m-%dT%H:%M"
ION_TIMESTAMP_YMDHMS = "%Y-%m-%dT%H:%M:%S"
ION_TIMESTAMP_YMDHMSF = "%Y-%m-%dT%H:%M:%S.%f"


class IonTimestampTZ(datetime.tzinfo):
    def __init__(self, offset, format, fraction_len):
        datetime.tzinfo.__init__(self)
        self.__offset = offset
        self.__format = format
        self.__fraction_len = fraction_len
        self.__present = format in {
            ION_TIMESTAMP_YMDHM,
            ION_TIMESTAMP_YMDHMS,
            ION_TIMESTAMP_YMDHMSF,
        }

        if offset and not self.__present:
            raise Exception(
                "IonTimestampTZ has offset %d with non-present format" % offset
            )

        if offset and (offset < -1439 or offset > 1439):
            raise Exception("IonTimestampTZ has invalid offset %d" % offset)

        if fraction_len < 0 or fraction_len > 6:
            raise Exception("IonTimestampTZ has invalid fraction len %d" % fraction_len)

        if fraction_len and format != ION_TIMESTAMP_YMDHMSF:
            raise Exception(
                "IonTimestampTZ has fraction len %d without fraction in format"
                % fraction_len
            )

    def utcoffset(self, dt):
        return datetime.timedelta(minutes=(self.__offset or 0))

    def tzname(self, dt):
        if self.__offset is None:
            name = "-00:00"
        elif self.__offset == 0:
            name = "Z"
        else:
            name = "%s%02d:%02d" % (
                "+" if self.__offset >= 0 else "-",
                abs(self.__offset) // 60,
                abs(self.__offset) % 60,
            )

        return name.encode("ascii") if IS_PYTHON2 else name

    def dst(self, dt):
        return datetime.timedelta(0)

    def offset_minutes(self):
        return self.__offset

    def format(self):
        return self.__format

    def present(self):
        return self.__present

    def fraction_len(self):
        return self.__fraction_len

    def __eq__(self, other):
        if not isinstance(other, IonTimestampTZ):
            raise Exception(
                "IonTimestampTZ __eq__: comparing with %s" % type_name(other)
            )

        return (self.__offset, self.__format, self.__fraction_len) == (
            other.__offset,
            other.__format,
            other.__fraction_len,
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


ION_TYPES = {
    IonAnnotation,
    IonBool,
    IonBLOB,
    IonCLOB,
    IonDecimal,
    IonFloat,
    IonInt,
    IonList,
    IonNull,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    IonTimestamp,
}


def unannotated(value):
    return value.value if isinstance(value, IonAnnotation) else value


def ion_data_eq(f1, f2, msg="Ion data mismatch", report_errors=True):
    def ion_data_eq_(f1, f2, ctx):
        data_type = ion_type(f1)

        if ion_type(f2) is not data_type:
            ctx.append("type mismatch: %s != %s" % (type_name(f1), type_name(f2)))
            return False

        if data_type is IonAnnotation:
            if not ion_data_eq_(IonList(f1.annotations), IonList(f2.annotations), ctx):
                ctx.append("IonAnnotation")
                return False

            if not ion_data_eq_(f1.value, f2.value, ctx):
                ctx.append("in IonAnnotation %s" % repr(f1))
                return False

            return True

        if data_type in [IonList, IonSExp]:
            if len(f1) != len(f2):
                ctx.append("%s length %d != %d" % (type_name(f1), len(f1), len(f2)))
                return False

            for i, (d1, d2) in enumerate(zip(f1, f2)):
                if not ion_data_eq_(d1, d2, ctx):
                    ctx.append("at %s index %d" % (type_name(f1), i))
                    return False

            return True

        if data_type is IonStruct:
            if len(f1) != len(f2):
                ctx.append("IonStruct length %d != %d" % (len(f1), len(f2)))
                return False

            for f1k, f1v in f1.items():
                if f1k not in f2:
                    ctx.append("IonStruct key %s missing" % f1k)
                    return False

                if not ion_data_eq_(f1v, f2[f1k], ctx):
                    ctx.append("at IonStruct key %s" % f1k)
                    return False

            return True

        if data_type is IonFloat and math.isnan(f1) and math.isnan(f2):
            return True

        if f1 != f2 or repr(f1) != repr(f2):
            ctx.append("value %s != %s" % (repr(f1), repr(f2)))
            return False

        return True

    ctx = []
    success = ion_data_eq_(f1, f2, ctx)

    if report_errors and not success:
        log.error("%s: %s" % (msg, ", ".join(ctx[::-1])))

    return success


def filtered_IonList(ion_list, omit_large_blobs=False):
    if not omit_large_blobs:
        return ion_list

    filtered = []
    for val in ion_list[:]:
        if (
            ion_type(val) is IonAnnotation
            and ion_type(val.value) is IonBLOB
            and val.value.is_large()
        ):
            val = IonAnnotation(val.annotations, repr(val.value))

        filtered.append(val)

    return filtered
