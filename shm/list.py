import cffi
import _cffi_backend
from shm import gclib

listffi = cffi.FFI()

listffi.cdef("""
    typedef struct {
        void* items;
        long size;   // number of allocated items
        long length; // number of actually used items
    } List;
""")

class List(object):

    def __init__(self, ffi, itemtype, items=None, root=False):
        """
        itemtype must be a valid ffi type, such as 'long' or 'void*'
        """
        self.ffi = ffi
        self.itemtype = itemtype
        self.itemtype_ptr = _cffi_backend.new_pointer_type(ffi.typeof(itemtype))
        self.lst = self._allocate(root)
        self._setcontent(items)

    @classmethod
    def from_pointer(cls, ffi, itemtype, ptr):
        self = cls.__new__(cls)
        self.ffi = ffi
        self.itemtype = itemtype
        self.itemtype_ptr = _cffi_backend.new_pointer_type(ffi.typeof(itemtype))
        self.lst = listffi.cast('List*', ptr)
        return self

    @property
    def typeditems(self):
        return self.ffi.cast(self.itemtype_ptr, self.lst.items)

    def _allocate(self, root):
        with gclib.disabled:
            lst = gclib.new(listffi, 'List*', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            lst.items = gclib.new_array(self.ffi, self.itemtype, 2)
            lst.size = 2
            lst.length = 0
        return lst

    def _grow(self, newsize):
        lst = self.lst
        if newsize <= lst.size:
            return
        lst.items = gclib.realloc_array(self.ffi, self.itemtype, lst.items, newsize)
        lst.size = newsize

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow(lst.size*2)
        n = lst.length
        lst.length = n+1
        self._setitem(n, item)

    def _setitem(self, n, item):
        self.typeditems[n] = item

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
        return self.typeditems[i]

    def __setitem__(self, i, item):
        i = self._getindex(i)
        self.typeditems[i] = item

    def __iter__(self):
        i = 0
        while i < self.lst.length:
            yield self.typeditems[i]
            i += 1

