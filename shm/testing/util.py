import py
import sys
import os
import shm
import subprocess

def _prepare_child(tmpdir, fn, *args):
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
    return str(filename)

def exec_child(tmpdir, fn, *args):
    filename = _prepare_child(tmpdir, fn, *args)
    cmd = "%s %s" % (sys.executable, filename)
    #cmd = "gdb --args %s" % cmd
    ret = os.system(cmd)
    if ret != 0:
        raise ValueError("The child returned non-0 status")
    return True

class SubProcess(object):
    """
    Simple helper class to ensure that all the subprocesses terminate
    correctly
    """

    def __init__(self):
        self.plist = []

    def background(self, tmpdir, fn, *args):
        filename = _prepare_child(tmpdir, fn, *args)
        p = subprocess.Popen([sys.executable, filename])
        self.plist.append(p)

    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        if etype is None:
            for p in self.plist:
                ret = p.wait()
                assert ret == 0, 'child returned non-0 status'
