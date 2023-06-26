from __future__ import absolute_import, division, print_function, unicode_literals

import decimal
import struct

from .ion import (
    ION_TIMESTAMP_Y,
    ION_TIMESTAMP_YM,
    ION_TIMESTAMP_YMD,
    ION_TIMESTAMP_YMDHM,
    ION_TIMESTAMP_YMDHMS,
    ION_TIMESTAMP_YMDHMSF,
    IonAnnotation,
    IonBLOB,
    IonBool,
    IonCLOB,
    IonDecimal,
    IonFloat,
    IonInt,
    IonList,
    IonNop,
    IonNull,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    IonTimestamp,
    IonTimestampTZ,
    ion_type,
)
from .ion_text import IonSerial
from .message_logging import log
from .python_transition import IS_PYTHON2, bytes_, bytes_indexed
from .utilities import Deserializer, Serializer, bytes_to_separated_hex

if IS_PYTHON2:
    from .python_transition import repr


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEBUG = False


class IonBinary(IonSerial):
    MAJOR_VERSION = 1
    MINOR_VERSION = 0

    VERSION_MARKER = 0xE0

    SIGNATURE = bytes_([VERSION_MARKER, MAJOR_VERSION, MINOR_VERSION, 0xEA])

    def deserialize_multiple_values(
        self, data, import_symbols=False, with_offsets=False
    ):
        values = self.deserialize_multiple_values_(data, import_symbols, with_offsets)

        return values

    SORTED_STRUCT_FLAG = 1
    VARIABLE_LEN_FLAG = 14
    NULL_FLAG = 15

    def serialize_multiple_values_(self, values):
        serial = Serializer()
        serial.append(IonBinary.SIGNATURE)

        for value in values:
            serial.append(self.serialize_value(value))

        return serial.serialize()

    def deserialize_multiple_values_(self, data, import_symbols, with_offsets):
        if DEBUG:
            log.debug("decoding: %s" % bytes_to_separated_hex(data[:1000]))

        serial = Deserializer(data)
        self.import_symbols = import_symbols

        ion_signature = serial.extract(4)
        if ion_signature != IonBinary.SIGNATURE:
            raise Exception(
                "Ion signature is incorrect (%s)"
                % bytes_to_separated_hex(ion_signature)
            )

        result = []
        while len(serial):
            if serial.extract(1, advance=False) == IonBinary.VERSION_MARKER:
                ion_signature = serial.unpack("4s")
                if ion_signature != IonBinary.SIGNATURE:
                    raise Exception(
                        "Embedded Ion signature is incorrect (%s)"
                        % bytes_to_separated_hex(ion_signature)
                    )
            else:
                value_offset = serial.offset
                value = self.deserialize_value(serial)

                if self.import_symbols and isinstance(value, IonAnnotation):
                    if value.is_annotation("$ion_symbol_table"):
                        self.symtab.create(value.value)
                    elif value.is_annotation("$ion_shared_symbol_table"):
                        self.symtab.catalog.create_shared_symbol_table(value.value)

                if not isinstance(value, IonNop):
                    result.append(
                        [value_offset, serial.offset - value_offset, value]
                        if with_offsets
                        else value
                    )

        return result

    def serialize_value(self, value):
        handler = IonBinary.ION_TYPE_HANDLERS[ion_type(value)]
        signature, data = handler(self, value)

        if signature is None:
            return data

        length = len(data)

        if length < IonBinary.VARIABLE_LEN_FLAG:
            return descriptor(signature, length) + data

        return (
            descriptor(signature, IonBinary.VARIABLE_LEN_FLAG)
            + serialize_vluint(length)
            + data
        )

    def deserialize_value(self, serial):
        descriptor = serial.unpack("B")
        if descriptor == IonBinary.VERSION_MARKER:
            raise Exception("Unexpected Ion version marker within data stream")

        signature = descriptor >> 4
        flag = descriptor & 0x0F
        if DEBUG:
            log.debug(
                "IonBinary 0x%02x: signature=%d flag=%d data=%s"
                % (
                    descriptor,
                    signature,
                    flag,
                    bytes_to_separated_hex(serial.extract(advance=False)[:16]),
                )
            )

        extract_data, deserializer, name = IonBinary.VALUE_DESERIALIZERS[signature]

        if flag == IonBinary.NULL_FLAG and signature != IonBinary.NULL_VALUE_SIGNATURE:
            log.error("IonBinary: Deserialized null of type %s" % name)
            extract_data, deserializer, name = IonBinary.VALUE_DESERIALIZERS[
                IonBinary.NULL_VALUE_SIGNATURE
            ]

        if extract_data:
            length = (
                deserialize_vluint(serial)
                if flag == IonBinary.VARIABLE_LEN_FLAG
                else flag
            )
            return deserializer(self, serial.extract(length))

        return deserializer(self, flag, serial)

    NULL_VALUE_SIGNATURE = 0

    def serialize_null_value(self, value):
        return (None, descriptor(IonBinary.NULL_VALUE_SIGNATURE, IonBinary.NULL_FLAG))

    def deserialize_null_value(self, flag, serial):
        if flag == IonBinary.NULL_FLAG:
            return None

        length = (
            deserialize_vluint(serial) if flag == IonBinary.VARIABLE_LEN_FLAG else flag
        )
        serial.extract(length)
        return IonNop()

    BOOL_VALUE_SIGNATURE = 1

    def serialize_bool_value(self, value):
        return (None, descriptor(IonBinary.BOOL_VALUE_SIGNATURE, 1 if value else 0))

    def deserialize_bool_value(self, flag, serial):
        if flag > 1:
            raise Exception("BinaryIonBool: Unknown IonBool flag value: %d" % flag)

        return flag != 0

    def serialize_int_value(self, value):
        return (
            (IonBinary.POSINT_VALUE_SIGNATURE, serialize_unsignedint(value))
            if value >= 0
            else (IonBinary.NEGINT_VALUE_SIGNATURE, serialize_unsignedint(-value))
        )

    POSINT_VALUE_SIGNATURE = 2

    def deserialize_posint_value(self, data):
        return deserialize_unsignedint(data)

    NEGINT_VALUE_SIGNATURE = 3

    def deserialize_negint_value(self, data):
        if len(data) == 0:
            log.error("BinaryIonNegInt has no data")

        if bytes_indexed(data, 0) == 0:
            log.error(
                "BinaryIonNegInt data starts with 0x00: %s"
                % bytes_to_separated_hex(data)
            )

        return -deserialize_unsignedint(data)

    FLOAT_VALUE_SIGNATURE = 4

    def serialize_float_value(self, value):
        return (
            IonBinary.FLOAT_VALUE_SIGNATURE,
            b"" if value == 0.0 else struct.pack(">d", value),
        )

    def deserialize_float_value(self, data):
        if len(data) == 0:
            return float(0.0)

        if len(data) == 4:
            return struct.unpack_from(">f", data)[0]

        if len(data) == 8:
            return struct.unpack_from(">d", data)[0]

        raise Exception(
            "IonFloat unexpected data length: %s" % bytes_to_separated_hex(data)
        )

    DECIMAL_VALUE_SIGNATURE = 5

    def serialize_decimal_value(self, value):
        if value.is_zero():
            return (IonBinary.DECIMAL_VALUE_SIGNATURE, b"")

        vt = value.as_tuple()
        return (
            IonBinary.DECIMAL_VALUE_SIGNATURE,
            serialize_vlsint(vt.exponent)
            + serialize_signedint(combine_decimal_digits(vt.digits, vt.sign)),
        )

    def deserialize_decimal_value(self, data):
        if len(data) == 0:
            return decimal.Decimal(0)

        serial = Deserializer(data)
        exponent = deserialize_vlsint(serial)
        magnitude = deserialize_signedint(serial.extract())
        return decimal.Decimal(magnitude) * (decimal.Decimal(10) ** exponent)

    TIMESTAMP_VALUE_SIGNATURE = 6

    def serialize_timestamp_value(self, value):
        serial = Serializer()

        if isinstance(value.tzinfo, IonTimestampTZ):
            offset_minutes = value.tzinfo.offset_minutes()
            format_len = len(value.tzinfo.format())
            fraction_exponent = -value.tzinfo.fraction_len()
        else:
            offset_minutes = (
                int(value.utcoffset().total_seconds()) // 60
                if value.utcoffset() is not None
                else None
            )
            format_len = len(ION_TIMESTAMP_YMDHMSF)
            fraction_exponent = -3

        serial.append(serialize_vlsint(offset_minutes))
        serial.append(serialize_vluint(value.year))

        if format_len >= len(ION_TIMESTAMP_YM):
            serial.append(serialize_vluint(value.month))

            if format_len >= len(ION_TIMESTAMP_YMD):
                serial.append(serialize_vluint(value.day))

                if format_len >= len(ION_TIMESTAMP_YMDHM):
                    serial.append(serialize_vluint(value.hour))
                    serial.append(serialize_vluint(value.minute))

                    if format_len >= len(ION_TIMESTAMP_YMDHMS):
                        serial.append(serialize_vluint(value.second))

                        if format_len >= len(ION_TIMESTAMP_YMDHMSF):
                            serial.append(serialize_vlsint(fraction_exponent))
                            serial.append(
                                serialize_signedint(
                                    (value.microsecond * int(10**-fraction_exponent))
                                    // 1000000
                                )
                            )

        return (IonBinary.TIMESTAMP_VALUE_SIGNATURE, serial.serialize())

    def deserialize_timestamp_value(self, data):
        serial = Deserializer(data)

        offset_minutes = deserialize_vlsint(serial, allow_minus_zero=True)
        year = deserialize_vluint(serial)
        month = deserialize_vluint(serial) if len(serial) > 0 else None
        day = deserialize_vluint(serial) if len(serial) > 0 else None
        hour = deserialize_vluint(serial) if len(serial) > 0 else None
        minute = deserialize_vluint(serial) if len(serial) > 0 else None
        second = deserialize_vluint(serial) if len(serial) > 0 else None

        if len(serial) > 0:
            fraction_exponent = deserialize_vlsint(serial)
            fraction_coefficient = (
                deserialize_signedint(serial.extract()) if len(serial) > 0 else 0
            )

            if fraction_coefficient == 0 and fraction_exponent > -1:
                microsecond = None
            else:
                if fraction_exponent < -6 or fraction_exponent > -1:
                    log.error(
                        "Unexpected IonTimestamp fraction exponent %d coefficient %d: %s"
                        % (
                            fraction_exponent,
                            fraction_coefficient,
                            bytes_to_separated_hex(data),
                        )
                    )

                microsecond = (fraction_coefficient * 1000000) // int(
                    10**-fraction_exponent
                )

                if microsecond < 0 or microsecond > 999999:
                    log.error(
                        "Incorrect IonTimestamp fraction %d usec: %s"
                        % (microsecond, bytes_to_separated_hex(data))
                    )
                    microsecond = None
                    fraction_exponent = 0
        else:
            microsecond = None
            fraction_exponent = 0

        if month is None:
            format = ION_TIMESTAMP_Y
            offset_minutes = None
        elif day is None:
            format = ION_TIMESTAMP_YM
            offset_minutes = None
        elif hour is None:
            format = ION_TIMESTAMP_YMD
            offset_minutes = None
        elif second is None:
            format = ION_TIMESTAMP_YMDHM
        elif microsecond is None:
            format = ION_TIMESTAMP_YMDHMS
        else:
            format = ION_TIMESTAMP_YMDHMSF

        return IonTimestamp(
            year,
            month if month is not None else 1,
            day if day is not None else 1,
            hour if hour is not None else 0,
            minute if hour is not None else 0,
            second if second is not None else 0,
            microsecond if microsecond is not None else 0,
            IonTimestampTZ(offset_minutes, format, -fraction_exponent),
        )

    SYMBOL_VALUE_SIGNATURE = 7

    def serialize_symbol_value(self, value):
        symbol_id = self.symtab.get_id(value)
        if not symbol_id:
            raise Exception("attempt to serialize undefined symbol %s" % repr(value))

        return (IonBinary.SYMBOL_VALUE_SIGNATURE, serialize_unsignedint(symbol_id))

    def deserialize_symbol_value(self, data):
        return self.symtab.get_symbol(deserialize_unsignedint(data))

    STRING_VALUE_SIGNATURE = 8

    def serialize_string_value(self, value):
        return (IonBinary.STRING_VALUE_SIGNATURE, value.encode("utf-8"))

    def deserialize_string_value(self, data):
        return data.decode("utf-8")

    CLOB_VALUE_SIGNATURE = 9

    def serialize_clob_value(self, value):
        log.error("Serialize CLOB")
        return (IonBinary.CLOB_VALUE_SIGNATURE, bytes(value))

    def deserialize_clob_value(self, data):
        log.error("Deserialize CLOB")
        return IonCLOB(data)

    BLOB_VALUE_SIGNATURE = 10

    def serialize_blob_value(self, value):
        return (IonBinary.BLOB_VALUE_SIGNATURE, bytes(value))

    def deserialize_blob_value(self, data):
        return IonBLOB(data)

    LIST_VALUE_SIGNATURE = 11

    def serialize_list_value(self, value):
        serial = Serializer()
        for val in value:
            serial.append(self.serialize_value(val))

        return (IonBinary.LIST_VALUE_SIGNATURE, serial.serialize())

    def deserialize_list_value(self, data, top_level=False):
        serial = Deserializer(data)
        result = []
        while len(serial):
            value = self.deserialize_value(serial)

            if not isinstance(value, IonNop):
                result.append(value)

        return result

    SEXP_VALUE_SIGNATURE = 12

    def serialize_sexp_value(self, value):
        return (
            IonBinary.SEXP_VALUE_SIGNATURE,
            self.serialize_list_value(list(value))[1],
        )

    def deserialize_sexp_value(self, data):
        return IonSExp(self.deserialize_list_value(data))

    STRUCT_VALUE_SIGNATURE = 13

    def serialize_struct_value(self, value):
        serial = Serializer()

        for key, val in value.items():
            serial.append(serialize_vluint(self.symtab.get_id(key)))
            serial.append(self.serialize_value(val))

        return (IonBinary.STRUCT_VALUE_SIGNATURE, serial.serialize())

    def deserialize_struct_value(self, flag, serial):
        if flag == IonBinary.SORTED_STRUCT_FLAG:
            log.error("BinaryIonStruct: Sorted IonStruct encountered")
            flag = IonBinary.VARIABLE_LEN_FLAG

        serial2 = Deserializer(
            serial.extract(
                deserialize_vluint(serial)
                if flag == IonBinary.VARIABLE_LEN_FLAG
                else flag
            )
        )
        result = IonStruct()

        while len(serial2):
            id_symbol = self.symtab.get_symbol(deserialize_vluint(serial2))

            value = self.deserialize_value(serial2)
            if DEBUG:
                log.debug("IonStruct: %s = %s" % (repr(id_symbol), repr(value)))

            if not isinstance(value, IonNop):
                if id_symbol in result:
                    log.error("BinaryIonStruct: Duplicate field name %s" % id_symbol)

                result[id_symbol] = value

        return result

    ANNOTATION_VALUE_SIGNATURE = 14

    def serialize_annotation_value(self, value):
        if not value.annotations:
            raise Exception("Serializing IonAnnotation without annotations")

        serial = Serializer()

        annotation_data = Serializer()
        for annotation in value.annotations:
            annotation_data.append(serialize_vluint(self.symtab.get_id(annotation)))

        serial.append(serialize_vluint(len(annotation_data)))
        serial.append(annotation_data.serialize())

        serial.append(self.serialize_value(value.value))

        return (IonBinary.ANNOTATION_VALUE_SIGNATURE, serial.serialize())

    def deserialize_annotation_value(self, data):
        serial = Deserializer(data)

        annotation_length = deserialize_vluint(serial)
        annotation_data = Deserializer(serial.extract(annotation_length))

        ion_value = self.deserialize_value(serial)
        if len(serial):
            raise Exception(
                "IonAnnotation has excess data: %s"
                % bytes_to_separated_hex(serial.extract())
            )

        annotations = []
        while len(annotation_data):
            annotations.append(
                self.symtab.get_symbol(deserialize_vluint(annotation_data))
            )

        if len(annotations) == 0:
            raise Exception("IonAnnotation has no annotations")

        return IonAnnotation(annotations, ion_value)

    RESERVED_VALUE_SIGNATURE = 15

    def deserialize_reserved_value(self, data):
        raise Exception(
            "Deserialize reserved ion value signature %d" % self.value_signature
        )

    VALUE_DESERIALIZERS = {
        NULL_VALUE_SIGNATURE: (False, deserialize_null_value, "null"),
        BOOL_VALUE_SIGNATURE: (False, deserialize_bool_value, "bool"),
        POSINT_VALUE_SIGNATURE: (True, deserialize_posint_value, "int"),
        NEGINT_VALUE_SIGNATURE: (True, deserialize_negint_value, "int"),
        FLOAT_VALUE_SIGNATURE: (True, deserialize_float_value, "float"),
        DECIMAL_VALUE_SIGNATURE: (True, deserialize_decimal_value, "decimal"),
        TIMESTAMP_VALUE_SIGNATURE: (True, deserialize_timestamp_value, "timestamp"),
        SYMBOL_VALUE_SIGNATURE: (True, deserialize_symbol_value, "symbol"),
        STRING_VALUE_SIGNATURE: (True, deserialize_string_value, "string"),
        CLOB_VALUE_SIGNATURE: (True, deserialize_clob_value, "clob"),
        BLOB_VALUE_SIGNATURE: (True, deserialize_blob_value, "blob"),
        LIST_VALUE_SIGNATURE: (True, deserialize_list_value, "list"),
        SEXP_VALUE_SIGNATURE: (True, deserialize_sexp_value, "sexp"),
        STRUCT_VALUE_SIGNATURE: (False, deserialize_struct_value, "struct"),
        ANNOTATION_VALUE_SIGNATURE: (True, deserialize_annotation_value, "annotation"),
        RESERVED_VALUE_SIGNATURE: (True, deserialize_reserved_value, "reserved"),
    }

    ION_TYPE_HANDLERS = {
        IonAnnotation: serialize_annotation_value,
        IonBLOB: serialize_blob_value,
        IonBool: serialize_bool_value,
        IonCLOB: serialize_clob_value,
        IonDecimal: serialize_decimal_value,
        IonFloat: serialize_float_value,
        IonInt: serialize_int_value,
        IonList: serialize_list_value,
        IonNull: serialize_null_value,
        IonSExp: serialize_sexp_value,
        IonString: serialize_string_value,
        IonStruct: serialize_struct_value,
        IonSymbol: serialize_symbol_value,
        IonTimestamp: serialize_timestamp_value,
    }


