libshmgc.so: gc.h gc.c gc.lds
	gcc --std=gnu99 -I. -shared -fPIC -Wl,-T,gc.lds gc.c -o libshmgc.so
