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

    def __init__(self, ffi, itemtype, items=None, root=False):
        """
        itemtype must be a valid ffi type, such as 'long' or 'void*'
        """
        self.ffi = ffi
        self.itemtype = itemtype
        initial_size = 2
        self.lst = self._allocate(root)
        self.typeditems = ffi.cast(itemtype+'*', self.lst.items)
        self._setcontent(items)

    def _allocate(self, root):
        with gclib.disabled:
            lst = gclib.new(listffi, 'List', root)
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
        self.typeditems = self.ffi.cast(self.itemtype+'*', lst.items)

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

    def __len__(self):
        return self.lst.length
