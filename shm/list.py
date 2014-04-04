import cffi
import _cffi_backend
from shm import gclib
from shm.util import ctype_pointer_to

listffi = cffi.FFI()

listffi.cdef("""
    typedef struct {
        void* items;
        long size;   // number of allocated items
        long length; // number of actually used items
    } List;
""")

class ListType(object):
    def __init__(self, pyffi, itemtype):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.itemtype = itemtype
        self.itemtype_ptr = ctype_pointer_to(self.ffi, itemtype)

    def __repr__(self):
        return '<shm type list [%s]>' % self.itemtype

    def __call__(self, items=None, root=False):
        with gclib.disabled:
            ptr = gclib.new(listffi, 'List*', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            ptr.items = gclib.new_array(self.ffi, self.itemtype, 2)
            ptr.size = 2
            ptr.length = 0
        lst = ListInstance(self, ptr)
        lst._setcontent(items)
        return lst

    def from_pointer(self, ptr):
        ptr = listffi.cast('List*', ptr)
        return ListInstance(self, ptr)


class ListInstance(object):

    def __init__(self, listtype, lst):
        """
        itemtype must be a valid ffi type, such as 'long' or 'void*'
        """
        self.listtype = listtype
        self.lst = lst

    @property
    def typeditems(self):
        t = self.listtype
        return t.ffi.cast(t.itemtype_ptr, self.lst.items)

    def _grow(self, newsize):
        t = self.listtype
        lst = self.lst
        if newsize <= lst.size:
            return
        lst.items = gclib.realloc_array(t.ffi, t.itemtype, lst.items, newsize)
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

