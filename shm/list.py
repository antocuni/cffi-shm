import cffi
from shm import gclib

ffi = cffi.FFI()

ffi.cdef("""
    typedef struct {
        void** items;
        long size;   // number of allocated items
        long length; // number of actually used items
    } List;
""")

class List(object):

    def __init__(self, itemtype='void*', root=False):
        self.lst = self._allocate(root)
        self.itemtype = itemtype

    def _allocate(self, root):
        with gclib.disabled:
            lst = gclib.new(ffi, 'List', root)
            # even for empty lists, we start by allocating 2 items, and then
            # growing
            lst.items = gclib.new_array(ffi, 'void*', 2)
            lst.size = 2
            lst.length = 0
        return lst

    def __len__(self):
        return self.lst.length
