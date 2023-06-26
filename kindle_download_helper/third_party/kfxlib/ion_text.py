from __future__ import absolute_import, division, print_function, unicode_literals

import base64
import datetime
import decimal
import math
import re
import traceback

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
    IonNull,
    IonSExp,
    IonString,
    IonStruct,
    IonSymbol,
    IonTimestamp,
    IonTimestampTZ,
    ion_type,
)
from .message_logging import log
from .python_transition import IS_PYTHON2, bytes_
from .utilities import UNICODE_PYTHON_NARROW_BUILD, quote_name, type_name

if IS_PYTHON2:
    from .python_transition import chr, repr, str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEBUG = False


RESERVED_TOKENS = {
    "null",
    "null.null",
    "true",
    "false",
    "nan",
    "+inf",
    "-inf",
    "null.bool",
    "null.int",
    "null.float",
    "null.decimal",
    "null.timestamp",
    "null.string",
    "null.symbol",
    "null.blob",
    "null.clob",
    "null.struct",
    "null.list",
    "null.sexp",
}

INDENT_SPACES = 2

OPERATOR_RE = r"^[!#%&*+./;<=>?@^`|~-]+$"


class ParseError(ValueError):
    pass


class IonSerial(object):
    def __init__(self, symtab=None):
        self.symtab = symtab

    def serialize_single_value(self, value):
        return self.serialize_multiple_values([value])

    def serialize_multiple_values(self, values):
        return self.serialize_multiple_values_(values)

    def deserialize_annotated_value(
        self, data, expect_annotation=None, import_symbols=False
    ):
        value = self.deserialize_single_value(data, import_symbols)

        if not isinstance(value, IonAnnotation):
            raise Exception(
                "deserialize_annotated_value returned %s" % type_name(value)
            )

        if expect_annotation is not None:
            value.verify_annotation(expect_annotation)

        return value

    def deserialize_single_value(self, data, import_symbols=False):
        values = self.deserialize_multiple_values(data, import_symbols)
        if len(values) != 1:
            raise Exception(
                "Expected single Ion value found %d: %s" % (len(values), repr(values))
            )

        return values[0]

    def deserialize_multiple_values(self, data, import_symbols=False):
        return self.deserialize_multiple_values_(data, import_symbols)


