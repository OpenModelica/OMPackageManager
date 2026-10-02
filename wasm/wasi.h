/* What C sources written for POSIX call that WASI does not have: musl's temporary
 * names over the mkdir and stat wasi-libc does have, and a process id. */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>

static char *omc_wasi_randname(char *suffix) {
  static unsigned long counter;
  struct timeval tv;
  unsigned long r;
  int i;
  gettimeofday(&tv, NULL);
  r = (unsigned long)tv.tv_usec * 65537UL ^ ((unsigned long)(uintptr_t)&tv / 16 + counter++);
  for (i = 0; i < 6; i++, r >>= 5) {
    suffix[i] = 'A' + (r & 15) + (r & 16) * 2;
  }
  return suffix;
}

static __attribute__((unused)) char *omc_wasi_mkdtemp(char *template_) {
  size_t l = strlen(template_);
  int retries;
  if (l < 6 || memcmp(template_ + l - 6, "XXXXXX", 6) != 0) {
    errno = EINVAL;
    return NULL;
  }
  for (retries = 100; retries > 0; retries--) {
    omc_wasi_randname(template_ + l - 6);
    if (mkdir(template_, 0700) == 0) {
      return template_;
    }
    if (errno != EEXIST) {
      return NULL;
    }
  }
  memcpy(template_ + l - 6, "XXXXXX", 6);
  errno = EEXIST;
  return NULL;
}

static __attribute__((unused)) char *omc_wasi_tmpnam(char *s) {
  static char internal[sizeof "/tmp/tmpnam_XXXXXX"];
  char path[] = "/tmp/tmpnam_XXXXXX";
  struct stat st;
  int retries;
  for (retries = 100; retries > 0; retries--) {
    omc_wasi_randname(path + sizeof(path) - 7);
    if (stat(path, &st) != 0 && errno == ENOENT) {
      return strcpy(s ? s : internal, path);
    }
  }
  return NULL;
}

static __attribute__((unused)) char *omc_wasi_mktemp(char *template_) {
  size_t l = strlen(template_);
  struct stat st;
  int retries;
  if (l < 6 || memcmp(template_ + l - 6, "XXXXXX", 6) != 0) {
    errno = EINVAL;
    *template_ = 0;
    return template_;
  }
  for (retries = 100; retries > 0; retries--) {
    omc_wasi_randname(template_ + l - 6);
    if (stat(template_, &st) != 0 && errno == ENOENT) {
      return template_;
    }
  }
  *template_ = 0;
  return template_;
}

static __attribute__((unused)) int omc_wasi_getpid(void) {
  return 1;
}

#define mkdtemp omc_wasi_mkdtemp
#define mktemp omc_wasi_mktemp
#define tmpnam omc_wasi_tmpnam
#define getpid omc_wasi_getpid
