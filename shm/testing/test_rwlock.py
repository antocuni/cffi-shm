import time
import cffi
from shm.sharedmem import sharedmem
from shm.rwlock import ShmRWLock
from shm.testing.util import SubProcess

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)

def test_rwlock_wrlock(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        from shm.testing.util import assert_elapsed_time
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        with assert_elapsed_time(0.3, 0.5):
            # the lock is owned by the parent for 0.5 seconds
            lock.wr_acquire()
            lock.wr_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    with SubProcess() as p:
        p.background(tmpdir, child, PATH, lock_addr)
        lock.wr_acquire()
        time.sleep(0.5)
        lock.wr_release()

