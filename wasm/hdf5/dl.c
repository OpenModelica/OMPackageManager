/* HDF5's plugin loader calls these even with plugin support off; WASI has no
 * dynamic loading, so every plugin lookup fails. */
#include <stddef.h>

void *dlopen(const char *file, int mode) {
  (void)file;
  (void)mode;
  return NULL;
}

void *dlsym(void *handle, const char *name) {
  (void)handle;
  (void)name;
  return NULL;
}

int dlclose(void *handle) {
  (void)handle;
  return 0;
}

char *dlerror(void) {
  return "dynamic loading is not supported in WebAssembly";
}
