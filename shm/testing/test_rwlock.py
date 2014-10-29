import time
import cffi
from shm.sharedmem import sharedmem
from shm.rwlock import ShmRWLock
from shm.testing.util import SubProcess

PATH = '/cffi-shm-testing'
sharedmem.init(PATH)

def test_rwlock_write_write(tmpdir):
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


def test_rwlock_read_read_write(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        from shm.testing.util import assert_elapsed_time
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        # the master is holding a read lock:
        with assert_elapsed_time(0.0, 0.001):
            # 1) a read lock is available immediately
            lock.rd_acquire()
            assert lock.readers_count == 2
            lock.rd_release()
        assert lock.readers_count == 1
        
        with assert_elapsed_time(0.3, 0.5):
            # 2) the write lock only when the master release it
            lock.wr_acquire()
            lock.wr_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    assert lock.readers_count == 0
    with SubProcess() as p:
        lock.rd_acquire()
        assert lock.readers_count == 1
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.rd_release()

    assert lock.readers_count == 0

def test_rwlock_write_read_read(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        from shm.testing.util import assert_elapsed_time
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        # the master is holding a write lock:
        with assert_elapsed_time(0.3, 0.5):
            # 1) we need to wait for the read lock
            lock.rd_acquire()
            lock.rd_release()

        with assert_elapsed_time(0.0, 0.001):
            # 2) but now we can acquire it immediately
            lock.rd_acquire()
            lock.rd_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    assert lock.readers_count == 0
    with SubProcess() as p:
        lock.wr_acquire()
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.wr_release()