class IonText(IonSerial):
    MAJOR_VERSION = 1
    MINOR_VERSION = 0

    SIGNATURE_STR = "$ion_%d_%d" % (MAJOR_VERSION, MINOR_VERSION)
    SIGNATURE = SIGNATURE_STR.encode("ascii")

    def __init__(self, symtab=None):
        IonSerial.__init__(self, symtab)

        self.indent = 0
        self.file = None
        self.allow_operators = 0
        self.allow_unicode_strings = True

    def serialize_multiple_values(self, values):
        data = self.serialize_multiple_values_(values)

        return data

    def deserialize_multiple_values(
        self, data, import_symbols=False, disable_equiv_test=False
    ):
        values = self.deserialize_multiple_values_(data, import_symbols)

        return values

    def unicode_single_value(self, value):
        return self.serialize_value(value)

    def serialize_multiple_values_(self, values):
        result = []

        result.append(self.serialize_value(IonSymbol("$ion_1_0")))

        for value in values:
            result.append(self.serialize_value(value))

        return ("\n\n".join(result) + "\n").encode("utf8")

    def serialize_value(self, value):
        handler = IonText.ION_TYPE_HANDLERS[ion_type(value)]
        return handler(self, value)

    def deserialize_multiple_values_(self, data, import_symbols):
        if isinstance(data, bytes):
            data = data.decode("utf8")

        self.import_symbols = import_symbols

        self.file = IonTextFile(data)

        try:
            result = []
            while self.file.current_token().ttype != TOKEN_EOF:
                value = self.deserialize_annotated_next_value()

                if isinstance(value, IonSymbol) and re.match(
                    r"^\$ion_[0-9]+_[0-9]+$", value
                ):
                    if value != IonText.SIGNATURE_STR:
                        raise ValueError(
                            "Ion version marker incorrect: %s" % repr(value)
                        )

                elif (
                    self.import_symbols
                    and isinstance(value, IonAnnotation)
                    and (
                        value.has_annotation("$ion_symbol_table")
                        or value.has_annotation("$ion_shared_symbol_table")
                    )
                    and isinstance(value.value, IonStruct)
                ):
                    if value.has_annotation("$ion_symbol_table"):
                        self.symtab.create(value.value)
                    else:
                        self.symtab.catalog.create_shared_symbol_table(value.value)

                    if self.import_symbols:
                        result.append(value)

                else:
                    result.append(value)

            return result

        except Exception as e:
            if IS_PYTHON2:
                traceback.print_exc()

            raise ValueError(
                "Ion text parse failure at %s: %s"
                % (str(self.file.current_token()), repr(e))
            )

    def deserialize_annotated_next_value(self):
        value = self.deserialize_next_value()
        annotations = []
        while self.file.current_token().ttype == "::":
            self.file.next_token()

            if not isinstance(value, IonSymbol):
                raise ParseError("Annotation '%s' is not a symbol" % repr(value))

            annotations.append(value)

            value = self.deserialize_next_value()

        if annotations:
            return IonAnnotation(annotations, value)

        return value

    def deserialize_next_value(self):
        token = self.file.current_token()
        if token.ttype in [
            "null",
            "null.null",
            "null.bool",
            "null.int",
            "null.float",
            "null.decimal",
            "null.timestamp",
            "null.string",
            "null.symbol",
            "null.blob",
            "null.clob",
            "null.struct",
            "null.list",
            "null.sexp",
        ]:
            value = self.deserialize_null_value(token)

        elif token.ttype == "true" or token.ttype == "false":
            value = self.deserialize_bool_value(token)

        elif token.ttype == TOKEN_INT:
            value = self.deserialize_int_value(token)

        elif token.ttype == TOKEN_FLOAT or token.ttype in ["nan", "+inf", "-inf"]:
            value = self.deserialize_float_value(token)

        elif token.ttype == TOKEN_DECIMAL:
            value = self.deserialize_decimal_value(token)

        elif token.ttype == TOKEN_TIMESTAMP:
            value = self.deserialize_timestamp_value(token)

        elif token.ttype in [TOKEN_IDENTIFIER, TOKEN_QUOTED_SYMBOL, TOKEN_OPERATOR]:
            value = self.deserialize_symbol_value(token)

        elif token.ttype in [TOKEN_STRING, TOKEN_LONG_STRING]:
            value = self.deserialize_string_value(token)

        elif token.ttype == "{{":
            self.file.allow_comments(False)
            self.file.allow_double_close(True)
            self.allow_unicode_strings = False

            if self.file.peek_token().ttype in [TOKEN_STRING, TOKEN_LONG_STRING]:
                value = self.deserialize_clob_value(token)
            else:
                value = self.deserialize_blob_value(token)

            self.allow_unicode_strings = True
            self.file.allow_double_close(False)
            self.file.allow_comments(True)

        elif token.ttype == "[":
            value = self.deserialize_list_value(token)

        elif token.ttype == "(":
            value = self.deserialize_sexp_value(token)

        elif token.ttype == "{":
            value = self.deserialize_struct_value(token)

        elif token.ttype == TOKEN_EOF:
            raise ParseError("End of file encountered when value expected")

        else:
            raise ParseError("Cannot determine type of value")

        self.file.next_token()
        return value

    def indent_(self):
        return " " * (INDENT_SPACES * self.indent)

    def serialize_null_value(self, value):
        return "null"

    def deserialize_null_value(self, token):
        if token.text == "null" or token.text == "null.null":
            return None

        if token.text.startswith("null."):
            log.error(
                "TextIonNull deserialized %s to null (typed null not supported)"
                % token.text
            )
            return None

        raise ParseError("Incorrect null value")

    def serialize_bool_value(self, value):
        return "true" if value else "false"

    def deserialize_bool_value(self, token):
        if token.text == "true":
            return True

        if token.text == "false":
            return False

        raise ParseError("Incorrect bool value")

    def serialize_int_value(self, value):
        if value >= 0x000FFFFF:
            return "0x%x" % value

        return "%d" % value

    def deserialize_int_value(self, token):
        text = remove_underscores_between_digits(token.text)

        if re.match(r"^-?[0-9]+$", text):
            return int(text)

        if re.match(r"^-?0b[01]+$", text, flags=re.IGNORECASE):
            if text.startswith("-"):
                return -int(text[3:], 2)

            return int(text[2:], 2)

        text = remove_underscores_between_digits(token.text, hex=True)

        if re.match(r"^-?0x[0-9a-f]+$", text, flags=re.IGNORECASE):
            if text.startswith("-"):
                return -int(text[3:], 16)

            return int(text[2:], 16)

        raise ParseError("Incorrect int value")

    def serialize_float_value(self, value):
        if math.isnan(value):
            return "nan"

        if math.isinf(value):
            return "+inf" if value > 0 else "-inf"

        s = "%.16e" % value
        if re.search(r"0000000[1-9]e", s, flags=re.IGNORECASE) or re.search(
            r"9999999[0-9]e", s, flags=re.IGNORECASE
        ):
            s = "%.15e" % value

        s = s.lower().replace("e+", "e")
        s = re.sub(r"(\.[0-9]*[1-9])0+e", r"\1e", s)
        s = re.sub(r"\.0*e", r"e", s)
        s = re.sub(r"e(-?)0([0-9])", r"e\1\2", s)
        return s

    def deserialize_float_value(self, token):
        text = remove_underscores_between_digits(token.text)

        if text == "nan":
            return float("nan")

        if text == "+inf":
            return float("inf")

        if text == "-inf":
            return -float("inf")

        if re.match(r"^-?[0-9]+(\.[0-9]*)?e[+-]?[0-9]+$", text, flags=re.IGNORECASE):
            return float(text)

        raise ParseError("Incorrect float value")

    def serialize_decimal_value(self, value):
        result = str(value).lower().replace("e", "d")

        if ("." not in result) and ("d" not in result):
            result = result + "."

        return result

    def deserialize_decimal_value(self, token):
        text = remove_underscores_between_digits(token.text)

        if re.match(r"^-?[0-9]+(\.[0-9]*)?$", text, flags=re.IGNORECASE):
            return decimal.Decimal(text)

        if re.match(r"^-?[0-9]+(\.[0-9]*)?d[+-]?[0-9]+$", text, flags=re.IGNORECASE):
            return decimal.Decimal(text.replace("d", "e").replace("D", "e"))

        raise ParseError("Incorrect decimal value")

    def serialize_timestamp_value(self, value):
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
        else:
            raise Exception("TextIonTimestamp: timestamp does not have IonTimestampTZ")

    def deserialize_timestamp_value(self, token):
        text = token.text

        m = re.search(r"Z|([+-][0-9]{2}:[0-9]{2})$", text)
        if m:
            tz_present = True
            tzstr = m.group(0)
            text = text[: -len(tzstr)]

            if tzstr == "Z":
                offset_minutes = 0
            elif tzstr == "-00:00":
                offset_minutes = None
            else:
                offset_hours = int(tzstr[1:3])
                offset_minutes = int(tzstr[4:])
                if offset_hours > 23 or offset_minutes > 59:
                    raise Exception("Incorrect time zone offset")

                offset_minutes += offset_hours * 60
                if tzstr[0] == "-":
                    offset_minutes = -offset_minutes
        else:
            tz_present = False
            offset_minutes = None

        fraction_len = 0
        format = None

        if not tz_present:
            if re.match(r"^[0-9]{4}T$", text):
                format = ION_TIMESTAMP_Y

            elif re.match(r"^[0-9]{4}-[0-1][0-9]T$", text):
                format = ION_TIMESTAMP_YM

            elif re.match(r"^[0-9]{4}-[0-1][0-9]-[0-3][0-9]T?$", text):
                format = ION_TIMESTAMP_YMD
                text = text[:10]
        else:
            if re.match(r"^[0-9]{4}-[0-1][0-9]-[0-3][0-9]T[0-9]{2}:[0-9]{2}$", text):
                format = ION_TIMESTAMP_YMDHM

            elif re.match(
                r"^[0-9]{4}-[0-1][0-9]-[0-3][0-9]T[0-9]{2}:[0-9]{2}:[0-9]{2}$", text
            ):
                format = ION_TIMESTAMP_YMDHMS

            elif re.match(
                r"^[0-9]{4}-[0-1][0-9]-[0-3][0-9]T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{1,20}$",
                text,
            ):
                format = ION_TIMESTAMP_YMDHMSF
                text = text[:26]
                fraction_len = len(text) - 20

        if format:
            v = datetime.datetime.strptime(text, format)
            return IonTimestamp(
                v.year,
                v.month,
                v.day,
                v.hour,
                v.minute,
                v.second,
                v.microsecond,
                IonTimestampTZ(offset_minutes, format, fraction_len),
            )

        raise ParseError("Incorrect timestamp value")

    def serialize_symbol_value(self, value):
        result = value.tostring()

        if self.symtab and self.symtab.export_translate:
            result = self.symtab.export_translate.get(result, result)

        if result not in RESERVED_TOKENS and (
            re.match(r"^[a-zA-Z$_][a-zA-Z0-9$_]*$", result)
            or (self.allow_operators and re.match(OPERATOR_RE, result))
        ):
            return result

        return "'%s'" % escape_string(result, quote="'")

    def deserialize_symbol_value(self, token):
        if (
            token.ttype == TOKEN_QUOTED_SYMBOL
            and token.text.startswith("'")
            and token.text.endswith("'")
        ):
            return self.create_symbol(unescape_quoted_symbol(token.text))

        if token.ttype == TOKEN_IDENTIFIER and re.match(r"^\$[0-9]+$", token.text):
            symnum = int(token.text[1:])
            if self.symtab and symnum > 0:
                return self.symtab.get_symbol(symnum)

        if token.ttype == TOKEN_IDENTIFIER and re.match(
            r"^[a-zA-Z$_][a-zA-Z0-9$_]*$", token.text
        ):
            return self.create_symbol(token.text)

        if (
            token.ttype == TOKEN_OPERATOR
            and self.allow_operators
            and re.match(OPERATOR_RE, token.text)
        ):
            return self.create_symbol(token.text)

        raise ParseError("Incorrect symbol")

    def create_symbol(self, name):
        if self.symtab and self.symtab.import_translate:
            name = self.symtab.import_translate.get(name, name)

        sym = IonSymbol(name)

        if self.import_symbols is not False:
            self.symtab.get_id(sym)

        return sym

    def serialize_string_value(self, value):
        return '"%s"' % escape_string(value, quote='"')

    def deserialize_string_value(self, token):
        if token.ttype == TOKEN_LONG_STRING:
            val = []
            while True:
                val.append(
                    unescape_string(
                        token.text, allow_unicode=self.allow_unicode_strings
                    )
                )
                if self.file.peek_token().ttype != TOKEN_LONG_STRING:
                    break

                token = self.file.next_token()

            return "".join(val)

        if token.ttype == TOKEN_STRING:
            return unescape_string(token.text, allow_unicode=self.allow_unicode_strings)

        raise ParseError("Incorrect string")

    def serialize_blob_value(self, value):
        result = []

        ascii_data = value.ascii_data()
        if ascii_data:
            result.append("\n")
            clean_ascii_data = (
                ascii_data.replace("\r\n", "\n")
                .replace("\r", "\n")
                .replace("\t", "    ")
            )
            for s in clean_ascii_data.split("\n"):
                result.append("%s// %s\n" % (self.indent_(), s))

            result.append("%s{{\n" % self.indent_())
        else:
            result.append("{{\n")

        self.indent += 1

        data = base64.b64encode(value).decode("ascii")

        for s in split_string(data, max_size=80):
            result.append("%s%s\n" % (self.indent_(), s))

        self.indent -= 1
        result.append("%s}}" % self.indent_())

        return "".join(result)

    def deserialize_blob_value(self, token):
        if token.ttype != "{{":
            raise ParseError("BLOB missing '{{'")

        b64text = []
        while True:
            token = self.file.next_token()
            if token.ttype == "}}":
                break

            if re.match(r"^[0-9A-Za-z+/=]+$", token.text):
                b64text.append(token.text)
            else:
                raise ParseError("Incorrect BLOB value (not base64)")

        return IonBLOB(base64.b64decode("".join(b64text)))

    def serialize_clob_value(self, value):
        return '{{ "%s" }}' % escape_string(value, quote='"')

    def deserialize_clob_value(self, token):
        if token.ttype != "{{":
            raise ParseError("CLOB missing '{{'")

        s = bytes_only(self.deserialize_string_value(self.file.next_token()))

        if self.file.next_token().ttype != "}}":
            raise ParseError("CLOB missing '}}'")

        return IonCLOB(s)

    COMPACT_TYPES = {
        IonNull,
        IonBool,
        IonInt,
        IonFloat,
        IonDecimal,
        IonTimestamp,
        IonString,
        IonSymbol,
    }

    def serialize_list_value(self, value):
        for val in value:
            if ion_type(val) is IonList:
                for val2 in val:
                    if ion_type(val2) not in IonText.COMPACT_TYPES:
                        compact = False
                        break

            elif ion_type(val) not in IonText.COMPACT_TYPES:
                compact = False
                break
        else:
            compact = True

        if compact:
            return "[%s]" % (", ".join([self.serialize_value(val) for val in value]))

        result = ["[\n"]
        self.indent += 1
        for val in value:
            result.append("%s%s,\n" % (self.indent_(), self.serialize_value(val)))

        self.indent -= 1
        result.append("%s]" % self.indent_())
        return "".join(result)

    def deserialize_list_value(self, token):
        if token.ttype != "[":
            raise ParseError("List missing '['")

        value = []
        while True:
            token = self.file.next_token()
            if token.ttype == "]":
                break

            value.append(self.deserialize_annotated_next_value())

            token = self.file.current_token()
            if token.ttype == ",":
                continue

            if token.ttype == "]":
                break

            raise ParseError("Expected ',' or ']' after list value")

        return value

    def serialize_sexp_value(self, value):
        result = ["("]
        self.allow_operators += 1

        for val in value:
            result.append(self.serialize_value(val))

        self.allow_operators -= 1
        result.append(")")
        return " ".join(result)

    def deserialize_sexp_value(self, token):
        if token.ttype != "(":
            raise ParseError("S-expression missing '('")

        token = self.file.next_token()
        value = IonSExp()
        self.allow_operators += 1

        while True:
            if token.ttype == ")":
                break

            value.append(self.deserialize_annotated_next_value())

            token = self.file.current_token()
            if token.ttype == ")":
                break

        self.allow_operators -= 1
        return value

    def serialize_struct_value(self, value):
        result = ["{\n"]
        self.indent += 1

        for key, val in value.items():
            result.append(
                "%s%s: %s,\n"
                % (self.indent_(), self.serialize_value(key), self.serialize_value(val))
            )

        self.indent -= 1
        result.append("%s}" % self.indent_())
        return "".join(result)

    def deserialize_struct_value(self, token):
        if token.ttype != "{":
            raise ParseError("Struct missing '{'")

        value = IonStruct()
        while True:
            token = self.file.next_token()
            if token.ttype == "}":
                break

            key = self.deserialize_annotated_next_value()

            if isinstance(key, (IonString, str)):
                key = IonSymbol(key)

            if not isinstance(key, IonSymbol):
                raise ParseError(
                    "Struct key must be symbol (found %s)" % type_name(key)
                )

            if key in value:
                log.error("TextIonStruct: Duplicate field name %s" % key)

                while key in value:
                    key = IonSymbol(key + "_")

            token = self.file.current_token()
            if token.ttype != ":":
                raise ParseError("Expected ':' after struct key")

            self.file.next_token()
            value[key] = self.deserialize_annotated_next_value()

            token = self.file.current_token()
            if token.ttype == ",":
                continue

            if token.ttype == "}":
                break

            raise ParseError("Expected ',' or '}' after struct value")

        return value

    def serialize_annotation_value(self, value):
        result = []

        for annotation in value.annotations:
            result.append("%s::" % (self.serialize_value(annotation)))

        result.append(self.serialize_value(value.value))

        return " ".join(result)

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


