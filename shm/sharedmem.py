import os
from shm import gclib

class SharedMemory(object):
    @staticmethod
    def open(path):
        gclib.open(path)
