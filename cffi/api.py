import sys, types
from .lock import allocate_lock
import _cffi1_backend

class DeprecatedError(Exception):
    pass

try:
    callable
except NameError:
    # Python 3.1
    from collections import Callable
    callable = lambda x: isinstance(x, Callable)

try:
    basestring
except NameError:
    # Python 3.x
    basestring = str


FFIError = _cffi1_backend.FFI.error

class CDefError(Exception):
    def __str__(self):
        try:
            line = 'line %d: ' % (self.args[1].coord.line,)
        except (AttributeError, TypeError, IndexError):
            line = ''
        return '%s%s' % (line, self.args[0])


class FFI(_cffi1_backend.FFI):
    r'''
    The main top-level class that you instantiate once, or once per module.

    Example usage:

        ffi = FFI()
        ffi.cdef("""
            int printf(const char *, ...);
        """)

        C = ffi.dlopen(None)   # standard library
        -or-
        C = ffi.verify()  # use a C compiler: verify the decl above is right

        C.printf("hello, %s!\n", ffi.new("char[]", "world"))
    '''

    def __init__(self):
        """Create an FFI instance.  The 'backend' argument is used to
        select a non-default backend, mostly for tests.
        """
        from . import cparser, model
        from . import __version__

        backend = _cffi1_backend
        assert backend.__version__ == __version__, \
            "version mismatch, %s != %s" % (backend.__version__, __version__)

        self._backend = backend
        self._lock = allocate_lock()
        self._parser = cparser.Parser()
        self._cached_btypes = {}
        self._parsed_types = types.ModuleType('parsed_types').__dict__
        self._new_types = types.ModuleType('new_types').__dict__
        self._function_caches = []
        self._libraries = []
        self._cdefsources = []
        self._windows_unicode = None
        if hasattr(backend, 'set_ffi'):
            backend.set_ffi(self)
        for name in backend.__dict__:
            if name.startswith('RTLD_'):
                setattr(self, name, getattr(backend, name))
        #
        #with self._lock:
        #    self.BVoidP = self._get_cached_btype(model.voidp_type)
        #    self.BCharA = self._get_cached_btype(model.char_array_type)

    def cdef(self, csource, override=False, packed=False):
        """Parse the given C source.  This registers all declared functions,
        types, and global variables.  The functions and global variables can
        then be accessed via either 'ffi.dlopen()' or 'ffi.verify()'.
        The types can be used in 'ffi.new()' and other functions.
        If 'packed' is specified as True, all structs declared inside this
        cdef are packed, i.e. laid out without any field alignment at all.
        """
        if not isinstance(csource, str):    # unicode, on Python 2
            if not isinstance(csource, basestring):
                raise TypeError("cdef() argument must be a string")
            csource = csource.encode('ascii')
        with self._lock:
            self._parser.parse(csource, override=override, packed=packed)
            self._cdefsources.append(csource)
            if override:
                for cache in self._function_caches:
                    cache.clear()
        _set_cdef_types(self)

    def dlopen(self, name, flags=0):
        """Load and return a dynamic library identified by 'name'.
        The standard C library can be loaded by passing None.
        Note that functions and types declared by 'ffi.cdef()' are not
        linked to a particular library, just like C headers; in the
        library we only look for the actual (untyped) symbols.
        """
        assert isinstance(name, basestring) or name is None
        with self._lock:
            lib, function_cache = _make_ffi_library(self, name, flags)
            self._function_caches.append(function_cache)
            self._libraries.append(lib)
        return lib

    def _typeof_locked(self, cdecl):
        # call me with the lock!
        key = cdecl
        if key in self._parsed_types:
            return self._parsed_types[key]
        #
        if not isinstance(cdecl, str):    # unicode, on Python 2
            cdecl = cdecl.encode('ascii')
        #
        type = self._parser.parse_type(cdecl)
        really_a_function_type = type.is_raw_function
        if really_a_function_type:
            type = type.as_function_pointer()
        btype = self._get_cached_btype(type)
        result = btype, really_a_function_type
        self._parsed_types[key] = result
        return result

    def _typeof(self, cdecl, consider_function_as_funcptr=False):
        # string -> ctype object
        try:
            result = self._parsed_types[cdecl]
        except KeyError:
            with self._lock:
                result = self._typeof_locked(cdecl)
        #
        btype, really_a_function_type = result
        if really_a_function_type and not consider_function_as_funcptr:
            raise CDefError("the type %r is a function type, not a "
                            "pointer-to-function type" % (cdecl,))
        return btype

    def XXXtypeof(self, cdecl):
        """Parse the C type given as a string and return the
        corresponding <ctype> object.
        It can also be used on 'cdata' instance to get its C type.
        """
        if isinstance(cdecl, basestring):
            return self._typeof(cdecl)
        if isinstance(cdecl, self.CData):
            return self._backend.typeof(cdecl)
        if isinstance(cdecl, types.BuiltinFunctionType):
            res = _builtin_function_type(cdecl)
            if res is not None:
                return res
        if (isinstance(cdecl, types.FunctionType)
                and hasattr(cdecl, '_cffi_base_type')):
            with self._lock:
                return self._get_cached_btype(cdecl._cffi_base_type)
        raise TypeError(type(cdecl))

    def XXXsizeof(self, cdecl):
        """Return the size in bytes of the argument.  It can be a
        string naming a C type, or a 'cdata' instance.
        """
        if isinstance(cdecl, basestring):
            BType = self._typeof(cdecl)
            return self._backend.sizeof(BType)
        else:
            return self._backend.sizeof(cdecl)

    def XXXalignof(self, cdecl):
        """Return the natural alignment size in bytes of the C type
        given as a string.
        """
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl)
        return self._backend.alignof(cdecl)

    def XXXoffsetof(self, cdecl, *fields_or_indexes):
        """Return the offset of the named field inside the given
        structure or array, which must be given as a C type name.  
        You can give several field names in case of nested structures.
        You can also give numeric values which correspond to array
        items, in case of an array type.
        """
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl)
        return self._typeoffsetof(cdecl, *fields_or_indexes)[1]

    def XXXnew(self, cdecl, init=None):
        """Allocate an instance according to the specified C type and
        return a pointer to it.  The specified C type must be either a
        pointer or an array: ``new('X *')`` allocates an X and returns
        a pointer to it, whereas ``new('X[n]')`` allocates an array of
        n X'es and returns an array referencing it (which works
        mostly like a pointer, like in C).  You can also use
        ``new('X[]', n)`` to allocate an array of a non-constant
        length n.

        The memory is initialized following the rules of declaring a
        global variable in C: by default it is zero-initialized, but
        an explicit initializer can be given which can be used to
        fill all or part of the memory.

        When the returned <cdata> object goes out of scope, the memory
        is freed.  In other words the returned <cdata> object has
        ownership of the value of type 'cdecl' that it points to.  This
        means that the raw data can be used as long as this object is
        kept alive, but must not be used for a longer time.  Be careful
        about that when copying the pointer to the memory somewhere
        else, e.g. into another structure.
        """
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl)
        return self._backend.newp(cdecl, init)

    def XXXcast(self, cdecl, source):
        """Similar to a C cast: returns an instance of the named C
        type initialized with the given 'source'.  The source is
        casted between integers or pointers of any type.
        """
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl)
        return self._backend.cast(cdecl, source)

    def XXXstring(self, cdata, maxlen=-1):
        """Return a Python string (or unicode string) from the 'cdata'.
        If 'cdata' is a pointer or array of characters or bytes, returns
        the null-terminated string.  The returned string extends until
        the first null character, or at most 'maxlen' characters.  If
        'cdata' is an array then 'maxlen' defaults to its length.

        If 'cdata' is a pointer or array of wchar_t, returns a unicode
        string following the same rules.

        If 'cdata' is a single character or byte or a wchar_t, returns
        it as a string or unicode string.

        If 'cdata' is an enum, returns the value of the enumerator as a
        string, or 'NUMBER' if the value is out of range.
        """
        return self._backend.string(cdata, maxlen)

    def XXXbuffer(self, cdata, size=-1):
        """Return a read-write buffer object that references the raw C data
        pointed to by the given 'cdata'.  The 'cdata' must be a pointer or
        an array.  Can be passed to functions expecting a buffer, or directly
        manipulated with:

            buf[:]          get a copy of it in a regular string, or
            buf[idx]        as a single character
            buf[:] = ...
            buf[idx] = ...  change the content
        """
        return self._backend.buffer(cdata, size)

    def XXXfrom_buffer(self, python_buffer):
        """Return a <cdata 'char[]'> that points to the data of the
        given Python object, which must support the buffer interface.
        Note that this is not meant to be used on the built-in types str,
        unicode, or bytearray (you can build 'char[]' arrays explicitly)
        but only on objects containing large quantities of raw data
        in some other format, like 'array.array' or numpy arrays.
        """
        return self._backend.from_buffer(self.BCharA, python_buffer)

    def XXXcallback(self, cdecl, python_callable=None, error=None):
        """Return a callback object or a decorator making such a
        callback object.  'cdecl' must name a C function pointer type.
        The callback invokes the specified 'python_callable' (which may
        be provided either directly or via a decorator).  Important: the
        callback object must be manually kept alive for as long as the
        callback may be invoked from the C level.
        """
        def callback_decorator_wrap(python_callable):
            if not callable(python_callable):
                raise TypeError("the 'python_callable' argument "
                                "is not callable")
            return self._backend.callback(cdecl, python_callable, error)
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl, consider_function_as_funcptr=True)
        if python_callable is None:
            return callback_decorator_wrap                # decorator mode
        else:
            return callback_decorator_wrap(python_callable)  # direct mode

    def XXXgetctype(self, cdecl, replace_with=''):
        """Return a string giving the C type 'cdecl', which may be itself
        a string or a <ctype> object.  If 'replace_with' is given, it gives
        extra text to append (or insert for more complicated C types), like
        a variable name, or '*' to get actually the C type 'pointer-to-cdecl'.
        """
        if isinstance(cdecl, basestring):
            cdecl = self._typeof(cdecl)
        replace_with = replace_with.strip()
        if (replace_with.startswith('*')
                and '&[' in self._backend.getcname(cdecl, '&')):
            replace_with = '(%s)' % replace_with
        elif replace_with and not replace_with[0] in '[(':
            replace_with = ' ' + replace_with
        return self._backend.getcname(cdecl, replace_with)

    def XXXgc(self, cdata, destructor):
        """Return a new cdata object that points to the same
        data.  Later, when this new cdata object is garbage-collected,
        'destructor(old_cdata_object)' will be called.
        """
        with self._lock:
            try:
                gc_weakrefs = self.gc_weakrefs
            except AttributeError:
                from .gc_weakref import GcWeakrefs
                gc_weakrefs = self.gc_weakrefs = GcWeakrefs(self)
            return gc_weakrefs.build(cdata, destructor)

    def _get_cached_btype(self, type):
        raise DeprecatedError

    def verify(self, source='', **kwargs):
        from recompiler import verify    # XXX must be in the current dir
        FFI._verify_counter += 1
        return verify(self, 'verify%d' % FFI._verify_counter, source, **kwargs)
    _verify_counter = 0

    def XXXverify(self, source='', tmpdir=None, **kwargs):
        """Verify that the current ffi signatures compile on this
        machine, and return a dynamic library object.  The dynamic
        library can be used to call functions and access global
        variables declared in this 'ffi'.  The library is compiled
        by the C compiler: it gives you C-level API compatibility
        (including calling macros).  This is unlike 'ffi.dlopen()',
        which requires binary compatibility in the signatures.
        """
        from .verifier import Verifier, _caller_dir_pycache
        #
        # If set_unicode(True) was called, insert the UNICODE and
        # _UNICODE macro declarations
        if self._windows_unicode:
            self._apply_windows_unicode(kwargs)
        #
        # Set the tmpdir here, and not in Verifier.__init__: it picks
        # up the caller's directory, which we want to be the caller of
        # ffi.verify(), as opposed to the caller of Veritier().
        tmpdir = tmpdir or _caller_dir_pycache()
        #
        # Make a Verifier() and use it to load the library.
        self.verifier = Verifier(self, source, tmpdir, **kwargs)
        lib = self.verifier.load_library()
        #
        # Save the loaded library for keep-alive purposes, even
        # if the caller doesn't keep it alive itself (it should).
        self._libraries.append(lib)
        return lib

    def _get_errno(self):
        return self._backend.get_errno()
    def _set_errno(self, errno):
        self._backend.set_errno(errno)
    XXXerrno = property(_get_errno, _set_errno, None,
                     "the value of 'errno' from/to the C calls")

    def XXXgetwinerror(self, code=-1):
        return self._backend.getwinerror(code)

    def _pointer_to(self, ctype):
        from . import model
        with self._lock:
            return model.pointer_cache(self, ctype)

    def XXXaddressof(self, cdata, *fields_or_indexes):
        """Return the address of a <cdata 'struct-or-union'>.
        If 'fields_or_indexes' are given, returns the address of that
        field or array item in the structure or array, recursively in
        case of nested structures.
        """
        ctype = self._backend.typeof(cdata)
        if fields_or_indexes:
            ctype, offset = self._typeoffsetof(ctype, *fields_or_indexes)
        else:
            if ctype.kind == "pointer":
                raise TypeError("addressof(pointer)")
            offset = 0
        ctypeptr = self._pointer_to(ctype)
        return self._backend.rawaddressof(ctypeptr, cdata, offset)

    def _typeoffsetof(self, ctype, field_or_index, *fields_or_indexes):
        ctype, offset = self._backend.typeoffsetof(ctype, field_or_index)
        for field1 in fields_or_indexes:
            ctype, offset1 = self._backend.typeoffsetof(ctype, field1, 1)
            offset += offset1
        return ctype, offset

    def include(self, ffi_to_include):
        """Includes the typedefs, structs, unions and enums defined
        in another FFI instance.  Usage is similar to a #include in C,
        where a part of the program might include types defined in
        another part for its own usage.  Note that the include()
        method has no effect on functions, constants and global
        variables, which must anyway be accessed directly from the
        lib object returned by the original FFI instance.
        """
        XXX
        with ffi_to_include._lock:
            with self._lock:
                self._parser.include(ffi_to_include._parser)
                self._cdefsources.append('[')
                self._cdefsources.extend(ffi_to_include._cdefsources)
                self._cdefsources.append(']')

    def XXXnew_handle(self, x):
        return self._backend.newp_handle(self.BVoidP, x)

    def XXXfrom_handle(self, x):
        return self._backend.from_handle(x)

    def set_unicode(self, enabled_flag):
        """Windows: if 'enabled_flag' is True, enable the UNICODE and
        _UNICODE defines in C, and declare the types like TCHAR and LPTCSTR
        to be (pointers to) wchar_t.  If 'enabled_flag' is False,
        declare these types to be (pointers to) plain 8-bit characters.
        This is mostly for backward compatibility; you usually want True.
        """
        XXX
        if self._windows_unicode is not None:
            raise ValueError("set_unicode() can only be called once")
        enabled_flag = bool(enabled_flag)
        if enabled_flag:
            self.cdef("typedef wchar_t TBYTE;"
                      "typedef wchar_t TCHAR;"
                      "typedef const wchar_t *LPCTSTR;"
                      "typedef const wchar_t *PCTSTR;"
                      "typedef wchar_t *LPTSTR;"
                      "typedef wchar_t *PTSTR;"
                      "typedef TBYTE *PTBYTE;"
                      "typedef TCHAR *PTCHAR;")
        else:
            self.cdef("typedef char TBYTE;"
                      "typedef char TCHAR;"
                      "typedef const char *LPCTSTR;"
                      "typedef const char *PCTSTR;"
                      "typedef char *LPTSTR;"
                      "typedef char *PTSTR;"
                      "typedef TBYTE *PTBYTE;"
                      "typedef TCHAR *PTCHAR;")
        self._windows_unicode = enabled_flag

    def _apply_windows_unicode(self, kwds):
        defmacros = kwds.get('define_macros', ())
        if not isinstance(defmacros, (list, tuple)):
            raise TypeError("'define_macros' must be a list or tuple")
        defmacros = list(defmacros) + [('UNICODE', '1'),
                                       ('_UNICODE', '1')]
        kwds['define_macros'] = defmacros


