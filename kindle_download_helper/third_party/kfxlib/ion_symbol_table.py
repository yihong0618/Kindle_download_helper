from __future__ import absolute_import, division, print_function, unicode_literals

import re

from .ion import (
    IS,
    IonAnnotation,
    IonStruct,
    IonSymbol,
    ion_type,
    isstring,
    unannotated,
)
from .message_logging import log
from .python_transition import IS_PYTHON2
from .utilities import list_symbols, quote_name, type_name
from .yj_symbol_catalog import SYSTEM_SYMBOL_TABLE, YJ_SYMBOLS, IonSharedSymbolTable

if IS_PYTHON2:
    from .python_transition import repr


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"

DEBUG = False
REPORT_ALL_USED_SYMBOLS = False


class SymbolTableCatalog(object):
    def __init__(self, add_global_shared_symbol_tables=False):
        self.shared_symbol_tables = {}
        self.clear()

        if add_global_shared_symbol_tables:
            self.add_global_shared_symbol_tables()

    def clear(self):
        self.shared_symbol_tables.clear()
        self.add_shared_symbol_table(SYSTEM_SYMBOL_TABLE)

    def add_global_shared_symbol_tables(self):
        self.add_shared_symbol_table(YJ_SYMBOLS)

    def add_shared_symbol_table(self, shared_symbol_table):
        self.shared_symbol_tables[
            (shared_symbol_table.name, shared_symbol_table.version)
        ] = shared_symbol_table

        if (
            shared_symbol_table.name not in self.shared_symbol_tables
            or shared_symbol_table.version
            >= self.shared_symbol_tables[(shared_symbol_table.name, None)].version
        ):
            self.shared_symbol_tables[(shared_symbol_table.name, None)] = (
                shared_symbol_table
            )

    def create_shared_symbol_table(self, symbol_table_data):
        self.add_shared_symbol_table(
            IonSharedSymbolTable(
                symbol_table_data["name"],
                symbol_table_data["version"] if "version" in symbol_table_data else 1,
                symbol_table_data["symbols"] if "symbols" in symbol_table_data else [],
            )
        )

    def get_shared_symbol_table(self, name, version=None):
        return self.shared_symbol_tables.get(
            (name, version)
        ) or self.shared_symbol_tables.get((name, None))


global_catalog = SymbolTableCatalog(add_global_shared_symbol_tables=True)


class SymbolTableImport(object):
    def __init__(self, name, version, max_id):
        self.name = name
        self.version = version
        self.max_id = max_id


