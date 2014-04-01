import py

class StructDecorator(object):
    """
    class decorator, to wrap a cffi struct into Python class
    """

    def __init__(self, pyffi, ctype, immutable=False):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.ctype = pyffi.ctypeof(ctype)
        self.immutable = immutable
        if not _is_struct_ptr(self.ctype):
            raise TypeError("ctype must be a pointer to a struct, got %s" % self.ctype)

    def __call__(self, cls):
        cls.ffi = self.ffi
        cls.ctype = self.ctype
        self.add_ctor(cls)
        cls.from_pointer = classmethod(from_pointer)
        for name, field in self.ctype.item.fields:
            self.add_property(cls, name, field)
        self.pyffi.register(self.ctype, cls)
        return cls

    def add_ctor(self, cls):
        # def __init__(self, x, y):
        #     self._ptr = self.ffi.new(self.ctype)
        #     self.__set_x(x)
        #     self.__set_y(y)
        #
        fieldnames = [name for name, field in self.ctype.item.fields]
        paramlist = ', '.join(fieldnames)
        bodylines = []
        bodylines.append('self._ptr = self.ffi.new(self.ctype)')
        for fieldname in fieldnames:
            line = 'self.__set_{x}({x})'.format(x=fieldname)
            bodylines.append(line)
        body = py.code.Source(bodylines)
        init = body.putaround('def __init__(self, %s):' % paramlist)
        cls.__init__ = _compile_def(init)

    def add_property(self, cls, fieldname, field):
        getter = self.getter(cls, fieldname, field)
        setter = self.setter(cls, fieldname, field)
        if self.immutable:
            p = property(getter)
        else:
            p = property(getter, setter)
        setattr(cls, fieldname, p)

    def getter(self, cls, fieldname, field):
        # def __get_x(self):
        #     return convert(self._ptr.x)
        #
        if _is_struct_ptr(field.type):
            valuecls = self.pyffi.pytypeof(field.type)
            convert = valuecls.from_pointer
        else:
            convert = identity
        src = py.code.Source("""
            def __get_{x}(self):
                return convert(self._ptr.{x})
        """.format(x=fieldname))
        fn = _compile_def(src, convert=convert)
        setattr(cls, fn.__name__, fn)
        return fn

    def setter(self, cls, fieldname, field):
        # def __set_x(self, value):
        #     self._ptr.x = value        # OR
        #     #self._ptr.x = value._ptr
        #
        if _is_struct_ptr(field.type):
            value_expr = 'value._ptr'
        else:
            value_expr = 'value'
        src = py.code.Source("""
            def __set_{x}(self, value):
                self._ptr.{x} = {value_expr}
        """.format(x=fieldname, value_expr=value_expr))
        fn = _compile_def(src)
        setattr(cls, fn.__name__, fn)
        return fn



# =============================
# Helpers
# =============================

def _compile_def(src, **glob):
    d = {}
    exec(src.compile(), glob, d)
    assert len(d) == 1
    return d.values()[0]

def identity(x):
    return x

# this is attached to all struct classes
def from_pointer(cls, ptr):
    self = cls.__new__(cls)
    self._ptr = ptr
    return self

def _is_struct_ptr(ctype):
    return ctype.kind == 'pointer' and ctype.item.kind == 'struct'