def _load_backend_lib(backend, name, flags):
    if name is None:
        if sys.platform != "win32":
            return backend.load_library(None, flags)
        name = "c"    # Windows: load_library(None) fails, but this works
                      # (backward compatibility hack only)
    try:
        if '.' not in name and '/' not in name:
            raise OSError("library not found: %r" % (name,))
        return backend.load_library(name, flags)
    except OSError:
        import ctypes.util
        path = ctypes.util.find_library(name)
        if path is None:
            raise     # propagate the original OSError
        return backend.load_library(path, flags)

def _make_ffi_library(ffi, libname, flags):
    import os
    backend = ffi._backend
    backendlib = _load_backend_lib(backend, libname, flags)
    copied_enums = []
    #
    def make_accessor_locked(name):
        key = 'function ' + name
        if key in ffi._parser._declarations:
            tp = ffi._parser._declarations[key]
            BType = ffi._get_cached_btype(tp)
            try:
                value = backendlib.load_function(BType, name)
            except KeyError as e:
                raise AttributeError('%s: %s' % (name, e))
            library.__dict__[name] = value
            return
        #
        key = 'variable ' + name
        if key in ffi._parser._declarations:
            tp = ffi._parser._declarations[key]
            BType = ffi._get_cached_btype(tp)
            read_variable = backendlib.read_variable
            write_variable = backendlib.write_variable
            setattr(FFILibrary, name, property(
                lambda self: read_variable(BType, name),
                lambda self, value: write_variable(BType, name, value)))
            return
        #
        if not copied_enums:
            from . import model
            for key, tp in ffi._parser._declarations.items():
                if not isinstance(tp, model.EnumType):
                    continue
                for enumname, enumval in zip(tp.enumerators, tp.enumvalues):
                    if enumname not in library.__dict__:
                        library.__dict__[enumname] = enumval
            for key, val in ffi._parser._int_constants.items():
                if key not in library.__dict__:
                    library.__dict__[key] = val

            copied_enums.append(True)
            if name in library.__dict__:
                return
        #
        raise AttributeError(name)
    #
    def make_accessor(name):
        with ffi._lock:
            if name in library.__dict__ or name in FFILibrary.__dict__:
                return    # added by another thread while waiting for the lock
            make_accessor_locked(name)
    #
    class FFILibrary(object):
        def __getattr__(self, name):
            make_accessor(name)
            return getattr(self, name)
        def __setattr__(self, name, value):
            try:
                property = getattr(self.__class__, name)
            except AttributeError:
                make_accessor(name)
                setattr(self, name, value)
            else:
                property.__set__(self, value)
    #
    if libname is not None:
        try:
            if not isinstance(libname, str):    # unicode, on Python 2
                libname = libname.encode('utf-8')
            FFILibrary.__name__ = 'FFILibrary_%s' % libname
        except UnicodeError:
            pass
    library = FFILibrary()
    return library, library.__dict__