class LocalSymbolTable(object):
    def __init__(
        self,
        initial_import=None,
        context="",
        ignore_undef=False,
        catalog=global_catalog,
    ):
        self.context = context
        self.ignore_undef = ignore_undef
        self.catalog = catalog

        self.undefined_ids = set()
        self.undefined_symbols = set()
        self.unexpected_used_symbols = set()
        self.reported = False
        self.clear()
        self.set_translation(None)

        if initial_import:
            self.import_shared_symbol_table(initial_import)

    def clear(self):
        self.table_imports = []
        self.symbols = []
        self.id_of_symbol = {}
        self.symbol_of_id = {}
        self.unexpected_ids = set()
        self.creating_local_symbols = False
        self.creating_yj_local_symbols = False

        self.import_symbols(self.catalog.get_shared_symbol_table("$ion").symbols)
        self.local_min_id = len(self.symbols) + 1

    def create(self, symbol_table_data, yj_local_symbols=False):
        if "imports" in symbol_table_data:
            imports = symbol_table_data["imports"]
            if ion_type(imports) is IonSymbol:
                if imports != "$ion_symbol_table":
                    raise Exception("Unexpected imports value: %s" % imports)
            else:
                self.clear()

                for sym_import in imports:
                    self.import_shared_symbol_table(
                        sym_import["name"],
                        sym_import.get("version") or 1,
                        sym_import.get("max_id"),
                    )
        else:
            self.clear()

        symbol_list = (
            unannotated(symbol_table_data["symbols"])
            if "symbols" in symbol_table_data
            else []
        )

        self.creating_local_symbols = True
        self.import_symbols(symbol_list)

        if "max_id" in symbol_table_data:
            expected_max_id = symbol_table_data["max_id"]
            if expected_max_id is not None and expected_max_id != len(self.symbols):
                log.error(
                    "Symbol table max_id after import expected %d, found %d"
                    % (expected_max_id, len(self.symbols))
                )

    def import_shared_symbol_table(self, name, version=None, max_id=None):
        if DEBUG:
            log.debug(
                "Importing ion symbol table %s version %s max_id %s"
                % (quote_name(name), version, max_id)
            )

        if self.creating_local_symbols:
            raise Exception(
                "Importing shared symbols after local symbols have been created"
            )

        if name == "$ion":
            return

        symbol_table = self.catalog.get_shared_symbol_table(name, version)

        if symbol_table is None:
            log.error("Imported shared symbol table %s is unknown" % name)
            symbol_table = IonSharedSymbolTable(name=name, version=version)

        if version is None:
            version = symbol_table.version
        elif symbol_table.version != version:
            if max_id is None:
                log.error(
                    "Import version %d of shared symbol table %s without max_id, but have version %d"
                    % (version, name, symbol_table.version)
                )
            else:
                log.warning(
                    "Import version %d of shared symbol table %s, but have version %d"
                    % (version, name, symbol_table.version)
                )

        table_len = len(symbol_table.symbols)

        if max_id is None:
            max_id = table_len

        if max_id < 0:
            raise Exception(
                "Import symbol table %s version %d max_id %d is invalid"
                % (name, version, max_id)
            )

        self.table_imports.append(SymbolTableImport(name, version, max_id))

        if max_id < table_len:
            symbol_list = symbol_table.symbols[:max_id]
        elif max_id > table_len:
            if table_len > 0:
                prior_len = len(self.symbols)
                log.warning(
                    "Import symbol table %s version %d max_id %d(+%d=%d) exceeds known table size %d(+%d=%d)"
                    % (
                        name,
                        version,
                        max_id,
                        prior_len,
                        max_id + prior_len,
                        table_len,
                        prior_len,
                        table_len + prior_len,
                    )
                )

            symbol_list = symbol_table.symbols + ([None] * (max_id - table_len))
        else:
            symbol_list = symbol_table.symbols

        self.import_symbols(symbol_list)
        self.local_min_id = len(self.symbols) + 1

    def import_symbols(self, symbols):
        for symbol in symbols:
            symbol = unannotated(symbol)

            if symbol is not None:
                if not isstring(symbol):
                    log.error(
                        "imported symbol %s is type %s, treating as null"
                        % (symbol, type_name(symbol))
                    )
                    symbol = None

            self.add_symbol(symbol)

    def create_local_symbol(self, symbol):
        self.creating_local_symbols = True

        if symbol not in self.id_of_symbol:
            self.add_symbol(symbol)

        return IonSymbol(symbol)

    def add_symbol(self, symbol):
        if symbol is None:
            self.symbols.append(None)
            return -1

        if not isstring(symbol):
            raise Exception(
                "symbol %s is type %s, not string" % (symbol, type_name(symbol))
            )

        if len(symbol) == 0:
            raise Exception("symbol has zero length")

        expected = True

        if not self.creating_local_symbols:
            if symbol.endswith("?"):
                symbol = symbol[:-1]
                expected = False
            elif REPORT_ALL_USED_SYMBOLS:
                expected = False

        self.symbols.append(symbol)

        if symbol not in self.id_of_symbol:
            symbol_id = len(self.symbols)
            self.id_of_symbol[symbol] = symbol_id
            self.symbol_of_id[symbol_id] = symbol
        else:
            self.symbol_of_id[len(self.symbols)] = symbol
            symbol_id = self.id_of_symbol[symbol]
            log.error("Symbol %s already exists with id %d" % (symbol, symbol_id))

        if not expected:
            self.unexpected_ids.add(symbol_id)

        return symbol_id

    def get_symbol(self, symbol_id):
        if not isinstance(symbol_id, int):
            raise Exception(
                "get_symbol: symbol id must be integer not %s: %s"
                % (type_name(symbol_id), repr(symbol_id))
            )

        symbol = self.symbol_of_id.get(symbol_id)

        if symbol is None:
            symbol = "$%d" % symbol_id
            self.undefined_ids.add(symbol_id)

        if symbol_id in self.unexpected_ids:
            self.unexpected_used_symbols.add(symbol)

        return IonSymbol(symbol)

    def get_id(self, ion_symbol, used=True):
        if not isinstance(ion_symbol, IonSymbol):
            raise Exception(
                "get_id: symbol must be IonSymbol not %s: %s"
                % (type_name(ion_symbol), repr(ion_symbol))
            )

        symbol = ion_symbol.tostring()

        if symbol.startswith("$") and re.match(r"^\$[0-9]+$", symbol):
            symbol_id = int(symbol[1:])

            if symbol_id not in self.symbol_of_id:
                self.undefined_ids.add(symbol_id)
        else:
            symbol_id = self.id_of_symbol.get(symbol)

            if symbol_id is None:
                if used:
                    self.undefined_symbols.add(symbol)

                symbol_id = 0

        if used and symbol_id in self.unexpected_ids:
            self.unexpected_used_symbols.add(symbol)

        return symbol_id

    def is_shared_symbol(self, ion_symbol):
        symbol_id = self.get_id(ion_symbol, used=False)
        return symbol_id > 0 and symbol_id < self.local_min_id

    def is_local_symbol(self, ion_symbol):
        return self.get_id(ion_symbol, used=False) >= self.local_min_id

    def replace_local_symbols(self, new_symbols):
        self.discard_local_symbols()
        self.import_symbols(new_symbols)

    def get_local_symbols(self):
        return self.symbols[self.local_min_id - 1 :]

    def discard_local_symbols(self):
        symbol_id = self.local_min_id
        for symbol in self.symbols[self.local_min_id - 1 :]:
            self.id_of_symbol.pop(symbol)
            self.symbol_of_id.pop(symbol_id)
            symbol_id += 1

        self.symbols = self.symbols[: self.local_min_id - 1]

    def create_import(self, imports_only=False):
        if not self.symbols:
            return None

        symbol_table_data = IonStruct()

        if not imports_only:
            symbol_table_data[IS("max_id")] = len(self.symbols)

        symbol_table_data[IS("imports")] = [
            IonStruct(
                IS("name"),
                table_import.name,
                IS("version"),
                table_import.version,
                IS("max_id"),
                table_import.max_id,
            )
            for table_import in self.table_imports
        ]

        if not imports_only:
            symbol_table_data[IS("symbols")] = self.symbols[self.local_min_id - 1 :]

        return IonAnnotation([IS("$ion_symbol_table")], symbol_table_data)

    def set_translation(self, alt_symbol_table):
        self.import_translate = {}
        self.export_translate = {}

        if alt_symbol_table is None:
            return

        offset = len(self.catalog.get_shared_symbol_table("$ion").symbols) + 1

        for table_import in self.table_imports:
            if table_import.name == alt_symbol_table.name:
                orig_symbol_table = self.catalog.get_shared_symbol_table(
                    table_import.name, table_import.version
                )
                for idx in range(
                    max(len(orig_symbol_table.symbols), len(alt_symbol_table.symbols))
                ):
                    have_orig = idx < len(orig_symbol_table.symbols)
                    have_alt = idx < len(alt_symbol_table.symbols)

                    orig_symbol = (
                        orig_symbol_table.symbols[idx]
                        if have_orig
                        else "$%d" % (idx + offset)
                    )
                    if orig_symbol.endswith("?"):
                        orig_symbol = orig_symbol[:-1]

                    alt_symbol = (
                        alt_symbol_table.symbols[idx]
                        if have_alt
                        else "$%d" % (idx + offset)
                    )

                    if have_alt:
                        self.import_translate[alt_symbol] = orig_symbol

                    if have_orig:
                        self.export_translate[orig_symbol] = alt_symbol

                break

            offset += table_import.max_id

    def __repr__(self):
        return "symbols: %s; id_of_symbol %s; symbol_of_id %s" % (
            repr(self.symbols),
            repr(self.id_of_symbol),
            repr(self.symbol_of_id),
        )

    def report(self):
        if self.reported:
            return

        context = ("%s: " % self.context) if self.context else ""

        if self.unexpected_used_symbols:
            log.error(
                "%sUnexpected Ion symbols used: %s"
                % (context, list_symbols(self.unexpected_used_symbols))
            )

        if self.undefined_symbols and not self.ignore_undef:
            log.error(
                "%sUndefined Ion symbols found: %s"
                % (
                    context,
                    ", ".join([quote_name(s) for s in sorted(self.undefined_symbols)]),
                )
            )

        if self.undefined_ids:
            log.error(
                "%sUndefined Ion symbol IDs found: %s"
                % (context, list_symbols(self.undefined_ids))
            )

        self.reported = True
