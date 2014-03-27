libshmgc.so: gc.h gc.c gc.lds
	gcc --std=gnu99 -I. -shared -fPIC -Wl,-T,gc.lds -lrt gc.c -o libshmgc.so

# The purpose of this linker script is to place the library at the address
# immediately following the shared memory area, i.e. at
# GC_get_memory()+GC_get_memsize(): with the current #defines, it is at
# 0x31000000000
BASE_ADDRESS=0x31000000000
#
# This is needed because we want to be able to store a pointer to
# e.g. GC_malloc() in the shared memory, and call it from all processes, so
# we need to ensure that the functions are placed at the same virtual
# address.
#
# This linker script has been created following these instructions: 
# http://stackoverflow.com/questions/17600028/is-there-anyway-to-force-loader-to-load-shared-library-at-a-fixed-address
gc.lds:
	gcc -shared -Wl,--verbose 2>&1 | sed -e '/^======/,/^======/!d' -e '/^======/d;s/0\(.*\)\(+ SIZEOF_HEADERS\)/'$(BASE_ADDRESS)'\1\2/' > gc.lds

clean:
	rm -f gc.lds
	rm -f libshmgc.so