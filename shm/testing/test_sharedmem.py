import py
import sys
import os
import cffi
import shm
from shm import gclib
from shm.sharedmem import SharedMemory
from shm.list import ListType
from shm.dict import DictType
from shm.pyffi import PyFFI

PATH = '/cffi-shm-testing'
gclib.init(PATH)
ffi = cffi.FFI()

def exec_child(tmpdir, fn, *args):
    rootdir = py.path.local(shm.__file__).dirpath('..')
    
    filename = tmpdir.join(fn.__name__ + '.py')
    src = py.code.Source(fn)
    arglist = ', '.join(map(repr, args))
    call = '%s(%s)' % (fn.__name__, arglist)
    with filename.open('w') as f:
        f.write('import sys\n')
        f.write('sys.path.append(%s)\n' % repr(str(rootdir)))
        f.write(str(src))
        f.write('\n')
        f.write(call)
    #
    ret = os.system("%s %s" % (sys.executable, filename))
    if ret != 0:
        raise ValueError("The child returned non-0 status")
    return True


def test_exec_child(tmpdir):
    def fn(a, b):
        assert a == b
    assert exec_child(tmpdir, fn, 10, 10)
    py.test.raises(ValueError, "exec_child(tmpdir, fn, 10, 11)")
            
            
def test_sharedmem(tmpdir):
    def child(path, address, size, str_addr):
        import cffi
        from shm.sharedmem import SharedMemory
        #
        ffi = cffi.FFI()
        mem = SharedMemory.open(path)
        rawstr = ffi.cast('char*', str_addr)
        assert ffi.string(rawstr) == 'hello world'

    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    rawstr = gclib.new_string('hello world', root=True)
    str_addr = int(ffi.cast('long', rawstr))
    assert exec_child(tmpdir, child, PATH, base_addr, size, str_addr)


def test_list(tmpdir):
    def child(path, address, size, list_addr):
        import cffi
        from shm.sharedmem import SharedMemory
        from shm.pyffi import PyFFI
        from shm.list import ListType
        #
        pyffi = PyFFI(cffi.FFI())
        mem = SharedMemory.open(path)
        LT = ListType(pyffi, 'long')
        lst = LT.from_pointer(list_addr)
        assert list(lst) == range(100)

    pyffi = PyFFI(ffi)
    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    LT = ListType(pyffi, 'long')
    lst = LT(range(100), root=True)
    list_addr = int(ffi.cast('long', lst.lst))
    assert exec_child(tmpdir, child, PATH, base_addr, size, list_addr)


def test_dict(tmpdir):
    def child(path, address, size, dict_addr):
        import cffi
        from shm.sharedmem import SharedMemory
        from shm.pyffi import PyFFI
        from shm.dict import DictType
        #
        pyffi = PyFFI(cffi.FFI())
        DT = DictType(pyffi, 'const char*', 'long')
        mem = SharedMemory.open(path)
        d = DT.from_pointer(dict_addr)
        assert d['hello'] == 1
        assert d['world'] == 2
        assert sorted(d.keys()) == ['hello', 'world']

    pyffi = PyFFI(ffi)
    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    DT = DictType(pyffi, 'const char*', 'long')
    d = DT(root=True)
    d['hello'] = 1
    d['world'] = 2
    dict_addr = int(ffi.cast('long', d.ht))
    assert exec_child(tmpdir, child, PATH, base_addr, size, dict_addr)
