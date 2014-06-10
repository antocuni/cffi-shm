/*
 * cfuhash.c - This file is part of the libcfu library
 *
 * Copyright (c) 2005 Don Owens. All rights reserved.
 * Copyright (c) 2014 Antonio Cuni. All rights reserved.
 *
 * This code is released under the BSD license:
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *
 *   * Neither the name of the author nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 * OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#define HAVE_PTHREAD_H

#include "cfu.h"
#include "cfuhash.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <assert.h>

#ifdef HAVE_PTHREAD_H
# include <pthread.h>
#endif

#include <strings.h>

typedef struct cfuhash_event_flags {
	int resized:1;
	int pad:31;
} cfuhash_event_flags;

typedef struct cfuhash_entry {
	void *key;
	size_t key_size;
	void *data;
	size_t data_size;
	struct cfuhash_entry *next;
} cfuhash_entry;

/* Note that there are two kinds of "free functions":
 
   - malloc_fn/free_fn are mandatory and are used to allocate the hasttable
     itself and all the internal structures

   - values_free_fn is optional: if it's specified, the hash table takes the
     ownership of the values put inside and frees them when they are removed
*/


struct cfuhash_table {
	libcfu_type type;
	size_t num_buckets;
	size_t entries; /* Total number of entries in the table. */
	cfuhash_entry **buckets;
#ifdef HAVE_PTHREAD_H
	pthread_mutex_t mutex;
#endif
	unsigned int flags;
	cfuhash_function_t hash_func;
	cfuhash_cmp_t cmp_func;
	size_t each_bucket_index;
	cfuhash_entry *each_chain_entry;
	float high;
	float low;
    cfuhash_fieldspec_t *key_fieldspec;
	cfuhash_malloc_fn_t malloc_fn;
	cfuhash_free_fn_t free_fn;
	cfuhash_free_fn_t values_free_fn; /* this is optional */
	unsigned int resized_count;
	cfuhash_event_flags event_flags;
};

/* Perl's hash function */
static unsigned int
hash_func_part(unsigned int hv, const void *key, size_t length) {
	register size_t i = length;
	register const unsigned char *s = (const unsigned char *)key;
    if (!key)
        return hv;
	while (i--) {
		hv += *s++;
		hv += (hv << 10);
		hv ^= (hv >> 6);
	}
    return hv;
}

static unsigned int
hash_func_finalize(unsigned int hv) {
	hv += (hv << 3);
	hv ^= (hv >> 11);
	hv += (hv << 15);
	return hv;
}

static unsigned int
hash_func(const void *key, size_t length) {
	register unsigned int hv = 0; /* could put a seed here instead of zero */
    hv = hash_func_part(hv, key, length);
    return hash_func_finalize(hv);
}

/* Call the hash function associated to the ht. In case it's NULL, it calls
   the default hash_func.  We cannot simply store hash_func as the default
   value because in case we share the memory between two processes, we get two
   different address spaces.
*/
static unsigned int call_hash_func(cfuhash_table_t *ht, const void *key, size_t length) {
    if (ht->key_fieldspec != NULL)
        return cfuhash_generic_hash(ht->key_fieldspec, key);
	else if (ht->hash_func == NULL)
		return hash_func(key, length);
	else
		return ht->hash_func(key, length);
}


/* like stdlib's calloc, but using our own malloc function */
static void * cfuhash_calloc(cfuhash_table_t *ht, size_t nmemb, size_t size) {
	size_t total_size = nmemb*size;
	void *mem = ht->malloc_fn(total_size);
	if (!mem)
		return NULL;
	memset(mem, 0, total_size);
	return mem;
}

/* makes sure the real size of the buckets array is a power of 2 */
static unsigned int
hash_size(unsigned int s) {
	unsigned int i = 1;
	while (i < s) i <<= 1;
	return i;
}

static CFU_INLINE void *
hash_key_dup(cfuhash_table_t *ht, const void *key, size_t key_size) {
	assert(key_size != 0);
	void *new_key = ht->malloc_fn(key_size);
	memcpy(new_key, key, key_size);
	return new_key;
}

