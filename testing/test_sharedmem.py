import py
import sys
import os
import cffi
import shm
from shm import gclib
from shm.sharedmem import SharedMemory
from shm.list import List
from shm.dict import Dict

PATH = '/run/shm/cffi-shm-testing'
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
        mem = SharedMemory.open(path, address, size)
        rawstr = ffi.cast('char*', str_addr)
        assert ffi.string(rawstr) == 'hello world'
        mem.close()

    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    rawstr = gclib.new_string('hello world', root=True)
    str_addr = int(ffi.cast('long', rawstr))
    assert exec_child(tmpdir, child, PATH, base_addr, size, str_addr)


def test_list(tmpdir):
    def child(path, address, size, list_addr):
        import cffi
        from shm.sharedmem import SharedMemory
        from shm.list import List
        #
        ffi = cffi.FFI()
        mem = SharedMemory.open(path, address, size)
        lst = List.from_pointer(ffi, 'long', list_addr)
        assert list(lst) == range(100)
        mem.close()

    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    lst = List(ffi, 'long', range(100), root=True)
    list_addr = int(ffi.cast('long', lst.lst))
    assert exec_child(tmpdir, child, PATH, base_addr, size, list_addr)


def test_dict(tmpdir):
    def child(path, address, size, dict_addr):
        import cffi
        from shm.sharedmem import SharedMemory
        from shm.dict import Dict
        #
        ffi = cffi.FFI()
        mem = SharedMemory.open(path, address, size)
        d = Dict.from_pointer(ffi, 'const char*', 'long', dict_addr)
        assert d['hello'] == 1
        assert d['world'] == 2
        mem.close()

    base_addr = int(ffi.cast('long', gclib.lib.GC_get_memory()))
    size = gclib.lib.GC_get_memsize()
    d = Dict(ffi, 'const char*', 'long', root=True)
    d['hello'] = 1
    d['world'] = 2
    dict_addr = int(ffi.cast('long', d.d))
    assert exec_child(tmpdir, child, PATH, base_addr, size, dict_addr)
