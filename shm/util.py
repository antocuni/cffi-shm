def compile_def(src, **glob):
    d = {}
    exec(src.compile(), glob, d)
    assert len(d) == 1
    return d.values()[0]

def identity(x):
    return x

def cffi_typeof(ffi, t):
    if isinstance(t, str):
        return ffi.typeof(t)
    return t

def cffi_is_primitive(ffi, t):
    ctype = cffi_typeof(ffi, t)
    return ctype.kind == 'primitive'

def cffi_is_double(ffi, t):
    ctype = cffi_typeof(ffi, t)
    return ctype == ffi.typeof('double')

def cffi_is_string(ffi, t):
    return cffi_typeof(ffi, t) == ffi.typeof('char*')

def cffi_is_char_array(ffi, t):
    ctype = cffi_typeof(ffi, t)
    return ctype.kind == 'array' and ctype.item == ffi.typeof('char')

def cffi_is_struct_ptr(ffi, t):
    ctype = cffi_typeof(ffi, t)
    return ctype.kind == 'pointer' and ctype.item.kind == 'struct'
    
def cffi_is_struct(ffi, t):
    ctype = cffi_typeof(ffi, t)
    return ctype.kind == 'struct'

# ====================================================================
# XXX: the following functions are a complete hack!
# However, cffi does not seem to offer an official way to manipulate ctype
# objects, so we need to parse the C str repr of the type and start from there

def ctype_pointer_to(ffi, t):
    ctype = cffi_typeof(ffi, t)
    t = _strtype(ctype)
    return ffi.typeof(t + '*')

def ctype_array_of(ffi, t):
    ctype = cffi_typeof(ffi, t)
    t = _strtype(ctype)
    return ffi.typeof(t + '[]')

def _strtype(ctype):
    s = repr(ctype)
    assert s.startswith("<ctype '")
    _, t, _ = s.split("'")
    return t


class CNamespace(object):

    def __init__(self, lib, prefix):
        self._lib = lib
        PREFIX = prefix.upper()
        for key, value in lib.__dict__.iteritems():
            if key.startswith(prefix) or key.startswith(PREFIX):
                key = key[len(prefix):]
                setattr(self, key, value)


class Checked(object):

    def __init__(self, lib):
        self._lib = lib
        for key, value in lib.__dict__.iteritems():
            if callable(value):
                value = self._checked(value)
            setattr(self, key, value)

    def _checked(self, func):
        from functools import wraps
        import errno
        @wraps(func)
        def fn(*args, **kwargs):
            ret = func(*args, **kwargs)
            if ret != 0:
                err = errno.errorcode.get(ret, '<ERROR %d>' % ret)
                raise ValueError(err)
            return ret
        return fn