def remove_underscores_between_digits(text, hex=False):
    while True:
        text, n = re.subn(
            r"([0-9a-fA-F])_([0-9a-fA-F])" if hex else r"([0-9])_([0-9])", r"\1\2", text
        )
        if not n:
            return text


def bytes_only(s):
    ss = []
    for c in s:
        o = ord(c)
        if o > 255:
            raise ValueError("CLOB character '%s' (%d) is not byte" % (c, o))

        ss.append(o)

    return bytes_(ss)


def escape_string(s, quote='"'):
    ss = []
    i = 0
    while i < len(s):
        c = s[i]
        o = ord(c)
        i += 1

        if c == quote or c == "\\":
            ss.append("\\")
            ss.append(c)
        elif o >= 0x20 and o <= 0x7E:
            ss.append(c)
        elif o == 0x09:
            ss.append("\\t")
        elif o == 0x0A:
            ss.append("\\n")
        elif o == 0x0D:
            ss.append("\\r")
        elif o <= 0xFF:
            ss.append("\\x%02x" % o)
        elif (
            UNICODE_PYTHON_NARROW_BUILD
            and o >= 0xD800
            and o <= 0xDBFF
            and i < len(s)
            and ord(s[i]) >= 0xDC00
            and ord(s[i]) <= 0xDFFF
        ):
            ss.append(
                "\\U%08x" % ((o - 0xD800) * 0x400 + (ord(s[i]) - 0xDC00) + 0x10000)
            )
            i += 1
        elif o <= 0xFFFF:
            ss.append("\\u%04x" % o)
        else:
            ss.append("\\U%08x" % o)

    return "".join(ss)


