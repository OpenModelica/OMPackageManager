/* Resources/C-Sources/pythonWrapper.c calls this without a prototype. A wasm
 * import is typed by its declaration, and the implicit `int` one does not link
 * against the real function. */
#include <stddef.h>

void pythonExchangeValuesNoModelica(const char * moduleName,
                                    const char * functionName,
                                    const char * pythonPath,
                                    const double * dblValWri, size_t nDblWri,
                                    double * dblValRea, size_t nDblRea,
                                    const int * intValWri, size_t nIntWri,
                                    int * intValRea, size_t nIntRea,
                                    const char ** strValWri, size_t nStrWri,
                                    void (*inModelicaFormatError)(const char *string, ...),
                                    void* object,
                                    int have_memory);