static CFU_INLINE void *
hash_key_dup_lower_case(cfuhash_table_t *ht, const void *key, size_t key_size) {
	assert(key_size != 0);
	char *new_key = (char *)hash_key_dup(ht, key, key_size);
	size_t i = 0;
	for (i = 0; i < key_size; i++) new_key[i] = tolower(new_key[i]);
	return (void *)new_key;
}

/* returns the index into the buckets array */
static CFU_INLINE unsigned int
hash_value(cfuhash_table_t *ht, const void *key, size_t key_size, size_t num_buckets) {
	unsigned int hv = 0;

	if (key_size == 0) {
		/* hashing the pointer itself, not the content */
		hv = (unsigned int)key;
	}
	else if (key) {
		if (ht->flags & CFUHASH_IGNORE_CASE) {
			char *lc_key = (char *)hash_key_dup_lower_case(ht, key, key_size);
			hv = call_hash_func(ht, lc_key, key_size);
			ht->free_fn(lc_key);
		} else {
			hv = call_hash_func(ht, key, key_size);
		}
	}

	/* The idea is the following: if, e.g., num_buckets is 32
	   (000001), num_buckets - 1 will be 31 (111110). The & will make
	   sure we only get the first 5 bits which will guarantee the
	   index is less than 32.
	*/
	return hv & (num_buckets - 1);
}

static cfuhash_table_t *
_cfuhash_new(size_t size, unsigned int flags, cfuhash_malloc_fn_t malloc_fn, 
			 cfuhash_free_fn_t free_fn) {
	cfuhash_table_t *ht;

	if (malloc_fn == NULL)
		malloc_fn = malloc;
	if (free_fn == NULL)
		free_fn = free;

	size = hash_size(size);
	ht = malloc_fn(sizeof(cfuhash_table_t));
	memset(ht, '\000', sizeof(cfuhash_table_t));

	ht->malloc_fn = malloc_fn;
	ht->free_fn = free_fn;

	ht->type = libcfu_t_hash_table;
	ht->num_buckets = size;
	ht->entries = 0;
	ht->flags = flags;
	ht->buckets = cfuhash_calloc(ht, size, sizeof(cfuhash_entry *));

#ifdef HAVE_PTHREAD_H
	pthread_mutex_init(&ht->mutex, NULL);
#endif

	ht->hash_func = NULL;
	ht->high = 0.75;
	ht->low = 0.25;

	return ht;
}

cfuhash_table_t *
cfuhash_new(void) {
	return _cfuhash_new(8, CFUHASH_FROZEN_UNTIL_GROWS, NULL, NULL);
}

cfuhash_table_t *
cfuhash_new_with_malloc_fn(cfuhash_malloc_fn_t malloc_fn, 
						   cfuhash_free_fn_t free_fn) {
	return _cfuhash_new(8, CFUHASH_FROZEN_UNTIL_GROWS, malloc_fn, free_fn);
}

cfuhash_table_t *
cfuhash_new_with_initial_size(size_t size) {
	if (size == 0) size = 8;
	return _cfuhash_new(size, CFUHASH_FROZEN_UNTIL_GROWS, NULL, NULL);
}

cfuhash_table_t *
cfuhash_new_with_flags(unsigned int flags) {
	return _cfuhash_new(8, CFUHASH_FROZEN_UNTIL_GROWS|flags, NULL, NULL);
}

cfuhash_table_t * cfuhash_new_with_free_fn(cfuhash_free_fn_t ff) {
	cfuhash_table_t *ht = _cfuhash_new(8, CFUHASH_FROZEN_UNTIL_GROWS, NULL, NULL);
	cfuhash_set_free_function(ht, ff);
	return ht;
}

int
cfuhash_copy(cfuhash_table_t *src, cfuhash_table_t *dst) {
	size_t num_keys = 0;
	void **keys = NULL;
	size_t *key_sizes;
	size_t i = 0;
	void *val = NULL;
	size_t data_size = 0;

	keys = cfuhash_keys_data(src, &num_keys, &key_sizes, 0);

	for (i = 0; i < num_keys; i++) {
		if (cfuhash_get_data(src, (void *)keys[i], key_sizes[i], &val, &data_size)) {
			cfuhash_put_data(dst, (void *)keys[i], key_sizes[i], val, data_size, NULL);
		}
		src->free_fn(keys[i]);
	}

	src->free_fn(keys);
	src->free_fn(key_sizes);

	return 1;
}

