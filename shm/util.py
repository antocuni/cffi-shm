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

def ctype_pointer(ffi, t):
    # XXX: this is a complete hack! But cffi does not seem to offer an
    # official way to get the pointer from the ctype
    ctype = cffi_typeof(ffi, t)
    s = repr(ctype)
    assert s.startswith("<ctype '")
    _, t, _ = s.split("'")
    return ffi.typeof(t + '*')
