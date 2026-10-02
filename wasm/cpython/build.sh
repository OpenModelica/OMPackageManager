#!/bin/sh
# CPython for wasm32-wasip1 as a PIC dylink module, which the OpenModelica wasm
# runtime loads into the simulation's memory beside the external "C" code that
# embeds Python.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: the module and the standard library
#   OUT/include  the headers the embedding code is compiled against
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=3.14.4
PYVER=3.14
# The wasi-libc the libc system library is built from.
WASI_LIBC=wasi-sdk-32
OUT=$(realpath "$1")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
BUILD_PYTHON=${BUILD_PYTHON:-python$PYVER}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist/lib" "$OUT/include"
if [ ! -f "$src/configure" ]; then
  curl -sSfL "https://www.python.org/ftp/python/$VERSION/Python-$VERSION.tgz" | tar xz -C "$src" --strip-components=1
fi

cd "$build"
if [ ! -f Makefile ]; then
  CONFIG_SITE="$src/Tools/wasm/wasi/config.site-wasm32-wasi" \
  CC="$CLANG --target=wasm32-wasip1 $CPU --sysroot=$SYSROOT" \
  CPP="$CLANG --target=wasm32-wasip1 $CPU --sysroot=$SYSROOT -E" \
  CFLAGS="-fPIC -O2" \
  LDFLAGS="-nodefaultlibs" \
  LIBS="-lc $SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a" \
  AR="$AR" RANLIB=true \
  PKG_CONFIG_PATH= PKG_CONFIG_LIBDIR="$SYSROOT/lib/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$SYSROOT" \
  ac_cv_func_dlopen=no ac_cv_lib_dl_dlopen=no \
  "$src/configure" --host=wasm32-wasip1 --build="$("$src/config.guess")" \
    --with-build-python="$BUILD_PYTHON" --prefix=/ \
    --disable-test-modules --without-ensurepip --disable-ipv6
fi
make -j"$(nproc)" "libpython$PYVER.a" Modules/expat/libexpat.a Modules/_decimal/libmpdec/libmpdec.a \
  $(sed -n 's/^LIBHACL_\(.*\)_LIB_STATIC=//p' Makefile)

# The sysroot ships the WASI emulation libraries PIC only as shared libraries,
# which nothing would load, so their sources are compiled into the module.
libc=$OUT/wasi-libc
if [ ! -d "$libc" ]; then
  mkdir -p "$libc"
  curl -sSfL "https://github.com/WebAssembly/wasi-libc/archive/refs/tags/$WASI_LIBC.tar.gz" | tar xz -C "$libc" --strip-components=1
fi
emulated=""
for f in libc-bottom-half/signal/signal.c libc-bottom-half/getpid/getpid.c \
         libc-bottom-half/clocks/clock.c libc-bottom-half/clocks/getrusage.c libc-bottom-half/clocks/times.c \
         libc-top-half/musl/src/signal/psignal.c libc-top-half/musl/src/string/strsignal.c; do
  case $f in
    libc-top-half/*) inc="-I$libc/libc-top-half/musl/src/internal -I$libc/libc-top-half/musl/src/include" ;;
    *) inc="-I$libc/libc-bottom-half/headers/private -I$libc/libc-bottom-half/cloudlibc/src" ;;
  esac
  o=emulated-$(basename "$f" .c).o
  "$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -O2 -Wno-macro-redefined $inc \
    -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_GETPID -D_WASI_EMULATED_PROCESS_CLOCKS -c "$libc/$f" -o "$o"
  emulated="$emulated $o"
done

# Every module the WASI build has is built into libpython; the other archives
# are what those modules use.
archives="$(ls Modules/expat/libexpat.a Modules/_decimal/libmpdec/libmpdec.a Modules/_hacl/*.a 2>/dev/null)"
# libc itself is the runtime's own libc.so.
"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -shared -nodefaultlibs \
  -Wl,--export-all -Wl,--allow-undefined -O2 \
  -o "$OUT/dist/libpython$PYVER.wasm" \
  -Wl,--whole-archive "libpython$PYVER.a" -Wl,--no-whole-archive $archives $emulated \
  "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"

# The standard library, uncompressed: zipimport needs zlib only to inflate.
rm -f "$OUT/dist/lib/python${PYVER%.*}${PYVER#*.}.zip"
(cd "$src/Lib" && "$BUILD_PYTHON" - "$OUT/dist/lib/python${PYVER%.*}${PYVER#*.}.zip" <<'EOF'
import os, sys, zipfile
skip = {"test", "idlelib", "tkinter", "turtledemo", "ensurepip", "venv", "lib2to3", "__pycache__"}
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_STORED) as z:
    for root, dirs, files in os.walk("."):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(root, f)
                info = zipfile.ZipInfo(os.path.normpath(p), (1980, 1, 1, 0, 0, 0))
                with open(p, "rb") as fh:
                    z.writestr(info, fh.read())
EOF
)
mkdir -p "$OUT/dist/lib/python$PYVER/lib-dynload"
cp "$build"/build/lib.wasi-wasm32-$PYVER/_sysconfigdata_*.py "$OUT/dist/lib/python$PYVER/" 2>/dev/null || true

rm -rf "$OUT/include/python$PYVER"
mkdir -p "$OUT/include/python$PYVER"
cp -r "$src/Include/." "$OUT/include/python$PYVER/"
cp pyconfig.h "$OUT/include/python$PYVER/"