cfuhash_table_t *
cfuhash_merge(cfuhash_table_t *ht1, cfuhash_table_t *ht2, unsigned int flags) {
	cfuhash_table_t *new_ht = NULL;

	flags |= CFUHASH_FROZEN_UNTIL_GROWS;
	new_ht = _cfuhash_new(cfuhash_num_entries(ht1) + cfuhash_num_entries(ht2), flags,
						  ht1->malloc_fn, ht1->free_fn);
	if (ht1) cfuhash_copy(ht1, new_ht);
	if (ht2) cfuhash_copy(ht2, new_ht);

	return new_ht;
}

/* returns the flags */
unsigned int
cfuhash_get_flags(cfuhash_table_t *ht) {
	return ht->flags;
}

/* sets the given flag and returns the old flags value */
unsigned int
cfuhash_set_flag(cfuhash_table_t *ht, unsigned int new_flag) {
	unsigned int flags = ht->flags;
	ht->flags = flags | new_flag;
	return flags;
}

unsigned int
cfuhash_clear_flag(cfuhash_table_t *ht, unsigned int new_flag) {
	unsigned int flags = ht->flags;
	ht->flags = flags & ~new_flag;
	return flags;
}

int
cfuhash_set_thresholds(cfuhash_table_t *ht, float low, float high) {
	float h = high < 0 ? ht->high : high;
	float l = low < 0 ? ht->low : low;

	if (h < l) return -1;

	ht->high = h;
	ht->low = l;

	return 0;
}

int cfuhash_set_key_fieldspec(cfuhash_table_t *ht, cfuhash_fieldspec_t fs[]) {
    ht->key_fieldspec = fs;
    return 0;
}

/* Sets the hash function for the hash table ht.  Pass NULL for hf to reset to the default */
int
cfuhash_set_hash_function(cfuhash_table_t *ht, cfuhash_function_t hf) {
	/* can't allow changing the hash function if the hash already contains entries */
	if (ht->entries) return -1;

	ht->hash_func = hf;
	return 0;
}


int cfuhash_set_cmp_function(cfuhash_table_t *ht, cfuhash_cmp_t cmpf) {
	/* can't allow changing the cmp function if the hash already contains entries */
	if (ht->entries) return -1;

	ht->cmp_func = cmpf;
	return 0;
}

int
cfuhash_set_free_function(cfuhash_table_t * ht, cfuhash_free_fn_t ff) {
	if (ff) ht->values_free_fn = ff;
	return 0;
}

static CFU_INLINE void
lock_hash(cfuhash_table_t *ht) {
	if (!ht) return;
	if (ht->flags & CFUHASH_NO_LOCKING) return;
#ifdef HAVE_PTHREAD_H
	pthread_mutex_lock(&ht->mutex);
#endif
}

static CFU_INLINE void
unlock_hash(cfuhash_table_t *ht) {
	if (!ht) return;
	if (ht->flags & CFUHASH_NO_LOCKING) return;
#ifdef HAVE_PTHREAD_H
	pthread_mutex_unlock(&ht->mutex);
#endif
}

int
cfuhash_lock(cfuhash_table_t *ht) {
#ifdef HAVE_PTHREAD_H
	pthread_mutex_lock(&ht->mutex);
#endif
	return 1;
}

int
cfuhash_unlock(cfuhash_table_t *ht) {
#ifdef HAVE_PTHREAD_H
	pthread_mutex_unlock(&ht->mutex);
#endif
	return 1;
}

/* see if this key matches the one in the hash entry */
/* uses the convention that zero means a match, like memcmp */

static CFU_INLINE int
hash_cmp(cfuhash_table_t *ht, const void *key, size_t key_size, 
		 cfuhash_entry *he, unsigned int case_insensitive) {
	if (key_size != he->key_size) return 1;
	if (key == he->key) return 0;
	if (key_size == 0) return 1; /* compare by pointer, not by value */
    if (ht->key_fieldspec) {
        return cfuhash_generic_cmp(ht->key_fieldspec, key, he->key);
    }
	if (ht->cmp_func) {
		return ht->cmp_func(key, key_size, he->key, he->key_size);
	}
	if (case_insensitive) {
		return strncasecmp(key, he->key, key_size);
	}
	return memcmp(key, he->key, key_size);
}