def _builtin_function_type(func):
    # a hack to make at least ffi.typeof(builtin_function) work,
    # if the builtin function was obtained by 'vengine_cpy'.
    import sys
    try:
        module = sys.modules[func.__module__]
        ffi = module._cffi_original_ffi
        types_of_builtin_funcs = module._cffi_types_of_builtin_funcs
        tp = types_of_builtin_funcs[func]
    except (KeyError, AttributeError, TypeError):
        return None
    else:
        with ffi._lock:
            return ffi._get_cached_btype(tp)

def _set_cdef_types(ffi):
    from . import model

    all_structs = {}
    all_typedefs = {}
    for name, tp in ffi._parser._declarations.items():
        kind, basename = name.split(' ', 1)
        if kind == 'struct' or kind == 'union' or kind == 'anonymous':
            all_structs[tp.name] = tp
        elif kind == 'typedef':
            all_typedefs[basename] = tp
            if getattr(tp, "origin", None) == "unknown_type":
                all_structs[tp.name] = tp
            elif isinstance(tp, model.NamedPointerType):
                all_structs[tp.totype.name] = tp.totype

    struct_unions = []
    pending_completion = []
    for name, tp in sorted(all_structs.items()):
        if not isinstance(tp, model.UnionType):
            BType = _cffi1_backend.new_struct_type(name)
        else:
            BType = _cffi1_backend.new_union_type(name)
        struct_unions.append(name)
        struct_unions.append(BType)
        if not tp.partial and tp.fldtypes is not None:
            pending_completion.append((tp, BType))
    #
    typenames = []
    for name, tp in sorted(all_typedefs.items()):
        cname = tp._get_c_name()
        if cname == name:
            assert isinstance(tp, model.StructOrUnionOrEnum)
            cname = '%s %s' % (tp.kind, tp.name)
        try:
            BType = ffi.typeof(cname)
        except ffi.error:
            ffi.__set_types(struct_unions, typenames)
            BType = ffi.typeof(cname)
        typenames.append(name)
        typenames.append(BType)
    #
    ffi.__set_types(struct_unions, typenames)
    #
    for tp, BType in pending_completion:
        fldtypes = [ffi.typeof(ftp._get_c_name()) for ftp in tp.fldtypes]
        lst = list(zip(tp.fldnames, fldtypes, tp.fldbitsize))
        sflags = 0
        if tp.packed:
            sflags = 8    # SF_PACKED
        _cffi1_backend.complete_struct_or_union(BType, lst, ffi,
                                                -1, -1, sflags)
