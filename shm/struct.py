import py
from shm import gclib
from shm.util import (cffi_typeof, cffi_is_struct_ptr, cffi_is_string,
                      cffi_is_char_array, compile_def, identity)


class StructDecorator(object):
    """
    class decorator, to wrap a cffi struct into Python class
    """

    def __init__(self, pyffi, ctype, immutable=False):
        self.pyffi = pyffi
        self.ffi = pyffi.ffi
        self.ctype = cffi_typeof(self.ffi, ctype)
        self.immutable = immutable
        if not cffi_is_struct_ptr(self.ffi, self.ctype):
            raise TypeError("ctype must be a pointer to a struct, got %s" % self.ctype)

    def __call__(self, cls):
        cls.pyffi = self.pyffi
        cls.ctype = self.ctype
        self.add_ctor(cls)
        cls.from_pointer = classmethod(from_pointer)
        for name, field in self.ctype.item.fields:
            self.add_property(cls, name, field)
        self.pyffi.register(self.ctype, cls)
        return cls

    def add_ctor(self, cls):
        # def __init__(self, x, y):
        #     self._ptr = gclib.new(self.pyffi.ffi, self.ctype)
        #     self.__set_x(x)
        #     self.__set_y(y)
        #
        fieldnames = [name for name, field in self.ctype.item.fields]
        paramlist = ', '.join(fieldnames)
        bodylines = []
        bodylines.append('self._ptr = gclib.new(self.pyffi.ffi, self.ctype)')
        for fieldname in fieldnames:
            line = 'self.__set_{x}({x})'.format(x=fieldname)
            bodylines.append(line)
        body = py.code.Source(bodylines)
        init = body.putaround('def __init__(self, %s):' % paramlist)
        cls.__init__ = compile_def(init, gclib=gclib)

    def add_property(self, cls, fieldname, field):
        getter = self.getter(cls, fieldname, field)
        setter = self.setter(cls, fieldname, field)
        if self.immutable:
            p = property(getter)
        else:
            p = property(getter, setter)
        setattr(cls, fieldname, p)

    def getter(self, cls, fieldname, field):
        conv = self.pyffi.get_converter(field.type)
        src = py.code.Source("""
            def __get_{x}(self):
                return conv.to_python(self._ptr.{x})
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn

    def setter(self, cls, fieldname, field):
        conv = self.pyffi.get_converter(field.type)
        src = py.code.Source("""
            def __set_{x}(self, value):
                self._ptr.{x} = conv.from_python(value)
        """.format(x=fieldname))
        fn = compile_def(src, conv=conv)
        setattr(cls, fn.__name__, fn)
        return fn


# this is used by setters
def to_pointer(obj):
    return obj._ptr

# this is attached to all struct classes
def from_pointer(cls, ptr):
    self = cls.__new__(cls)
    self._ptr = ptr
    return self