static CFU_INLINE cfuhash_entry *
hash_add_entry(cfuhash_table_t *ht, unsigned int hv, const void *key, size_t key_size,
	void *data, size_t data_size) {
	cfuhash_entry *he = cfuhash_calloc(ht, 1, sizeof(cfuhash_entry));

	assert(hv < ht->num_buckets);

	if (ht->flags & CFUHASH_NOCOPY_KEYS)
		he->key = (void *)key;
	else
		he->key = hash_key_dup(ht, key, key_size);
	he->key_size = key_size;
	he->data = data;
	he->data_size = data_size;
	he->next = ht->buckets[hv];
	ht->buckets[hv] = he;
	ht->entries++;

	return he;
}

static size_t strlen_robust(const char *s) {
    if (s)
        return strlen(s);
    else
        return 0;
}

static int strcmp_robust(const char* a, const char* b) {
    if (a && b)
        return strcmp(a, b);
    return CMP(a, b);
}

static int memcmp_robust(const void* a, const void* b, size_t length) {
    if (a && b)
        return memcmp(a, b, length);
    return CMP(a, b);
}


/*
 Returns one if the entry was found, zero otherwise.  If found, r is
 changed to point to the data in the entry.
*/
int
cfuhash_get_data(cfuhash_table_t *ht, const void *key, size_t key_size, void **r,
	size_t *data_size) {
	unsigned int hv = 0;
	cfuhash_entry *hr = NULL;

	if (!ht) return 0;

	if (key_size == (size_t)(-1)) {
		if (key) key_size = strlen(key) + 1;
		else key_size = 0;

	}

	lock_hash(ht);
	hv = hash_value(ht, key, key_size, ht->num_buckets);

	assert(hv < ht->num_buckets);

	for (hr = ht->buckets[hv]; hr; hr = hr->next) {
		if (!hash_cmp(ht, key, key_size, hr, ht->flags & CFUHASH_IGNORE_CASE)) break;
	}

	if (hr && r) {
		*r = hr->data;
		if (data_size) *data_size = hr->data_size;
	}

	unlock_hash(ht);

	return (hr ? 1 : 0);
}

/*
 Assumes the key is a null-terminated string, returns the data, or NULL if not found.  Note that it is possible for the data itself to be NULL
*/
void *
cfuhash_get(cfuhash_table_t *ht, const char *key) {
	void *r = NULL;
	int rv = 0;

	rv = cfuhash_get_data(ht, (const void *)key, -1, &r, NULL);
	if (rv) return r; /* found */
	return NULL;
}

/* Returns 1 if an entry exists in the table for the given key, 0 otherwise */
int
cfuhash_exists_data(cfuhash_table_t *ht, const void *key, size_t key_size) {
	void *r = NULL;
	int rv = cfuhash_get_data(ht, key, key_size, &r, NULL);
	if (rv) return 1; /* found */
	return 0;
}

/* Same as cfuhash_exists_data(), except assumes key is a null-terminated string */
int
cfuhash_exists(cfuhash_table_t *ht, const char *key) {
	return cfuhash_exists_data(ht, (const void *)key, -1);
}

/*
 Add the entry to the hash.	 If there is already an entry for the
 given key, the old data value will be returned in r, and the return
 value is zero.	 If a new entry is created for the key, the function
 returns 1.
*/
int
cfuhash_put_data(cfuhash_table_t *ht, const void *key, size_t key_size, void *data,
	size_t data_size, void **r) {
	unsigned int hv = 0;
	cfuhash_entry *he = NULL;
	int added_an_entry = 0;

	if (key_size == (size_t)(-1)) {
		if (key) key_size = strlen(key) + 1;
		else key_size = 0;
	}
	if (data_size == (size_t)(-1)) {
		if (data) data_size = strlen(data) + 1;
		else data_size = 0;

	}

	lock_hash(ht);
	hv = hash_value(ht, key, key_size, ht->num_buckets);
	assert(hv < ht->num_buckets);
	for (he = ht->buckets[hv]; he; he = he->next) {
		if (!hash_cmp(ht, key, key_size, he, ht->flags & CFUHASH_IGNORE_CASE)) break;
	}

	if (he) {
		if (r) *r = he->data;
		if (ht->values_free_fn) {
			ht->values_free_fn(he->data);
			if (r) *r = NULL; /* don't return a pointer to a free()'d location */
		}
		he->data = data;
		he->data_size = data_size;
	} else {
		hash_add_entry(ht, hv, key, key_size, data, data_size);
		added_an_entry = 1;
	}

	unlock_hash(ht);

	if (added_an_entry && !(ht->flags & CFUHASH_FROZEN)) {
		if ( (float)ht->entries/(float)ht->num_buckets > ht->high ) cfuhash_rehash(ht);
	}

	return added_an_entry;
}

