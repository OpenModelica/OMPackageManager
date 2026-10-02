/* Declarations wasi-libc withholds while H5private.h uses them anyway; qsort_r
 * is in the library with its prototype hidden. */
#include <stddef.h>
static inline void tzset(void) {}
void qsort_r(void *, size_t, size_t, int (*)(const void *, const void *, void *), void *);
