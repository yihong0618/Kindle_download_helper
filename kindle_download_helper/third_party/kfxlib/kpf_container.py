from __future__ import absolute_import, division, print_function, unicode_literals

import io
import os

try:
    import apsw

    have_apsw = True
except ImportError:
    import sqlite3

    have_apsw = False


from .ion import (
    IS,
    IonAnnotation,
    IonBLOB,
    IonInt,
    IonList,
    IonSExp,
    IonString,
    IonStruct,
    ion_type,
)
from .ion_binary import IonBinary
from .message_logging import log
from .original_source_epub import SourceEpub
from .python_transition import IS_PYTHON2
from .utilities import (
    ZIP_SIGNATURE,
    DataFile,
    Deserializer,
    KFXDRMError,
    bytes_to_separated_hex,
    json_deserialize,
    json_serialize,
    natural_sort_key,
    temp_filename,
)
from .yj_container import (
    CONTAINER_FORMAT_KPF,
    DRMION_SIGNATURE,
    ROOT_FRAGMENT_TYPES,
    YJContainer,
    YJFragment,
)
from .yj_symbol_catalog import SYSTEM_SYMBOL_TABLE

if IS_PYTHON2:
    from .python_transition import repr


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DEBUG = False
RETAIN_KFX_ID_ANNOT = False

RESOURCE_DIRECTORY = "resources"
DICTIONARY_RULES_FILENAME = "DictionaryRules.ion"

SQLITE_SIGNATURE = b"SQLite format 3\0"


