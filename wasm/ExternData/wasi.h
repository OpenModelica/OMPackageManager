/* POSIX functions WASI does not have, which the sources call without a fallback.
 * WASI cannot duplicate a descriptor: `dup` hands out the same one, counted, and
 * `close` closes it with the last reference, so the offset is shared as with POSIX. */
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <unistd.h>

static inline char *mkdtemp(char *template_) {
  (void)template_;
  errno = ENOSYS;
  return NULL;
}

#define OMC_WASI_MAX_FD 1024
static unsigned short omc_wasi_dups[OMC_WASI_MAX_FD] __attribute__((unused));

static inline int dup(int fd) {
  if (fd < 0 || fd >= OMC_WASI_MAX_FD || fcntl(fd, F_GETFD) == -1) {
    errno = EBADF;
    return -1;
  }
  omc_wasi_dups[fd]++;
  return fd;
}

static inline int omc_wasi_close(int fd) {
  if (fd >= 0 && fd < OMC_WASI_MAX_FD && omc_wasi_dups[fd]) {
    omc_wasi_dups[fd]--;
    return 0;
  }
  return close(fd);
}
#define close omc_wasi_close
