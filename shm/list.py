import cffi
import _cffi_backend
from shm.sharedmem import sharedmem
from shm.converter import Dummy
from shm.util import ctype_pointer_to, cffi_typeof
from shm.pyffi import AbstractGenericType

listffi = cffi.FFI()

listffi.cdef("""
    typedef struct {
        void* items;
        long size;   // number of allocated items
        long length; // number of actually used items
    } List;
""")

class ListType(AbstractGenericType):

    def __init__(self, pyffi, itemtype, listclass=None, immutable=False):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.itemtype = itemtype
        self.itemtype_ptr = ctype_pointer_to(self.ffi, itemtype)
        if immutable:
            defaultclass = ImmutableList
        else:
            defaultclass = FixedSizeList
        self.listclass = listclass or defaultclass
        self.immutable = immutable
        #
        # if it's a primitive we do not need a converter, because the
        # conversion is already performed automatically by typeditems, which
        # is a typed cffi array
        if cffi_typeof(self.ffi, itemtype).kind == 'primitive':
            self.conv = Dummy(self.ffi, itemtype)
        else:
            self.conv = pyffi.get_converter(itemtype)

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

    def _getindex(self, i):
        if i < 0:
            i += self.lst.length
        if 0 <= i < self.lst.length:
            return i
        raise IndexError
    
    def __len__(self):
        return self.lst.length

    def __getitem__(self, i):
        i = self._getindex(i)
        return self._getitem(i)

    def __iter__(self):
        i = 0
        while i < self.lst.length:
            yield self._getitem(i)
            i += 1


class FixedSizeList(ImmutableList):

    def __setitem__(self, i, item):
        i = self._getindex(i)
        self._setitem(i, item)


class ResizableList(FixedSizeList):
    """
    WARNING: ListInstance is not thread-safe!
    """

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow(lst.size*2)
        n = lst.length
        lst.length = n+1
        self._setitem(n, item)
