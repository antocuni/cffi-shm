"""
Implement a shm deque on top of a shm list.
So far, only .append() and .popleft() are implemented.
"""

from shm.sharedmem import sharedmem
from shm.list import ListType, ResizableList

class DequeType(ListType):

    def __init__(self, pyffi, itemtype):
        ListType.__init__(self, pyffi, itemtype, Deque)

    def __repr__(self):
        return '<shm type deque [%s]>' % self.itemtype


class Deque(ResizableList):

    def _itemindex(self, i):
        i += self.lst.offset
        if i >= self.lst.size:
            i -= self.lst.size
        return i

    def _grow(self, newsize):
        t = self.listtype
        lst = self.lst
        oldsize = lst.size
        if newsize <= lst.size:
            return
        newitems = sharedmem.new_array(t.ffi, t.itemtype, newsize)
        i = lst.offset
        for j in xrange(lst.length):
            newitems[j] = self.typeditems[i]
            i += 1
            if i == oldsize:
                i = 0
        lst.items = newitems
        lst.size = newsize
        lst.offset = 0

    def popleft(self):
        if len(self) == 0:
            raise IndexError
        i = self._itemindex(0)
        res = self._getitem(i)
        if self.listtype.itemtype_is_pointer:
            self.typeditems[i] = self.listtype.ffi.NULL
        self.lst.offset = (self.lst.offset+1) % self.lst.size
        self.lst.length -= 1
        return res
