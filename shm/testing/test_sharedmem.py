import py
from shm.sharedmem import Uninitialized_shm, RW_shm, RO_shm

class MyGclib(object):

    status = None

    def init(self, path):
        self.status = ('rw', path)

    def open_readonly(self, path):
        self.status = ('ro', path)


class MySharedMemory(Uninitialized_shm):
    gclib = MyGclib()
    

def test_init():
    my_sharedmem = MySharedMemory()
    my_sharedmem.init('/foo')
    assert isinstance(my_sharedmem, RW_shm)
    assert MySharedMemory.gclib.status == ('rw', '/foo')
    my_sharedmem.init('/foo') # does not crash
    py.test.raises(ValueError, "my_sharedmem.init('/bar')")
    py.test.raises(ValueError, "my_sharedmem.open_readonly('/foo')")

def test_open_readonly():
    my_sharedmem = MySharedMemory()
    my_sharedmem.open_readonly('/foo')
    assert isinstance(my_sharedmem, RO_shm)
    assert MySharedMemory.gclib.status == ('ro', '/foo')
    my_sharedmem.open_readonly('/foo') # does not crash
    py.test.raises(ValueError, "my_sharedmem.init('/foo')")
    py.test.raises(ValueError, "my_sharedmem.open_readonly('/bar')")
