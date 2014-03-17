import cffi
from shm import gclib

ffi = cffi.FFI()

ffi.cdef("""
    typedef struct {
        void* items;
        long size;   // number of allocated items
        long length; // number of actually used items
    } List;
""")

class List(object):

    def __init__(self, itemtype='void*', root=False):
        self.itemtype = itemtype
        self.lst = self._allocate(root)
        self.typeditems = ffi.cast(itemtype+'*', self.lst.items)

    def _allocate(self, root):
        with gclib.disabled:
            lst = gclib.new(ffi, 'List', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            lst.items = gclib.new_array(ffi, self.itemtype, 2)
            lst.size = 2
            lst.length = 0
        return lst

    def append(self, item):
        lst = self.lst
        if lst.size > lst.length:
            n = lst.length
            lst.length = n+1
            self._setitem(n, item)
        else:
            assert False

    def _setitem(self, n, item):
        self.typeditems[n] = item

    def __len__(self):
        return self.lst.length
