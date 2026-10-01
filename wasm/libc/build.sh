#!/bin/sh
# wasi-libc for wasm32-wasip1 as a PIC shared library, with the sysroot
# everything else is compiled against. One libc is loaded per simulation, so
# every module of a generation is built against this one.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: libc.so
#   OUT/sysroot  headers, libc.so and the compiler-rt builtins to build against
set -e

VERSION=wasi-sdk-32
SHA256=ea9827495c0f35bca3b3d0a953e854cac112c43bea3196b5a4f7f8fc4704b9a4
OUT=$(realpath "$1")
CLANG=${OMC_WASI_CLANG:-clang}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}
RANLIB=${RANLIB:-$(command -v llvm-ranlib || ls /usr/bin/llvm-ranlib-* | sort -V | tail -1)}
BUILTINS=${OMC_WASI_BUILTINS:-$("$CLANG" -print-resource-dir)/lib/wasi/libclang_rt.builtins-wasm32.a}

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist"
if [ ! -f "$src/CMakeLists.txt" ]; then
  curl -sSfL -o "$OUT/libc.tar.gz" "https://github.com/WebAssembly/wasi-libc/archive/refs/tags/$VERSION.tar.gz"
  echo "$SHA256  $OUT/libc.tar.gz" | sha256sum -c -
  tar xzf "$OUT/libc.tar.gz" -C "$src" --strip-components=1
  rm "$OUT/libc.tar.gz"
fi

cat > "$build/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME WASI)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_SYSROOT $build/sysroot)
set(CMAKE_AR $AR)
set(CMAKE_RANLIB $RANLIB)
set(CMAKE_C_FLAGS_INIT "$CPU -O2")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
TOOLCHAIN

cmake -S "$src" -B "$build" -DCMAKE_TOOLCHAIN_FILE="$build/toolchain.cmake" -DBUILD_SHARED=ON \
  -DBUILD_TESTS=OFF -DCMAKE_LINK_DEPENDS_USE_LINKER=OFF -DBUILTINS_LIB="$BUILTINS"
cmake --build "$build" --parallel

rm -rf "$OUT/sysroot"
cp -r "$build/sysroot" "$OUT/sysroot"
cp "$BUILTINS" "$OUT/sysroot/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"
cp "$OUT/sysroot/lib/wasm32-wasip1/libc.so" "$OUT/dist/libc.so"
