/* gzclose would close the descriptor behind the counted `dup` of wasi.h, so
 * libxml2 reads gzip-compressed files as they are. */
#include "wasi.h"

struct gzFile_s;
static inline struct gzFile_s *omc_wasi_gzdopen(int fd, const char *mode) {
  (void)fd;
  (void)mode;
  return NULL;
}
#define gzdopen omc_wasi_gzdopen
