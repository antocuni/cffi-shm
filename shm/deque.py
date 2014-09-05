"""
Implement a shm deque on top of a shm list.
"""

from shm.sharedmem import sharedmem
from shm.list import ListType, FixedSizeList

class DequeType(ListType):

    def __init__(self, pyffi, itemtype):
        ListType.__init__(self, pyffi, itemtype, Deque)

    def __repr__(self):
        return '<shm type deque [%s]>' % self.itemtype


class Deque(FixedSizeList):

    def _getindex(self, i):
        i = FixedSizeList._getindex(self, i)
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

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow(lst.size*2)
        n = lst.length
        lst.length += 1
        n = self._getindex(n)
        self._setitem(n, item)

    def popleft(self):
        i = self._getindex(0)
        res = self._getitem(i)
        #self._setitem(i, NULL)
        self.lst.offset += 1
        self.lst.length -= 1
        return res

    def __iter__(self):
        i = 0
        while i < self.lst.length:
            yield self[i]
            i += 1
