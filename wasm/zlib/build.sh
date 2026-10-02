#!/bin/sh
# zlib for wasm32-wasip1 as a PIC archive with hidden symbols: each library links
# its own copy in, as nothing calls zlib across modules.
#
# Usage: build.sh OUT
#   OUT/include  zlib.h and zconf.h
#   OUT/lib      libz.a
set -e

VERSION=1.3.1
OUT=$(realpath "$1")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}

src=$OUT/src
mkdir -p "$src" "$OUT/obj" "$OUT/lib" "$OUT/include"
if [ ! -f "$src/zlib.h" ]; then
  curl -sSfL "https://github.com/madler/zlib/releases/download/v$VERSION/zlib-$VERSION.tar.gz" | tar xz -C "$src" --strip-components=1
fi

for f in adler32 compress crc32 deflate gzclose gzlib gzread gzwrite infback inffast inflate inftrees trees uncompr zutil; do
  # shellcheck disable=SC2086
  "$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=hidden -DHAVE_UNISTD_H \
    -c "$src/$f.c" -o "$OUT/obj/$f.o"
done
rm -f "$OUT/lib/libz.a"
"$AR" rcs "$OUT/lib/libz.a" "$OUT"/obj/*.o
cp "$src/zlib.h" "$src/zconf.h" "$OUT/include/"
