from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import functools

from .ion import IonAnnotation, IonAnnots, IonBLOB, IonList, IonSymbol, ion_type
from .python_transition import IS_PYTHON2
from .utilities import list_symbols, natural_sort_key, type_name

if IS_PYTHON2:
    from .python_transition import repr, str


__license__ = "GPL v3"
__copyright__ = "2016-2022, John Howell <jhowell@acm.org>"


DRMION_SIGNATURE = b"\xeaDRMION\xee"

CONTAINER_FORMAT_KPF = "KPF"
CONTAINER_FORMAT_KFX_MAIN = "KFX main"
CONTAINER_FORMAT_KFX_METADATA = "KFX metadata"
CONTAINER_FORMAT_KFX_ATTACHABLE = "KFX attachable"


RAW_FRAGMENT_TYPES = {"$418", "$417"}


PREFERED_FRAGMENT_TYPE_ORDER = [
    "$ion_symbol_table",
    "$270",
    "$593",
    "$585",
    "$490",
    "$258",
    "$538",
    "$389",
    "$390",
    "$260",
    "$259",
    "$608",
    "$145",
    "$756",
    "$692",
    "$157",
    "$391",
    "$266",
    "$394",
    "$264",
    "$265",
    "$550",
    "$609",
    "$621",
    "$611",
    "$610",
    "$597",
    "$267",
    "$387",
    "$395",
    "$262",
    "$164",
    "$418",
    "$417",
    "$419",
]


ROOT_FRAGMENT_TYPES = {
    "$ion_symbol_table",
    "$270",
    "$490",
    "$389",
    "$419",
    "$585",
    "$538",
    "$262",
    "$593",
    "$550",
    "$258",
    "$265",
    "$264",
    "$395",
    "$390",
    "$621",
    "$611",
}


SINGLETON_FRAGMENT_TYPES = ROOT_FRAGMENT_TYPES - {
    "$270",
    "$262",
    "$593",
}


REQUIRED_BOOK_FRAGMENT_TYPES = {
    "$ion_symbol_table",
    "$270",
    "$490",
    "$389",
    "$419",
    "$538",
    "$550",
    "$258",
    "$265",
    "$264",
    "$611",
}


ALLOWED_BOOK_FRAGMENT_TYPES = {
    "$266",
    "$597",
    "$418",
    "$417",
    "$394",
    "$145",
    "$585",
    "$610",
    "$164",
    "$262",
    "$593",
    "$391",
    "$692",
    "$387",
    "$395",
    "$756",
    "$260",
    "$267",
    "$390",
    "$609",
    "$259",
    "$608",
    "$157",
    "$621",
}


KNOWN_FRAGMENT_TYPES = REQUIRED_BOOK_FRAGMENT_TYPES | ALLOWED_BOOK_FRAGMENT_TYPES


CONTAINER_FRAGMENT_TYPES = [
    "$270",
    "$593",
    "$ion_symbol_table",
    "$419",
]


class YJContainer(object):
    def __init__(self, symtab, datafile=None, fragments=None):
        self.symtab = symtab
        self.datafile = datafile
        self.fragments = YJFragmentList() if fragments is None else fragments

    def get_fragments(self):
        return self.fragments


@functools.total_ordering
class YJFragmentKey(IonAnnots):
    def __new__(cls, arg=None, ftype=None, fid=None, annot=None):
        if arg is not None:
            raise Exception("YJFragmentKey initializer missing keyword")

        if annot is not None:
            return IonAnnots.__new__(cls, tuple(annot))

        if fid is None:
            return IonAnnots.__new__(cls, [IonSymbol(ftype)])

        if ftype is None:
            return IonAnnots.__new__(cls, [IonSymbol(fid)])

        return IonAnnots.__new__(cls, [IonSymbol(fid), IonSymbol(ftype)])

    def sort_key(self):
        return (
            (
                PREFERED_FRAGMENT_TYPE_ORDER.index(self.ftype)
                if self.ftype in PREFERED_FRAGMENT_TYPE_ORDER
                else len(PREFERED_FRAGMENT_TYPE_ORDER)
            ),
            natural_sort_key(self.fid),
        )

    def __eq__(self, other):
        if isinstance(other, YJFragment):
            return self == other.annotations

        if isinstance(other, YJFragmentKey):
            return tuple(self) == tuple(other)

        raise Exception("YJFragmentKey __eq__: comparing with %s" % type_name(other))

    def __lt__(self, other):
        if isinstance(other, YJFragment):
            return self < other.annotations

        if isinstance(other, YJFragmentKey):
            return self.sort_key() < other.sort_key()

        raise Exception("YJFragmentKey __lt__: comparing with %s" % type_name(other))

    def __hash__(self):
        return hash(tuple(self))

    @property
    def fid(self):
        return self[0]

    @fid.setter
    def fid(self, value):
        raise Exception("Attempt to modify YJFragmentKey fid")

    @property
    def ftype(self):
        return self[-1]

    @ftype.setter
    def ftype(self, value):
        raise Exception("Attempt to modify YJFragmentKey ftype")