ESC_SUB = {
    "0": chr(0x0000),
    "a": chr(0x0007),
    "b": chr(0x0008),
    "t": chr(0x0009),
    "n": chr(0x000A),
    "v": chr(0x000B),
    "f": chr(0x000C),
    "r": chr(0x000D),
    "'": "'",
    '"': '"',
    "?": "?",
    "/": "/",
    "\\": "\\",
}


def unescape_string(qs, allow_unicode=True):
    if len(qs) >= 6 and qs.startswith("'''") and qs.endswith("'''"):
        return unescape_string_(qs[3:-3], allow_unicode=allow_unicode, allow_eol=True)

    if len(qs) >= 2 and qs[0] == '"' and qs[-1] == '"':
        return unescape_string_(qs[1:-1], allow_unicode=allow_unicode)

    raise ParseError("Invalid string format")


def unescape_quoted_symbol(qs):
    if len(qs) >= 2 and qs[0] == "'" and qs[-1] == "'":
        return unescape_string_(qs[1:-1])

    raise ParseError("Invalid quoted symbol format")


def unescape_string_(s, allow_unicode=True, allow_eol=False):
    ss = []
    idx = 0

    while idx < len(s):
        c = s[idx]
        if c == "\\":
            idx += 1
            c = s[idx]

            if c == "x":
                ss.append(chr(int(s[idx + 1 : idx + 3], 16)))
                idx += 3
            elif c == "u" and allow_unicode:
                ss.append(chr(int(s[idx + 1 : idx + 5], 16)))
                idx += 5
            elif c == "U" and allow_unicode:
                o = int(s[idx + 1 : idx + 9], 16)

                if UNICODE_PYTHON_NARROW_BUILD and o > 0xFFFF:
                    cc = (b"\\U%08x" % o).decode("unicode-escape")
                else:
                    cc = chr(o)

                ss.append(cc)
                idx += 9
            elif c in ESC_SUB:
                ss.append(ESC_SUB[c])
                idx += 1
            elif c == "\n":
                idx += 1
            elif c == "\r":
                idx += 1
                if idx < len(s) and s[idx] == "\n":
                    idx += 1
            else:
                raise ParseError(
                    "Invalid string escape character '%s' (%02x)" % (c, ord(c))
                )

        elif allow_eol and c == "\r":
            ss.append("\n")
            idx += 1
            if idx < len(s) and s[idx] == "\n":
                idx += 1

        elif allow_eol and c == "\n":
            ss.append(c)
            idx += 1

        elif ord(c) < 0x20 or ord(c) == 0x7F:
            raise ParseError("Invalid control character (%02x)" % ord(c))

        elif ord(c) > 0x7F and not allow_unicode:
            raise ParseError("Unicode character (%x) not allowed" % ord(c))

        else:
            ss.append(c)
            idx += 1

    if idx > len(s):
        raise ParseError("Invalid escape sequence beyond end of string")

    return "".join(ss)