/*
 Same as cfuhash_put_data(), except the key is assumed to be a
 null-terminated string, and the old value is returned if it existed,
 otherwise NULL is returned.
*/
void *
cfuhash_put(cfuhash_table_t *ht, const char *key, void *data) {
	void *r = NULL;
	if (!cfuhash_put_data(ht, (const void *)key, -1, data, 0, &r)) {
		return r;
	}
	return NULL;
}

void
cfuhash_clear(cfuhash_table_t *ht) {
	cfuhash_entry *he = NULL;
	cfuhash_entry *hep = NULL;
	size_t i = 0;

	lock_hash(ht);
	for (i = 0; i < ht->num_buckets; i++) {
		if ( (he = ht->buckets[i]) ) {
			while (he) {
				hep = he;
				he = he->next;
				if (! (ht->flags & CFUHASH_NOCOPY_KEYS) ) ht->free_fn(hep->key);
				if (ht->values_free_fn) ht->values_free_fn(hep->data);
				ht->free_fn(hep);
			}
			ht->buckets[i] = NULL;
		}
	}
	ht->entries = 0;

	unlock_hash(ht);

	if ( !(ht->flags & CFUHASH_FROZEN) &&
		!( (ht->flags & CFUHASH_FROZEN_UNTIL_GROWS) && !ht->resized_count) ) {
		if ( (float)ht->entries/(float)ht->num_buckets < ht->low ) cfuhash_rehash(ht);
	}

}

void *
cfuhash_delete_data(cfuhash_table_t *ht, const void *key, size_t key_size) {
	unsigned int hv = 0;
	cfuhash_entry *he = NULL;
	cfuhash_entry *hep = NULL;
	void *r = NULL;

	if (key_size == (size_t)(-1)) key_size = strlen(key) + 1;
	lock_hash(ht);
	hv = hash_value(ht, key, key_size, ht->num_buckets);

	for (he = ht->buckets[hv]; he; he = he->next) {
		if (!hash_cmp(ht, key, key_size, he, ht->flags & CFUHASH_IGNORE_CASE)) break;
		hep = he;
	}

	if (he) {
		r = he->data;
		if (hep) hep->next = he->next;
		else ht->buckets[hv] = he->next;

		ht->entries--;
		if (! (ht->flags & CFUHASH_NOCOPY_KEYS) ) ht->free_fn(he->key);
		if (ht->values_free_fn) {
			ht->values_free_fn(he->data);
			r = NULL; /* don't return a pointer to a free()'d location */
		}
		ht->free_fn(he);
	}

	unlock_hash(ht);

	if (he && !(ht->flags & CFUHASH_FROZEN) &&
		!( (ht->flags & CFUHASH_FROZEN_UNTIL_GROWS) && !ht->resized_count) ) {
		if ( (float)ht->entries/(float)ht->num_buckets < ht->low ) cfuhash_rehash(ht);
	}


	return r;
}

void *
cfuhash_delete(cfuhash_table_t *ht, const char *key) {
	return cfuhash_delete_data(ht, key, -1);
}

