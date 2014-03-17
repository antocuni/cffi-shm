import cffi
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

    def __init__(self, ffi, itemtype, root=False):
        """
        itemtype must be a valid ffi type, such as 'long' or 'void*'
        """
        self.ffi = ffi
        self.itemtype = itemtype
        self.lst = self._allocate(root)
        self.typeditems = ffi.cast(itemtype+'*', self.lst.items)

    def _allocate(self, root):
        with gclib.disabled:
            lst = gclib.new(listffi, 'List', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            lst.items = gclib.new_array(self.ffi, self.itemtype, 2)
            lst.size = 2
            lst.length = 0
        return lst

    def _grow(self):
        lst = self.lst
        lst.size *= 2
        lst.items = gclib.realloc_array(self.ffi, self.itemtype, lst.items, lst.size)
        self.typeditems = self.ffi.cast(self.itemtype+'*', lst.items)

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow()
        n = lst.length
        lst.length = n+1
        self._setitem(n, item)

    def _setitem(self, n, item):
        self.typeditems[n] = item

    def __len__(self):
        return self.lst.length
