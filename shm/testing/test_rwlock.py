import time
import cffi
from shm.sharedmem import sharedmem
from shm.rwlock import ShmRWLock
from shm.testing.util import SubProcess

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)


def test_rwlock_wrlock(tmpdir):
    def child(path, lock_addr):
        import time
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        a = time.time()
        lock.wr_acquire() # the lock is owned by the parent for 0.5 seconds
        b = time.time()
        lock.wr_release()
        diff = abs(b-a)
        # we check that the lock has been owned by ~0.5 seconds
        assert 0.3 < diff < 0.5

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    with SubProcess() as p:
        p.background(tmpdir, child, PATH, lock_addr)
        lock.wr_acquire()
        time.sleep(0.5)
        lock.wr_release()

