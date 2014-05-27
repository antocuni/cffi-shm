"""
Implement a shm set on top of a shm dict
"""

from shm.dict import DictType
from shm.pyffi import AbstractGenericType

class SetType(AbstractGenericType):
    def __init__(self, pyffi, itemtype, **kwds):
        self.pyffi = pyffi
        self.itemtype = itemtype
        self.DT = DictType(pyffi, itemtype, 'long', **kwds)
        
    def __repr__(self):
        return '<shm type set [%s]>' % self.itemtype

    def __call__(self, root=True):
        d = self.DT(root)
        return SetInstance(self, d)

    def from_pointer(self, ptr):
        d = self.DT.from_pointer(ptr)
        return SetInstance(self, d)

class SetInstance(object):

    def __init__(self, settype, d):
        self.settype = settype
        self.d = d
        
    def __repr__(self):
        addr = int(dictffi.cast('long', self.d.as_cdata()))
        return '<shm set [%s] at 0x%x>' % (self.settype.itemtype,
                                           addr)
    def as_cdata(self):
        return self.d.ht

    def add(self, item):
        self.d[item] = 1

    def remove(self, item):
        del self.d[item]

    def discard(self, item):
        try:
            self.remove(item)
        except KeyError:
            pass

    def __contains__(self, item):
        return item in self.d

    def __iter__(self):
        return iter(self.d.keys())
