import time
import cffi
from shm.sharedmem import sharedmem
from shm.rwlock import ShmRWLock
from shm.testing.util import SubProcess, assert_elapsed_time, tslog

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
            #assert lock.readers_count == 2
            lock.rd_release()
        #assert lock.readers_count == 1
        
        with assert_elapsed_time(0.3, 0.5):
            # 2) the write lock only when the master release it
            lock.wr_acquire()
            lock.wr_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    #assert lock.readers_count == 0
    with SubProcess() as p:
        lock.rd_acquire()
        #assert lock.readers_count == 1
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.rd_release()

    #assert lock.readers_count == 0

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

    #assert lock.readers_count == 0
    with SubProcess() as p:
        lock.wr_acquire()
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.wr_release()


def test_rwlock_starvation(tmpdir):
    def child(pname, tsref, path, lock_addr, initial_delay, sleep_time):
        import time
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        from shm.testing.util import assert_elapsed_time, tslog
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        tslog(tsref, '%s: starting' % pname)
        time.sleep(initial_delay)
        tslog(tsref, '%s: acquiring read lock...' % pname)
        # acquire a read lock and sleep for n seconds
        lock.rd_acquire()
        tslog(tsref, '%s: got read lock, sleeping for %s secs' %
              (pname, sleep_time))
        time.sleep(sleep_time)
        tslog(tsref, '%s: releasing read lock' % pname)
        lock.rd_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    print
    #assert lock.readers_count == 0
    with SubProcess() as p:
        # we want to simulate this case:
        # 1) P1 acquires the READ LOCK
        # 2) P3 tries to acquire the WRITE LOCK and it blocks
        # 3) P2 acquires the READ LOCK
        # 4) P1 releases the READ LOCK; P3 still blocked
        # 5) P2 releases the READ LOCK
        # 6) P3 finally acquires the WRITE LOCK
        #
        # Note that this is technically starvation (because P3 tries to
        # acquire the lock BEFORE). However, RWLock is written explictly NOT
        # to prevent starvation.
        tsref = time.time()
        p.background(tmpdir, child, 'P1', tsref, PATH, lock_addr, 0,   0.5)
        p.background(tmpdir, child, 'P2', tsref, PATH, lock_addr, 0.2, 1)

        # the read lock is kept for a total of 1.2 seconds:
        #     P1 acquires at T
        #     P2 acquires at T+0.2
        #     P1 releases at T+0.5
        #     P2 releases at T+0.2+1
        #
        # so, P3 can acquire the write lock after at least 1.2 secs (plus the
        # time needed to start the two subprocesses, let's say that it's 0.2
        # secs)
        with assert_elapsed_time(1.2, 1.4):
            time.sleep(0.3) # give the child processes enough time to start
            tslog(tsref, 'P3: starting, acquiring write lock...')
            lock.wr_acquire()
            tslog(tsref, 'P3: got write lock, releasing it')
            lock.wr_release()

def test_rwlock_recursive(tmpdir):
    def child(path, lock_addr):
        from shm.sharedmem import sharedmem
        from shm.rwlock import ShmRWLock
        from shm.testing.util import assert_elapsed_time
        #
        sharedmem.open_readonly(path)
        lock = ShmRWLock.from_pointer(lock_addr)
        with assert_elapsed_time(0.3, 0.5):
            # we need to wait until the master releases it
            lock.wr_acquire()
            lock.wr_release()

    ffi = cffi.FFI()
    lock = ShmRWLock()
    lock_addr = int(ffi.cast('long', lock.as_cdata()))

    # first, we check that wr_lock is correctly recursive
    with SubProcess() as p:
        lock.wr_acquire() # 1st
        lock.wr_acquire() # 2nd
        #
        lock.wr_release() # 2nd
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.wr_release() # 1st

    # then, we check that rd_lock is correctly recursive (note that the child
    # still tries to get a wr_lock, else it wouldn't block)
    with SubProcess() as p:
        lock.rd_acquire() # 1st
        lock.rd_acquire() # 2nd
        #
        lock.rd_release() # 2nd
        p.background(tmpdir, child, PATH, lock_addr)
        time.sleep(0.5)
        lock.rd_release() # 1st
