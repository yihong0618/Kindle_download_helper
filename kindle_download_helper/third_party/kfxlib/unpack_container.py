from __future__ import absolute_import, division, print_function, unicode_literals

import io
import posixpath
import zipfile

from .ion import IonAnnotation, IonBLOB
from .ion_text import IonText
from .message_logging import log
from .utilities import (
    EXTS_OF_MIMETYPE,
    DataFile,
    font_file_ext,
    image_file_ext,
    json_serialize,
    type_name,
)
from .yj_container import YJContainer, YJFragment
from .yj_structure import SYMBOL_FORMATS

__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


class IonTextContainer(YJContainer):
    def deserialize(self, ignore_drm=False):
        self.fragments.clear()
        for annot in IonText(self.symtab).deserialize_multiple_values(
            self.datafile.get_data(), import_symbols=True
        ):
            if not isinstance(annot, IonAnnotation):
                raise Exception(
                    "deserialize kfx ion text expected IonAnnotation but found %s"
                    % type_name(annot)
                )

            self.fragments.append(YJFragment(annot))

    def serialize(self):
        return IonText(self.symtab).serialize_multiple_values(self.get_fragments())


class ZipUnpackContainer(YJContainer):
    ADDED_EXT_FLAG_CHAR = "."

    def deserialize(self, ignore_drm=False):
        with self.datafile.as_ZipFile() as zf:
            for info in zf.infolist():
                if info.filename == "book.ion":
                    IonTextContainer(
                        self.symtab,
                        datafile=DataFile(info.filename, data=zf.read(info)),
                        fragments=self.fragments,
                    ).deserialize()
                    break
            else:
                raise Exception("book.ion file missing from ZipUnpackContainer")

            fonts = set()
            for fragment in self.fragments:
                if fragment.ftype == "$262":
                    fonts.add(fragment.value.get("$165"))

            for info in zf.infolist():
                if info.filename != "book.ion" and not info.filename.endswith("/"):
                    fn, ext = posixpath.splitext(info.filename)

                    fid = (
                        fn[:-1]
                        if ext and fn.endswith(self.ADDED_EXT_FLAG_CHAR)
                        else info.filename
                    )

                    self.fragments.append(
                        YJFragment(
                            ftype=("$418" if fid in fonts else "$417"),
                            fid=fid,
                            value=IonBLOB(zf.read(info)),
                        )
                    )

    def serialize(self):
        desired_extension = {}
        for fragment in self.fragments.get_all("$164"):
            location = fragment.value.get("$165", "")
            extension = posixpath.splitext(location)[1]

            if not extension:
                format = fragment.value.get("$161")
                if format in SYMBOL_FORMATS:
                    extension = "." + SYMBOL_FORMATS[format]

                if extension in ["", ".pobject"]:
                    mime = fragment.value.get("$162")

                    if mime in EXTS_OF_MIMETYPE and mime != "figure":
                        extension = EXTS_OF_MIMETYPE[mime][0]

            if extension:
                if location:
                    desired_extension[location] = extension

                if "$636" in fragment.value:
                    for tile_row in fragment.value["$636"]:
                        for tile_location in tile_row:
                            desired_extension[tile_location] = extension

        zfile = io.BytesIO()

        with zipfile.ZipFile(zfile, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "book.ion",
                IonTextContainer(
                    self.symtab, fragments=self.fragments.filtered(omit_resources=True)
                ).serialize(),
            )

            for ftype in ["$417", "$418"]:
                for fragment in self.fragments.get_all(ftype):
                    fn = fragment.fid.tostring()

                    if not posixpath.splitext(fn)[1]:
                        if ftype == "$417":
                            if fn in desired_extension:
                                fn += self.ADDED_EXT_FLAG_CHAR + desired_extension[fn]
                            else:
                                extension = image_file_ext(fragment.value)
                                if extension:
                                    fn += self.ADDED_EXT_FLAG_CHAR + extension
                        else:
                            extension = font_file_ext(fragment.value)
                            if extension:
                                fn += self.ADDED_EXT_FLAG_CHAR + extension

                    zf.writestr(fn, bytes(fragment.value))

        data = zfile.getvalue()
        zfile.close()

        return data


class JsonContentContainer(object):
    VERSION = "1.1"
    TYPE_TEXT = 1
    TYPE_IMAGE = 2
    TYPE_HTML = 8

    def __init__(self, book):
        self.book = book

    def serialize(self):
        content_pos_info = self.book.collect_content_position_info()
        data = []
        next_pid = 0

        for chunk in content_pos_info:
            if chunk.pid != next_pid:
                log.error(
                    "next PID is %d but expected %d: %s"
                    % (chunk.pid, next_pid, repr(chunk))
                )
                next_pid = chunk.pid

            if chunk.text is not None:
                if len(chunk.text) != chunk.length:
                    log.error(
                        "chunk length %d but have %d characters: %s"
                        % (chunk.length, len(chunk.text), repr(chunk))
                    )

                entry = {}
                entry["content"] = chunk.text
                entry["position"] = chunk.pid
                entry["type"] = self.TYPE_TEXT
                data.append(entry)
            elif chunk.image_resource is not None:
                if chunk.length != 1:
                    log.error(
                        "chunk length %d for image: %s" % (chunk.length, repr(chunk))
                    )

                entry = {}
                entry["content"] = chunk.image_resource
                entry["position"] = chunk.pid
                entry["type"] = self.TYPE_IMAGE
                data.append(entry)

            next_pid += chunk.length

        content = {"data": data, "version": self.VERSION}
        return json_serialize(content, sort_keys=True, indent=2).encode("utf-8")
