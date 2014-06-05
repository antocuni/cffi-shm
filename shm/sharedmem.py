import os
from shm import gclib

class Uninitialized_shm(object):

    gclib = gclib
    
    def init(self, path):
        self.gclib.init(path)
        self.__class__ = RW_shm
    
    def open_readonly(self, path):
        self.gclib.open_readonly(path)
        self.__class__ = RO_shm



class RW_shm(object):

    def init(self, path):
        raise ValueError('sharedmem already initialized')
    open_readonly = init

    

class RO_shm(object):

    def init(self, path):
        raise ValueError('sharedmem already initialized')
    open_readonly = init


sharedmem = Uninitialized_shm()
