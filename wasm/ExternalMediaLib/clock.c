/* CoolProp times itself with clock(), which wasi-libc only has with the
 * emulated process clocks; elapsed time serves as well. */
#include <time.h>

clock_t clock(void);

clock_t clock(void) {
  static struct timespec start;
  struct timespec now;
  if (start.tv_sec == 0 && start.tv_nsec == 0) {
    clock_gettime(CLOCK_MONOTONIC, &start);
  }
  clock_gettime(CLOCK_MONOTONIC, &now);
  return (clock_t)((now.tv_sec - start.tv_sec) * CLOCKS_PER_SEC +
                   (now.tv_nsec - start.tv_nsec) / (1000000000 / CLOCKS_PER_SEC));
}