void **
cfuhash_keys_data(cfuhash_table_t *ht, size_t *num_keys, size_t **key_sizes, int fast) {
	size_t *key_lengths = NULL;
	void **keys = NULL;
	cfuhash_entry *he = NULL;
	size_t bucket = 0;
	size_t entry_index = 0;
	size_t key_count = 0;

	if (!ht) {
		if (key_sizes)
			*key_sizes = NULL;
		*num_keys = 0;
		return NULL;
	}

	if (! (ht->flags & CFUHASH_NO_LOCKING) ) lock_hash(ht);

	if (key_sizes) key_lengths = calloc(ht->entries, sizeof(size_t));
	keys = calloc(ht->entries, sizeof(void *));
	if (!keys) {
		key_lengths = NULL;
		key_count = 0;
		goto exit;
	}

	for (bucket = 0; bucket < ht->num_buckets; bucket++) {
		if ( (he = ht->buckets[bucket]) ) {
			for (; he; he = he->next, entry_index++) {
				if (entry_index >= ht->entries) break; /* this should never happen */

				if (fast) {
					keys[entry_index] = he->key;
				} else {
					keys[entry_index] = calloc(he->key_size, 1);
					memcpy(keys[entry_index], he->key, he->key_size);
				}
				key_count++;

				if (key_lengths) key_lengths[entry_index] = he->key_size;
			}
		}
	}

 exit:
	if (! (ht->flags & CFUHASH_NO_LOCKING) ) unlock_hash(ht);

	if (key_sizes) *key_sizes = key_lengths;
	*num_keys = key_count;

	return keys;
}

void **
cfuhash_keys(cfuhash_table_t *ht, size_t *num_keys, int fast) {
	return cfuhash_keys_data(ht, num_keys, NULL, fast);
}

int
cfuhash_each_data(cfuhash_table_t *ht, void **key, size_t *key_size, void **data,
	size_t *data_size) {

	ht->each_bucket_index = -1;
	ht->each_chain_entry = NULL;

	return cfuhash_next_data(ht, key, key_size, data, data_size);
}

int
cfuhash_next_data(cfuhash_table_t *ht, void **key, size_t *key_size, void **data,
	size_t *data_size) {

	if (ht->each_chain_entry && ht->each_chain_entry->next) {
		ht->each_chain_entry = ht->each_chain_entry->next;
	} else {
		ht->each_chain_entry = NULL;
		ht->each_bucket_index++;
		for (; ht->each_bucket_index < ht->num_buckets; ht->each_bucket_index++) {
			if (ht->buckets[ht->each_bucket_index]) {
				ht->each_chain_entry = ht->buckets[ht->each_bucket_index];
				break;
			}
		}
	}

	if (ht->each_chain_entry) {
		*key = ht->each_chain_entry->key;
		*key_size = ht->each_chain_entry->key_size;
		*data = ht->each_chain_entry->data;
		if (data_size) *data_size = ht->each_chain_entry->data_size;
		return 1;
	}

	return 0;
}

static void
_cfuhash_destroy_entry(cfuhash_table_t *ht, cfuhash_entry *he, cfuhash_free_fn_t ff) {
	if (ff) {
		ff(he->data);
	} else {
		if (ht->values_free_fn) ht->values_free_fn(he->data);
		else {
			if (ht->flags & CFUHASH_FREE_DATA) ht->free_fn(he->data);
		}
	}
	if ( !(ht->flags & CFUHASH_NOCOPY_KEYS) ) ht->free_fn(he->key);
	ht->free_fn(he);
}

size_t
cfuhash_foreach_remove(cfuhash_table_t *ht, cfuhash_remove_fn_t r_fn, cfuhash_free_fn_t ff,
					   void *arg) {
	cfuhash_entry *entry = NULL;
	cfuhash_entry *prev = NULL;
	size_t hv = 0;
	size_t num_removed = 0;
	cfuhash_entry **buckets = NULL;
	size_t num_buckets = 0;

	if (!ht) return 0;

	lock_hash(ht);

	buckets = ht->buckets;
	num_buckets = ht->num_buckets;
	for (hv = 0; hv < num_buckets; hv++) {
		entry = buckets[hv];
		if (!entry) continue;
		prev = NULL;

		while (entry) {
			if (r_fn(entry->key, entry->key_size, entry->data, entry->data_size, arg)) {
				num_removed++;
				if (prev) {
					prev->next = entry->next;
					_cfuhash_destroy_entry(ht, entry, ff);
					entry = prev->next;
				} else {
					buckets[hv] = entry->next;
					_cfuhash_destroy_entry(ht, entry, NULL);
					entry = buckets[hv];
				}
			} else {
				prev = entry;
				entry = entry->next;
			}
		}
	}

	unlock_hash(ht);

	return num_removed;
}