class KpfContainer(YJContainer):
    KPF_SIGNATURE = ZIP_SIGNATURE
    KDF_SIGNATURE = SQLITE_SIGNATURE
    db_timeout = 30

    def __init__(self, symtab, datafile=None, fragments=None, book=None):
        YJContainer.__init__(self, symtab, datafile=datafile, fragments=fragments)
        self.book = book

    def deserialize(self, ignore_drm=False):
        self.ignore_drm = ignore_drm
        self.fragments.clear()

        self.kpf_datafile = self.kdf_datafile = self.kcb_datafile = self.kcb_data = (
            self.source_epub
        ) = None

        if self.datafile.is_zipfile():
            self.kpf_datafile = self.datafile

            with self.kpf_datafile.as_ZipFile() as zf:
                for info in zf.infolist():
                    ext = os.path.splitext(info.filename)[1]
                    if ext == ".kdf":
                        self.kdf_datafile = DataFile(
                            info.filename, zf.read(info), self.kpf_datafile
                        )

                    elif ext == ".kdf-journal":
                        if len(zf.read(info)) > 0:
                            raise Exception(
                                "kdf-journal is not empty in %s"
                                % self.kpf_datafile.name
                            )

                    elif ext == ".kcb":
                        self.kcb_datafile = DataFile(
                            info.filename, zf.read(info), self.kpf_datafile
                        )
                        self.kcb_data = json_deserialize(self.kcb_datafile.get_data())

            if self.kdf_datafile is None:
                raise Exception("Failed to locate KDF within %s" % self.datafile.name)

        else:
            self.kdf_datafile = self.datafile

        unwrapped_kdf_datafile = SQLiteFingerprintWrapper(self.kdf_datafile).remove()

        db_filename = (
            unwrapped_kdf_datafile.name
            if unwrapped_kdf_datafile.is_real_file and not self.book.is_netfs
            else temp_filename("kdf", unwrapped_kdf_datafile.get_data())
        )

        if have_apsw:
            if natural_sort_key(apsw.sqlitelibversion()) < natural_sort_key("3.8.2"):
                raise Exception(
                    "SQLite version 3.8.2 or later is necessary in order to use a WITHOUT ROWID table. Found version %s"
                    % apsw.sqlitelibversion()
                )

            conn = apsw.Connection(db_filename)
        else:
            if sqlite3.sqlite_version_info < (3, 8, 2):
                raise Exception(
                    "SQLite version 3.8.2 or later is necessary in order to use a WITHOUT ROWID table. Found version %s"
                    % sqlite3.sqlite_version
                )

            conn = sqlite3.connect(db_filename, KpfContainer.db_timeout)

        cursor = conn.cursor()

        sql_list = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table';"
        ).fetchall()
        schema = set([x[0] for x in sql_list])

        dictionary_index_terms = set()
        first_head_word = ""
        INDEX_INFO_SCHEMA = (
            "CREATE TABLE index_info(namespace char(256), index_name char(256), property char(40), "
            "primary key (namespace, index_name)) without rowid"
        )

        if INDEX_INFO_SCHEMA in schema:
            schema.remove(INDEX_INFO_SCHEMA)
            self.book.is_dictionary = True
            for namespace, index_name, property in cursor.execute(
                "SELECT * FROM index_info;"
            ):
                if namespace != "dictionary" or property != "yj.dictionary.term":
                    log.error(
                        "unexpected index_info: namespace=%s, index_name=%s, property=%s"
                        % (namespace, index_name, property)
                    )

                table_name = "index_%s_%s" % (namespace, index_name)
                index_schema = (
                    "CREATE TABLE %s ([%s] char(256),  id char(40), "
                    "primary key ([%s], id)) without rowid"
                ) % (table_name, property, property)

                if index_schema in schema:
                    schema.remove(index_schema)
                    num_entries = 0
                    index_words = set()
                    index_kfx_ids = set()

                    for dictionary_term, kfx_id in cursor.execute(
                        "SELECT * FROM %s;" % table_name
                    ):
                        num_entries += 1
                        dictionary_index_terms.add((dictionary_term, IS(kfx_id)))
                        index_words.add(dictionary_term)
                        index_kfx_ids.add(kfx_id)

                        if dictionary_term < first_head_word or not first_head_word:
                            first_head_word = dictionary_term

                    log.info(
                        "Dictionary %s table has %d entries with %d terms and %d definitions"
                        % (
                            table_name,
                            num_entries,
                            len(index_words),
                            len(index_kfx_ids),
                        )
                    )

                else:
                    log.error("KPF database is missing the '%s' table" % table_name)

        self.eid_symbol = {}
        KFXID_TRANSLATION_SCHEMA = "CREATE TABLE kfxid_translation(eid INTEGER, kfxid char(40), primary key(eid)) without rowid"
        if KFXID_TRANSLATION_SCHEMA in schema:
            schema.remove(KFXID_TRANSLATION_SCHEMA)
            for eid, kfx_id in cursor.execute("SELECT * FROM kfxid_translation;"):
                self.eid_symbol[eid] = self.create_local_symbol(kfx_id)

        self.element_type = {}
        FRAGMENT_PROPERTIES_SCHEMA = (
            "CREATE TABLE fragment_properties(id char(40), key char(40), value char(40), "
            "primary key (id, key, value)) without rowid"
        )
        if FRAGMENT_PROPERTIES_SCHEMA in schema:
            schema.remove(FRAGMENT_PROPERTIES_SCHEMA)
            for id, key, value in cursor.execute("SELECT * FROM fragment_properties;"):
                if key == "child":
                    pass
                elif key == "element_type":
                    self.element_type[id] = value
                else:
                    log.error(
                        "fragment_property has unknown key: id=%s key=%s value=%s"
                        % (id, key, value)
                    )

        self.max_eid_in_sections = None
        FRAGMENTS_SCHEMA = "CREATE TABLE fragments(id char(40), payload_type char(10), payload_value blob, primary key (id))"
        if FRAGMENTS_SCHEMA in schema:
            schema.remove(FRAGMENTS_SCHEMA)

            for id in ["$ion_symbol_table", "max_id"]:
                rows = cursor.execute(
                    "SELECT payload_value FROM fragments WHERE id = ? AND payload_type = 'blob';",
                    (id,),
                ).fetchall()
                if rows:
                    payload_data = self.prep_payload_blob(rows[0][0])
                    if payload_data is None:
                        pass
                    elif id == "$ion_symbol_table":
                        self.symtab.creating_yj_local_symbols = True
                        sym_import = IonBinary(self.symtab).deserialize_annotated_value(
                            payload_data,
                            expect_annotation="$ion_symbol_table",
                            import_symbols=True,
                        )
                        self.symtab.creating_yj_local_symbols = False
                        if DEBUG:
                            log.info(
                                "kdf symbol import = %s" % json_serialize(sym_import)
                            )

                        self.fragments.append(YJFragment(sym_import))
                        break
                    else:
                        max_id = IonBinary(self.symtab).deserialize_single_value(
                            payload_data
                        )
                        if DEBUG:
                            log.info("kdf max_id = %d" % max_id)

                        self.symtab.clear()
                        self.symtab.import_shared_symbol_table(
                            "YJ_symbols",
                            max_id=max_id - len(SYSTEM_SYMBOL_TABLE.symbols),
                        )
                        self.fragments.append(YJFragment(self.symtab.create_import()))

            for id, payload_type, payload_value in cursor.execute(
                "SELECT * FROM fragments;"
            ):
                ftype = id

                if payload_type == "blob":
                    payload_data = self.prep_payload_blob(payload_value)

                    if id in ["max_id", "$ion_symbol_table"]:
                        pass

                    elif payload_data is None:
                        ftype = self.element_type.get(id)

                    elif id == "max_eid_in_sections":
                        ftype = None
                        self.max_eid_in_sections = IonBinary(
                            self.symtab
                        ).deserialize_single_value(payload_data)
                        if self.book.is_dictionary:
                            pass
                        else:
                            log.warning(
                                "Unexpected max_eid_in_sections for non-dictionary: %d"
                                % self.max_eid_in_sections
                            )

                    elif not payload_data.startswith(IonBinary.SIGNATURE):
                        ftype = None
                        self.fragments.append(
                            YJFragment(
                                ftype="$417",
                                fid=self.create_local_symbol(id),
                                value=IonBLOB(payload_data),
                            )
                        )

                    elif len(payload_data) == len(IonBinary.SIGNATURE):
                        if id != "book_navigation":
                            log.warning("Ignoring empty %s fragment" % id)

                    else:
                        value = IonBinary(self.symtab).deserialize_annotated_value(
                            payload_data
                        )

                        if not isinstance(value, IonAnnotation):
                            log.error(
                                "KDF fragment id=%s is missing annotation: %s"
                                % (id, repr(value))
                            )
                            continue
                        elif (
                            len(value.annotations) == 2
                            and value.annotations[1] == "$608"
                        ):
                            pass
                        elif len(value.annotations) > 1:
                            log.error(
                                "KDF fragment should have one annotation: %s"
                                % repr(value)
                            )

                        ftype = value.annotations[0]

                        if (
                            ftype in ROOT_FRAGMENT_TYPES
                        ):  # shortcut when symbol table unavailable
                            fid = None
                        else:
                            fid = self.create_local_symbol(id)

                        self.fragments.append(
                            YJFragment(
                                ftype=ftype,
                                fid=fid,
                                value=self.deref_kfx_ids(value.value),
                            )
                        )

                elif payload_type == "path":
                    ftype = "$417"

                    resource_data = self.get_resource_data(
                        self.prep_payload_blob(payload_value).decode("utf8")
                    )
                    if resource_data is not None:
                        self.fragments.append(
                            YJFragment(
                                ftype=ftype,
                                fid=self.create_local_symbol(id),
                                value=IonBLOB(resource_data),
                            )
                        )

                else:
                    log.error(
                        "Unexpected KDF payload_type=%s, id=%s, value=%d bytes"
                        % (payload_type, id, len(payload_value))
                    )

        else:
            log.error("KPF database is missing the 'fragments' table")

        GC_FRAGMENT_PROPERTIES_SCHEMA = (
            "CREATE TABLE gc_fragment_properties(id varchar(40), key varchar(40), "
            "value varchar(40), primary key (id, key, value)) without rowid"
        )
        if GC_FRAGMENT_PROPERTIES_SCHEMA in schema:
            schema.remove(GC_FRAGMENT_PROPERTIES_SCHEMA)

        GC_REACHABLE_SCHEMA = (
            "CREATE TABLE gc_reachable(id varchar(40), primary key (id)) without rowid"
        )
        if GC_REACHABLE_SCHEMA in schema:
            schema.remove(GC_REACHABLE_SCHEMA)

        CAPABILITIES_SCHEMA = "CREATE TABLE capabilities(key char(20), version smallint, primary key (key, version)) without rowid"
        if CAPABILITIES_SCHEMA in schema:
            schema.remove(CAPABILITIES_SCHEMA)
            capabilities = cursor.execute("SELECT * FROM capabilities;").fetchall()

            if capabilities:
                format_capabilities = [
                    IonStruct(IS("$492"), key, IS("version"), version)
                    for key, version in capabilities
                ]
                self.fragments.append(
                    YJFragment(ftype="$593", value=format_capabilities)
                )
        else:
            log.error("KPF database is missing the 'capabilities' table")

        if len(schema) > 0:
            for s in list(schema):
                log.error("Unexpected KDF database schema: %s" % s)

        cursor.close()
        conn.close()

        self.book.is_kpf_prepub = True
        book_metadata_fragment = self.fragments.get("$490")
        if book_metadata_fragment is not None:
            for cm in book_metadata_fragment.value.get("$491", {}):
                if cm.get("$495", "") == "kindle_title_metadata":
                    for kv in cm.get("$258", []):
                        if kv.get("$492", "") in [
                            "ASIN",
                            "asset_id",
                            "cde_content_type",
                            "content_id",
                        ]:
                            self.book.is_kpf_prepub = False
                            break
                    break

        self.fragments.append(
            YJFragment(
                ftype="$270",
                value=IonStruct(
                    IS("$587"), "", IS("$588"), "", IS("$161"), CONTAINER_FORMAT_KPF
                ),
            )
        )

        if self.kcb_datafile is not None and self.kcb_data is not None:
            source_path = self.kcb_data.get("metadata", {}).get("source_path")
            if source_path and os.path.splitext(source_path)[1] in [".epub", ".zip"]:
                epub_file = self.get_kpf_file(source_path)
                if epub_file is not None:
                    zip_file = io.BytesIO(epub_file.get_data())
                    self.source_epub = SourceEpub(zip_file)
                    zip_file.close()

    def prep_payload_blob(self, data):
        data = io.BytesIO(data).read()

        if not data.startswith(DRMION_SIGNATURE):
            return data

        if self.ignore_drm:
            return None

        raise KFXDRMError("Book container has DRM and cannot be converted")

    def create_local_symbol(self, symbol):
        return self.book.create_local_symbol(symbol)

    def get_resource_data(self, filename, report_missing=True):
        try:
            resource_datafile = self.kdf_datafile.relative_datafile(filename)
            return resource_datafile.get_data()
        except Exception:
            if report_missing:
                log.error("Missing resource in KPF: %s" % filename)

            return None

    def get_kpf_file(self, filename, report_missing=True):
        try:
            return self.kcb_datafile.relative_datafile(filename)
        except Exception:
            if report_missing:
                log.error("Missing file in KPF: %s" % filename)

            return None

    def deref_kfx_ids(self, data):
        def process(data):
            data_type = ion_type(data)

            if data_type is IonAnnotation:
                if data.is_annotation("$598"):
                    val = data.value
                    val_type = ion_type(val)

                    if val_type is IonString:
                        return self.create_local_symbol(val)
                    elif val_type is IonInt:
                        value = self.eid_symbol.get(val)
                        if value is not None:
                            return value
                        else:
                            log.error("Undefined kfx_id annotation eid: %d" % val)
                    else:
                        log.error(
                            "Unexpected data type for kfx_id annotation: %s" % val_type
                        )

                    return val

                process(data.value)

            if data_type is IonList or data_type is IonSExp:
                for i, val in enumerate(list(data)):
                    new_val = process(val)
                    if new_val is not None:
                        data.pop(i)
                        data.insert(i, new_val)

            if data_type is IonStruct:
                for key, val in data.items():
                    new_val = process(val)
                    if new_val is not None:
                        data[key] = new_val

            return None

        if not RETAIN_KFX_ID_ANNOT:
            process(data)

        return data