def split_string(s, max_size=80):
    return [s[i : i + max_size] for i in range(0, len(s), max_size)]


TOKEN_DECIMAL = "decimal"
TOKEN_EOF = "eof"
TOKEN_FLOAT = "float"
TOKEN_IDENTIFIER = "identifier"
TOKEN_INT = "int"
TOKEN_QUOTED_SYMBOL = "quoted symbol"
TOKEN_STRING = "string"
TOKEN_LONG_STRING = "long string"
TOKEN_TIMESTAMP = "timestamp"
TOKEN_UNKNOWN = "unknown"
TOKEN_UNTERMINATED_STRING = "unterminated string"
TOKEN_OPERATOR = "operator"


class Token(object):
    def __init__(self, text, line_number, start_col):
        self.text = text
        self.line_number = line_number
        self.start_col = start_col
        self.ttype = self.classify()

    def __repr__(self):
        return "line=%d col=%d type=%s text=%s" % (
            self.line_number,
            self.start_col + 1,
            quote_name(self.ttype),
            quote_name(self.text),
        )

    def classify(self):
        if not self.text:
            return TOKEN_EOF

        c = self.text[:1]

        if c == "'" or c == '"':
            if len(self.text) >= 2 and c == '"' and self.text[-1] == '"':
                return TOKEN_STRING

            if (
                len(self.text) >= 6
                and self.text.startswith("'''")
                and self.text.endswith("'''")
            ):
                return TOKEN_LONG_STRING

            if len(self.text) >= 2 and c == "'" and self.text[-1] == "'":
                return TOKEN_QUOTED_SYMBOL

            return TOKEN_UNTERMINATED_STRING

        if self.text in {"[", "]", "{", "}", "{{", "}}", "(", ")", ":", "::", ",", ""}:
            return self.text

        if self.text in RESERVED_TOKENS:
            return self.text

        if re.match("^[a-zA-Z$_][0-9a-zA-Z$_]*$", self.text):
            return TOKEN_IDENTIFIER

        if re.match(OPERATOR_RE, self.text):
            return TOKEN_OPERATOR

        if c in {"-", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            ltext = self.text.lower()

            if re.match(r"^-?0[bx]", ltext):
                return TOKEN_INT

            if re.match(r"^-?[0-9_]+$", ltext):
                return TOKEN_INT

            if "e" in ltext and re.match(r"^[0-9_e.+-]+$", ltext):
                return TOKEN_FLOAT

            if ("d" in ltext or "." in ltext) and re.match(r"^[0-9_d.+-]+$", ltext):
                return TOKEN_DECIMAL

            if (
                ":" in self.text
                or "T" in self.text
                or "Z" in self.text
                or (self.text[4:5] == "-" and self.text[7:8] == "-")
            ) and re.match(r"^[0-9][0-9.:TZ+-]+$", self.text):
                return TOKEN_TIMESTAMP

        return TOKEN_UNKNOWN


class IonTextFile(object):
    def __init__(self, data):
        self.data = data
        self.cursor = 0
        self.line_number = 1
        self.column_number = 1
        self.eof = False

        self.allow_comments_ = True
        self.allow_double_close_ = False
        self.current_token_ = None
        self.peek_token_ = None

    def next_char(self):
        if self.cursor >= len(self.data):
            self.eof = True
            return ""

        c = self.data[self.cursor]
        self.cursor += 1

        if c == "\r":
            c = "\n"
            if self.cursor < len(self.data) and self.data[self.cursor] == "\n":
                self.cursor += 1

        if c == "\n":
            self.line_number += 1
            self.column_number = 0
        else:
            self.column_number += 1

        return c

    def advance_char(self, count=1):
        while count:
            self.next_char()
            count -= 1

    def peek_char(self, offset=0):
        if self.cursor + offset >= len(self.data):
            return ""

        c = self.data[self.cursor + offset]
        return "\n" if c == "\r" else c

    def get_next_line(self):
        while (not self.eof) and self.next_char() != "\n":
            pass

    def skip_whitespace(self):
        while self.peek_char() in [" ", "\t", "\n"]:
            self.next_char()

    def next_token(self):
        if self.peek_token_ is not None:
            self.current_token_ = self.peek_token_
            self.peek_token_ = None
        else:
            self.current_token_ = self.get_next_token()

        return self.current_token_

    def current_token(self):
        if self.current_token_ is not None:
            return self.current_token_

        return self.next_token()

    def peek_token(self):
        if self.peek_token_ is None:
            if self.current_token_ is None:
                self.current_token_ = self.get_next_token()

            self.peek_token_ = self.get_next_token()

        return self.peek_token_

    def allow_comments(self, val):
        self.allow_comments_ = val

    def allow_double_close(self, val):
        self.allow_double_close_ = val

    def get_next_token(self):
        in_comment = False

        while not self.eof:
            while self.peek_char() in [" ", "\t", "\n"]:
                self.next_char()

            if in_comment:
                if self.peek_char() == "*" and self.peek_char(1) == "/":
                    self.advance_char(2)
                    in_comment = False
                    continue

                self.advance_char()
                continue

            if self.allow_comments_ and self.peek_char() == "/":
                if self.peek_char(1) == "*":
                    self.advance_char(2)
                    in_comment = True
                    continue

                if self.peek_char(1) == "/":
                    self.get_next_line()
                    continue

            break

        if in_comment:
            raise ParseError("Reached end of file within a comment")

        start_line = self.line_number
        start_column = self.column_number
        start_cursor = self.cursor
        c = self.next_char()

        if self.eof:
            token_text = ""
        else:
            if c == "'" or c == '"':
                endc = c
                long_string = (
                    c == "'" and self.peek_char() == "'" and self.peek_char(1) == "'"
                )
                if long_string:
                    self.advance_char(2)

                while True:
                    c = self.next_char()
                    if not c:
                        break

                    if c == "\\":
                        self.next_char()
                    elif long_string:
                        if (
                            c == "'"
                            and self.peek_char() == "'"
                            and self.peek_char(1) == "'"
                        ):
                            self.advance_char(2)
                            break
                    elif c == endc:
                        break

            elif c in ["[", "]", "(", ")", ","]:
                pass

            elif c in ["{", ":"]:
                if self.peek_char() == c:
                    self.next_char()

            elif c == "}":
                if self.allow_double_close_ and self.peek_char() == c:
                    self.next_char()

            elif (
                (c == "-" or c == "+")
                and self.peek_char() == "i"
                and self.peek_char(1) == "n"
                and self.peek_char(2) == "f"
                and not re.match(r"^[a-zA-Z0-9_$]$", self.peek_char(3))
            ):
                self.advance_char(3)

            elif (
                c == "n"
                and self.peek_char() == "u"
                and self.peek_char(1) == "l"
                and self.peek_char(2) == "l"
                and self.peek_char(3) == "."
            ):
                self.advance_char(4)

                while re.match(r"^[a-zA-Z0-9_$]$", self.peek_char()):
                    self.next_char()

            elif (c >= "0" and c <= "9") or (
                c == "-" and self.peek_char() >= "0" and self.peek_char() <= "9"
            ):
                while re.match(r"^[0-9a-zA-Z.:_+-]$", self.peek_char()):
                    self.next_char()

            elif re.match(r"^[a-zA-Z_$]$", c):
                while re.match(r"^[a-zA-Z0-9_$]$", self.peek_char()):
                    self.next_char()

            elif re.match(OPERATOR_RE, c):
                while re.match(OPERATOR_RE, self.peek_char()):
                    self.next_char()

            else:
                pass

            if self.data[start_cursor] != ":":
                while self.data[self.cursor - 1] == ":":
                    self.cursor -= 1

            token_text = self.data[start_cursor : self.cursor]

        return Token(token_text, start_line, start_column)