size_t
cfuhash_foreach(cfuhash_table_t *ht, cfuhash_foreach_fn_t fe_fn, void *arg) {
	cfuhash_entry *entry = NULL;
	size_t hv = 0;
	size_t num_accessed = 0;
	cfuhash_entry **buckets = NULL;
	size_t num_buckets = 0;
	int rv = 0;

	if (!ht) return 0;

	lock_hash(ht);

	buckets = ht->buckets;
	num_buckets = ht->num_buckets;
	for (hv = 0; hv < num_buckets && !rv; hv++) {
		entry = buckets[hv];

		for (; entry && !rv; entry = entry->next) {
			num_accessed++;
			rv = fe_fn(entry->key, entry->key_size, entry->data, entry->data_size, arg);
		}
	}

	unlock_hash(ht);

	return num_accessed;
}

int
cfuhash_each(cfuhash_table_t *ht, char **key, void **data) {
	size_t key_size = 0;
	return cfuhash_each_data(ht, (void **)key, &key_size, data, NULL);
}

int
cfuhash_next(cfuhash_table_t *ht, char **key, void **data) {
	size_t key_size = 0;
	return cfuhash_next_data(ht, (void **)key, &key_size, data, NULL);
}

int
cfuhash_destroy_with_free_fn(cfuhash_table_t *ht, cfuhash_free_fn_t ff) {
	size_t i;
	if (!ht) return 0;

	lock_hash(ht);
	for (i = 0; i < ht->num_buckets; i++) {
		if (ht->buckets[i]) {
			cfuhash_entry *he = ht->buckets[i];
			while (he) {
				cfuhash_entry *hn = he->next;
				_cfuhash_destroy_entry(ht, he, ff);
				he = hn;
			}
		}
	}
	ht->free_fn(ht->buckets);
	unlock_hash(ht);
#ifdef HAVE_PTHREAD_H
	pthread_mutex_destroy(&ht->mutex);
#endif
	ht->free_fn(ht);

	return 1;
}

int
cfuhash_destroy(cfuhash_table_t *ht) {
	return cfuhash_destroy_with_free_fn(ht, NULL);
}

typedef struct _pretty_print_arg {
	size_t count;
	FILE *fp;
} _pretty_print_arg;

static int
_pretty_print_foreach(void *key, size_t key_size, void *data, size_t data_size, void *arg) {
	_pretty_print_arg *parg = (_pretty_print_arg *)arg;
	key_size = key_size;
	data_size = data_size;
	parg->count += fprintf(parg->fp, "\t\"%s\" => \"%s\",\n", (char *)key, (char *)data);
	return 0;
}

int
cfuhash_pretty_print(cfuhash_table_t *ht, FILE *fp) {
	int rv = 0;
	_pretty_print_arg parg;

	parg.fp = fp;
	parg.count = 0;

	rv += fprintf(fp, "{\n");

	cfuhash_foreach(ht, _pretty_print_foreach, (void *)&parg);
	rv += parg.count;

	rv += fprintf(fp, "}\n");

	return rv;
}

int
cfuhash_rehash(cfuhash_table_t *ht) {
	size_t new_size, i;
	cfuhash_entry **new_buckets = NULL;

	lock_hash(ht);
	new_size = hash_size(ht->entries * 2 / (ht->high + ht->low));
	if (new_size == ht->num_buckets) {
		unlock_hash(ht);
		return 0;
	}
	new_buckets = cfuhash_calloc(ht, new_size, sizeof(cfuhash_entry *));

	for (i = 0; i < ht->num_buckets; i++) {
		cfuhash_entry *he = ht->buckets[i];
		while (he) {
			cfuhash_entry *nhe = he->next;
			unsigned int hv = hash_value(ht, he->key, he->key_size, new_size);
			he->next = new_buckets[hv];
			new_buckets[hv] = he;
			he = nhe;
		}
	}

	ht->num_buckets = new_size;
	ht->free_fn(ht->buckets);
	ht->buckets = new_buckets;
	ht->resized_count++;

	unlock_hash(ht);
	return 1;
}

size_t
cfuhash_num_entries(cfuhash_table_t *ht) {
	if (!ht) return 0;
	return ht->entries;
}

