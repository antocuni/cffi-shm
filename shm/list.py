import cffi
import _cffi_backend
from shm.sharedmem import sharedmem
from shm.converter import Dummy
from shm.util import ctype_pointer_to, cffi_typeof, cffi_is_pointer
from shm.pyffi import AbstractGenericType

listffi = cffi.FFI()

listffi.cdef("""
    typedef struct {
        long size;   // number of allocated items
        long length; // number of actually used items
        long offset;  // this is used only by deque
        void* items;
    } List;
""")

class ListType(AbstractGenericType):

    def __init__(self, pyffi, itemtype, listclass=None, immutable=False):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.itemtype = itemtype
        self.itemtype_ptr = ctype_pointer_to(self.ffi, itemtype)
        self.itemtype_is_pointer = cffi_is_pointer(self.ffi, itemtype)
        self.__immutable__ = immutable
        if immutable:
            defaultclass = ImmutableList
            self.__fieldspec__ = self.make_fieldspec()
        else:
            defaultclass = FixedSizeList
            self.__fieldspec__ = None
        self.listclass = listclass or defaultclass
        #
        # if it's a primitive we do not need a converter, because the
        # conversion is already performed automatically by typeditems, which
        # is a typed cffi array
        if cffi_typeof(self.ffi, itemtype).kind == 'primitive':
            self.conv = Dummy(self.ffi, itemtype)
        else:
            self.conv = pyffi.get_converter(itemtype)

    def make_fieldspec(self):
        from shm.libcfu import cfuhash, FieldSpec
        itemspec = FieldSpec.for_pointer(self.pyffi, self.itemtype)
        spec = FieldSpec(listffi, 'List')
        # note that we are deliberatly ignoring the field 'size': we do not
        # care how many items we have preallocated for doing comparisons
        spec.add('length', cfuhash.primitive, listffi.sizeof('long'))
        spec.add('offset', cfuhash.primitive, listffi.sizeof('long'))
        spec.add('items', cfuhash.array, self.ffi.sizeof(self.itemtype),
                 length_offset = listffi.offsetof('List', 'length'),
                 fieldspec = itemspec)
        return spec

    def __repr__(self):
        return '<shm type list [%s]>' % self.itemtype

    def __call__(self, items=None, root=True):
        with sharedmem.gc_disabled:
            ptr = sharedmem.new(listffi, 'List*', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            ptr.items = sharedmem.new_array(self.ffi, self.itemtype, 2)
            ptr.size = 2
            ptr.length = 0
            ptr.offset = 0
        lst = self.listclass.from_pointer(self, ptr)
        lst._setcontent(items)
        return lst

    def from_pointer(self, ptr):
        ptr = listffi.cast('List*', ptr)
        return self.listclass.from_pointer(self, ptr)

class ImmutableList(object):

    def __new__(self, *args, **kwds):
        raise NotImplementedError

    @classmethod
    def from_pointer(cls, listtype, lst):
        """
        itemtype must be a valid ffi type, such as 'long' or 'void*'
        """
        obj = object.__new__(cls)
        obj.listtype = listtype
        obj.lst = lst
        return obj

    def as_cdata(self):
        return self.lst

    @property
    def typeditems(self):
        t = self.listtype
        return t.ffi.cast(t.itemtype_ptr, self.lst.items)

    def _grow(self, newsize):
        t = self.listtype
        lst = self.lst
        if newsize <= lst.size:
            return
        lst.items = sharedmem.realloc_array(t.ffi, t.itemtype, lst.items, newsize)
        lst.size = newsize

    def _setitem(self, n, item):
        item = self.listtype.conv.from_python(item)
        self.typeditems[n] = item

    def _getitem(self, n):
        item = self.typeditems[n]
        return self.listtype.conv.to_python(item)

    def _setcontent(self, items):
        if items is not None:
            self._grow(len(items))
            self.lst.length = len(items)
            for i, item in enumerate(items):
                self._setitem(i, item)

    def _itemindex(self, i):
        """
        Return the index in the array for the i-th element. Always ``i`` for
        lists, overridden by Deque. No bound check.
        """
        return i

    def _getindex(self, i):
        """
        Compute the index for the i-th element. This handles negative indexes, and
        raises IndexError in case of out-of-bound.
        """
        if i < 0:
            i += self.lst.length
        if 0 <= i < self.lst.length:
            return self._itemindex(i)
        raise IndexError
    
    def __len__(self):
        return self.lst.length

    def __getitem__(self, i):
        if isinstance(i, slice):
            idx = xrange(*i.indices(len(self)))
            return [self._getitem(self._itemindex(j)) for j in idx]
        i = self._getindex(i)
        return self._getitem(i)

    # we do not define an __iter__: instead, we rely on the implicit one which
    # python derives from __getitem__


class FixedSizeList(ImmutableList):

    def __setitem__(self, i, item):
        i = self._getindex(i)
        self._setitem(i, item)


class ResizableList(FixedSizeList):
    """
    WARNING: ResizableList is not thread-safe, so it needs to be protected by
    a lock.
    """

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow(lst.size*2)
        n = lst.length
        lst.length += 1
        n = self._itemindex(n)
        self._setitem(n, item)