class SQLiteFingerprintWrapper(object):
    FINGERPRINT_OFFSET = 1024
    FINGERPRINT_RECORD_LEN = 1024
    DATA_RECORD_LEN = 1024
    DATA_RECORD_COUNT = 1024

    FINGERPRINT_SIGNATURE = b"\xfa\x50\x0a\x5f"

    def __init__(self, datafile):
        self.datafile = datafile

    def remove(self):
        data = self.datafile.get_data()

        if (
            len(data) < self.FINGERPRINT_OFFSET + self.FINGERPRINT_RECORD_LEN
            or data[
                self.FINGERPRINT_OFFSET : self.FINGERPRINT_OFFSET
                + len(self.FINGERPRINT_SIGNATURE)
            ]
            != self.FINGERPRINT_SIGNATURE
        ):
            return self.datafile

        fingerprint_count = 0
        data_offset = self.FINGERPRINT_OFFSET

        while len(data) >= data_offset + self.FINGERPRINT_RECORD_LEN:
            fingerprint = Deserializer(
                data[data_offset : data_offset + self.FINGERPRINT_RECORD_LEN]
            )

            signature = fingerprint.extract(4)
            if signature != self.FINGERPRINT_SIGNATURE:
                log.error(
                    "Unexpected fingerprint %d signature: %s"
                    % (fingerprint_count, bytes_to_separated_hex(signature))
                )
                return self.datafile

            data = (
                data[:data_offset] + data[data_offset + self.FINGERPRINT_RECORD_LEN :]
            )
            fingerprint_count += 1
            data_offset += self.DATA_RECORD_LEN * self.DATA_RECORD_COUNT

        log.info("Removed %d KDF SQLite file fingerprint(s)" % fingerprint_count)

        return DataFile(self.datafile.name + "-unwrapped", data)
