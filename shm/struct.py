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
        cls.__init__ = compile_def(init)

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
        if cffi_is_struct_ptr(self.ffi, field.type):
            valuecls = self.pyffi.pytypeof(field.type)
            convert = valuecls.from_pointer
        elif cffi_is_string(self.ffi, field.type):
            convert = self.ffi.string
        elif cffi_is_char_array(self.ffi, field.type):
            convert = self.ffi.string
        else:
            convert = identity
        src = py.code.Source("""
            def __get_{x}(self):
                return convert(self._ptr.{x})
        """.format(x=fieldname))
        fn = compile_def(src, convert=convert)
        setattr(cls, fn.__name__, fn)
        return fn

    def setter(self, cls, fieldname, field):
        # def __set_x(self, value):
        #     self._ptr.x = convert(value)
        #
        if cffi_is_struct_ptr(self.ffi, field.type):
            convert = to_pointer
        elif cffi_is_string(self.ffi, field.type):
            convert = gclib.new_string
        #elif array-of-chars:
        #    no conversion needed, cffi will take care of
        #    copying the python string to the array
        #    XXX: should we set to 0 the whole array first?
        else:
            convert = identity
        src = py.code.Source("""
            def __set_{x}(self, value):
                self._ptr.{x} = convert(value)
        """.format(x=fieldname))
        fn = compile_def(src, convert=convert)
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