def descriptor(signature, flag):
    if flag < 0 or flag > 0x0F:
        raise Exception("Serialize bad descriptor flag: %d" % flag)

    return bytes_([(signature << 4) + flag])


def serialize_unsignedint(value):
    return ltrim0(struct.pack(">Q", value))


def deserialize_unsignedint(data):
    if len(data) > 0 and bytes_indexed(data, 0) == 0:
        raise Exception("BinaryIonInt data padded with 0x00")

    return struct.unpack_from(">Q", lpad0(data, 8))[0]


def serialize_signedint(value):
    data = ltrim0x(struct.pack(">Q", abs(value)))

    if value < 0:
        data = or_first_byte(data, 0x80)

    return data


def deserialize_signedint(data):
    if len(data) == 0:
        return 0

    if (bytes_indexed(data, 0) & 0x80) != 0:
        return -(struct.unpack_from(">Q", lpad0(and_first_byte(data, 0x7F), 8))[0])

    return struct.unpack_from(">Q", lpad0(data, 8))[0]


def serialize_vluint(value):
    if value < 0:
        raise Exception("Cannot serialize negative value as IonVLUInt: %d" % value)

    datalst = [(value & 0x7F) + 0x80]
    while True:
        value = value >> 7
        if value == 0:
            return bytes_(datalst)

        datalst.insert(0, value & 0x7F)