size_t
cfuhash_num_buckets(cfuhash_table_t *ht) {
	if (!ht) return 0;
	return ht->num_buckets;
}

size_t
cfuhash_num_buckets_used(cfuhash_table_t *ht) {
	size_t i = 0;
	size_t count = 0;

	if (!ht) return 0;

	lock_hash(ht);

	for (i = 0; i < ht->num_buckets; i++) {
		if (ht->buckets[i]) count++;
	}
	unlock_hash(ht);
	return count;
}

int cfuhash_generic_cmp(cfuhash_fieldspec_t fields[], const void* a, const void* b)
{
    if (!(a && b))
        return CMP(a, b);

    int i;
    for(i=0; fields[i].kind != cfuhash_fieldspec_stop; i++) {
        int j;
        cfuhash_fieldspec_t *field = fields+i;
        size_t offset = field->offset;
        void* field_a = NULL;
        void* field_b = NULL;
        void* item_a = NULL;
        void* item_b = NULL;
        size_t array_length_a = 0;
        size_t array_length_b = 0;
        int cmp;

        switch(field->kind) {
        case cfuhash_primitive:
            cmp = memcmp_robust(a+offset, b+offset, field->size);
            break;
        case cfuhash_pointer:
        case cfuhash_array:
            if (field->kind == cfuhash_pointer) {
                // if it's a pointer, the lenght is in the fieldspec
                array_length_a = field->length;
                array_length_b = field->length;
            }
            else {
                // if it's an array, the lenght is a field of the object,
                // placed at lenght_offset
                array_length_a = FIELD(size_t, a, field->length_offset);
                array_length_b = FIELD(size_t, b, field->length_offset);
                if (array_length_a != array_length_b) {
                    // if the two objects have different lenghts, they are different
                    cmp = CMP(array_length_a, array_length_b);
                    break;
                }
            }
            field_a = FIELD(void*, a, offset);
            field_b = FIELD(void*, b, offset);
            for(j=0; j<array_length_a; j++) {
                item_a = field_a + (j*field->size);
                item_b = field_b + (j*field->size);
                cmp = cfuhash_generic_cmp(field->fieldspec, item_a, item_b);
                if (cmp != 0)
                    return cmp;
            }
            break;
        case cfuhash_string:
            field_a = FIELD(void*, a, offset);
            field_b = FIELD(void*, b, offset);
            cmp = strcmp_robust(field_a, field_b);
            break;
        default:
            fprintf(stderr, "cfuhash_generic_cmp: unknown field kind: %d\n", field->kind);
            abort();
        }
        if (cmp != 0)
            return cmp;
    }
    return 0;
}

unsigned int cfuhash_generic_hash_impl(unsigned int hv, cfuhash_fieldspec_t fields[], 
                                       const void* a)
{
    if (!a)
        return hv;

    int i;
    for(i=0; fields[i].kind != cfuhash_fieldspec_stop; i++) {
        int j;
        cfuhash_fieldspec_t *field = fields+i;
        size_t offset = field->offset;
        size_t array_length;
        void* field_a = NULL;
        void* item_a = NULL;

        switch(field->kind) {
        case cfuhash_primitive:
            hv = hash_func_part(hv, a+offset, field->size);
            break;
        case cfuhash_pointer:
        case cfuhash_array:
            if (field->kind == cfuhash_pointer) {
                array_length = field->length;
            }
            else {
                array_length = FIELD(size_t, a, field->length_offset);
            }
            field_a = FIELD(void*, a, offset);
            for(j=0; j<array_length; j++) {
                item_a = field_a + (j*field->size);
                hv = cfuhash_generic_hash_impl(hv, field->fieldspec, item_a);
            }
            break;
        case cfuhash_string:
            field_a = FIELD(void*, a, offset);
            hv = hash_func_part(hv, field_a, strlen_robust(field_a));
            break;
        default:
            fprintf(stderr, "cfuhash_generic_hash: unknown field kind: %d\n", field->kind);
            abort();
        }
    }
    return hv;
}


unsigned int cfuhash_generic_hash(cfuhash_fieldspec_t fields[], const void* key) {
    unsigned int hv = 0;
    hv = cfuhash_generic_hash_impl(hv, fields, key);
    return hash_func_finalize(hv);
}

