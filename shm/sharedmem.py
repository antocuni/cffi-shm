import os
from shm import gclib

class Uninitialized_shm(object):

    gclib = gclib
    path = None
    
    def init(self, path):
        self.gclib.init(path)
        self.path = path
        self.__class__ = RW_shm
    
    def open_readonly(self, path):
        self.gclib.open_readonly(path)
        self.path = path
        self.__class__ = RO_shm



class RW_shm(object):

    def init(self, path):
        if path == self.path:
            return
        raise ValueError('sharedmem already initialized: %s' % self.path)

    def open_readonly(self, path):
        raise ValueError('sharedmem already initialized in RW mode: %s' % self.path)

    

class RO_shm(object):

    def init(self, path):
        raise ValueError('sharedmem already opened in RO mode: %s' % self.path)

    def open_readonly(self, path):
        if path == self.path:
            return
        raise ValueError('sharedmem already opened: %s' % self.path)


sharedmem = Uninitialized_shm()
