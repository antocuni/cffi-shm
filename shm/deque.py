"""
Implement a shm deque on top of a shm list.
"""

from shm.list import ListType, FixedSizeList

class DequeType(ListType):

    def __init__(self, pyffi, itemtype):
        ListType.__init__(self, pyffi, itemtype, Deque)

    def __repr__(self):
        return '<shm type deque [%s]>' % self.itemtype


class Deque(FixedSizeList):

    def _getindex(self, i):
        i = FixedSizeList._getindex(self, i)
        return i + self.lst.offset

    def append(self, item):
        lst = self.lst
        if lst.size <= lst.length:
            self._grow(lst.size*2)
        n = lst.length
        lst.length = n+1
        self._setitem(n, item)

    def popleft(self):
        i = self._getindex(0)
        res = self._getitem(i)
        #self._setitem(i, NULL)
        self.lst.offset += 1
        self.lst.length -= 1
        return res