@functools.total_ordering
class YJFragment(IonAnnotation):
    def __init__(self, arg=None, ftype=None, fid=None, value=None):
        if isinstance(arg, YJFragmentKey):
            IonAnnotation.__init__(self, arg, value)
        elif isinstance(arg, IonAnnotation):
            IonAnnotation.__init__(
                self, YJFragmentKey(annot=arg.annotations), arg.value
            )
        else:
            IonAnnotation.__init__(self, YJFragmentKey(ftype=ftype, fid=fid), value)

    def __hash__(self):
        return hash(self.annotations)

    def __eq__(self, other):
        if isinstance(other, YJFragment):
            return self.annotations == other.annotations

        if isinstance(other, YJFragmentKey):
            return self.annotations == other

        raise Exception("YJFragment __eq__: comparing with %s" % type_name(other))

    def __lt__(self, other):
        if isinstance(other, YJFragment):
            return self.annotations < other.annotations

        if isinstance(other, YJFragmentKey):
            return self.annotations < other

        raise Exception("YJFragment __lt__: comparing with %s" % type_name(other))

    @property
    def fid(self):
        return self.annotations[0]

    @fid.setter
    def fid(self, value):
        raise Exception("Attempt to modify YJFragment fid")

    @property
    def ftype(self):
        return self.annotations[-1]

    @ftype.setter
    def ftype(self, value):
        raise Exception("Attempt to modify YJFragment ftype")


class YJFragmentList(IonList):
    def __init__(self, *args):
        IonList.__init__(self, *args)
        self.yj_dirty = True
        self.yj_ftype_index = collections.defaultdict(list)
        self.yj_fragment_index = collections.defaultdict(list)

    def yj_rebuild_index(self):
        self.yj_ftype_index.clear()
        self.yj_fragment_index.clear()

        for f in self:
            if not isinstance(f, YJFragment):
                raise Exception(
                    "YJFragmentList contains non-YJFragment: %s" % type_name(f)
                )

            self.yj_ftype_index[f.ftype].append(f)
            self.yj_fragment_index[f].append(f)

        self.yj_dirty = False

    def get_all(self, ftype=None):
        return self.get(ftype=ftype, all=True)

    def get(self, ftype=None, default=None, fid=None, first=False, all=False):
        key = ftype

        if isinstance(key, int):
            return list.__getitem__(self, key)

        if self.yj_dirty:
            self.yj_rebuild_index()

        if isinstance(key, YJFragmentKey):
            matches = self.yj_fragment_index.get(key, [])
        elif fid is not None:
            key = YJFragmentKey(ftype=ftype, fid=fid)
            matches = self.yj_fragment_index.get(key, [])
        else:
            matches = self.yj_ftype_index.get(ftype, [])

        if all:
            return list(matches)

        if not matches:
            return default

        if len(matches) > 1 and not first:
            raise KeyError(
                "YJFragmentList get has multiple matches for %s: %s"
                % (repr(key), list_symbols(matches))
            )

        return matches[0]

    def __getitem__(self, key):
        fragment = self.get(key)
        if fragment is None:
            raise KeyError("YJFragmentList item is missing: %s" % repr(key))

        return fragment

    def append(self, value):
        if not isinstance(value, YJFragment):
            raise Exception(
                "YJFragmentList append non-YJFragment: %s" % type_name(value)
            )

        IonList.append(self, value)
        self.yj_dirty = True

    def extend(self, values):
        if not isinstance(values, YJFragmentList):
            raise Exception(
                "YJFragmentList extend non-YJFragmentList: %s" % type_name(values)
            )

        IonList.extend(self, values)
        self.yj_dirty = True

    def remove(self, value):
        if not self.discard(value):
            raise KeyError("YJFragmentList remove, item is missing: %s" % str(value))

    def discard(self, value):
        if not isinstance(value, YJFragment):
            raise Exception(
                "YJFragmentList remove non-YJFragment: %s" % type_name(value)
            )

        for i, f in enumerate(self):
            if f is value:
                self.pop(i)
                self.yj_dirty = True
                return True

        return False

    def ftypes(self):
        if self.yj_dirty:
            self.yj_rebuild_index()

        return set(self.yj_ftype_index.keys())

    def filtered(self, omit_resources=False, omit_large_blobs=False):
        if not (omit_resources or omit_large_blobs):
            return self

        filtered_fragments = YJFragmentList()
        for fragment in list(self):
            if fragment.ftype in RAW_FRAGMENT_TYPES:
                if omit_resources:
                    continue

                if (
                    omit_large_blobs
                    and ion_type(fragment.value) is IonBLOB
                    and fragment.value.is_large()
                ):
                    fragment = YJFragment(
                        ftype=fragment.ftype,
                        fid=fragment.fid,
                        value=repr(fragment.value),
                    )

            filtered_fragments.append(fragment)

        return filtered_fragments

    def clear(self):
        del self[:]