def deserialize_vluint(serial):
    value = 0
    while True:
        i = serial.unpack("B")
        value = (value << 7) | (i & 0x7F)

        if i & 0x80:
            return value

        if value == 0:
            raise Exception("IonVLUInt padded with 0x00")

        if value > 0x7FFFFFFFFFFFFF:
            raise Exception("IonVLUInt data value is too large, missing terminator")


def serialize_vlsint(value):
    if value is None:
        return b"\xc0"

    data = serialize_vluint(abs(value))

    if bytes_indexed(data, 0) & 0x40:
        data = b"\x00" + data

    if value < 0:
        data = or_first_byte(data, 0x40)

    return data


def deserialize_vlsint(serial, allow_minus_zero=False):
    first = serial.unpack("B")
    ibyte = first & 0xBF

    datalst = []
    if ibyte != 0:
        datalst.append(ibyte)

    while (ibyte & 0x80) == 0:
        ibyte = serial.unpack("B")
        datalst.append(ibyte)

    value = deserialize_vluint(Deserializer(bytes_(datalst)))

    if first & 0x40:
        if value:
            value = -value
        elif allow_minus_zero:
            value = None
        else:
            raise Exception("deserialize_vlsint unexpected -0 value")

    return value


def lpad0(data, size):
    if len(data) > size:
        extra = len(data) - size
        if data[:size] != b"\x00" * extra:
            raise Exception(
                "lpad0, length (%d) > max (%d): %s"
                % (len(data), size, bytes_to_separated_hex(data))
            )

        return data[:size]

    return b"\x00" * (size - len(data)) + data


def ltrim0(data):
    while len(data) and bytes_indexed(data, 0) == 0:
        data = data[1:]

    return data


def ltrim0x(data):
    while len(data) and bytes_indexed(data, 0) == 0:
        if len(data) > 1 and (bytes_indexed(data, 1) & 0x80):
            break

        data = data[1:]

    return data


def combine_decimal_digits(digits, sign_negative):
    val = 0

    for digit in digits:
        val = (val * 10) + digit

    if sign_negative:
        val = -val

    return val


def and_first_byte(data, mask):
    return bytes_([bytes_indexed(data, 0) & mask]) + data[1:]


def or_first_byte(data, mask):
    return bytes_([bytes_indexed(data, 0) | mask]) + data[1:]
