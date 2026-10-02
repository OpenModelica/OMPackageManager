#!/bin/sh
# ModelicaSDF (SDF-Modelica's C/) for wasm32-wasip1 as a PIC dylink module, with
# HDF5, zlib and matio linked in privately as its native build does, and its C++
# against libc++. SYSLIB_hdf5, SYSLIB_zlib and SYSLIB_libcxx are those system
# libraries.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: the module
#   OUT/include  the header
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=0.4.5
MATIO_VERSION=1.5.28
OUT=$(realpath "$1")
HERE=$(dirname "$(realpath "$0")")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CLANGXX=${OMC_WASI_CLANGXX:-$(dirname "$(command -v "$CLANG")")/$(basename "$CLANG" | sed 's/clang/clang++/')}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}
RANLIB=${RANLIB:-$(command -v llvm-ranlib || ls /usr/bin/llvm-ranlib-* | sort -V | tail -1)}
EH="-fwasm-exceptions -mllvm -wasm-use-legacy-eh=false"

src=$OUT/src
mkdir -p "$src" "$OUT/dist" "$OUT/include"
if [ ! -f "$src/C/src/ModelicaSDFFunctions.c" ]; then
  curl -sSfL "https://github.com/ScientificDataFormat/SDF-Modelica/archive/refs/tags/v$VERSION.tar.gz" | tar xz -C "$src" --strip-components=1
fi

# matio for dsres.cpp, which reads only MAT v4 result files.
matio=$OUT/matio
if [ ! -f "$matio/src/CMakeLists.txt" ]; then
  mkdir -p "$matio/src"
  curl -sSfL "https://github.com/tbeu/matio/releases/download/v$MATIO_VERSION/matio-$MATIO_VERSION.tar.gz" |
    tar xz -C "$matio/src" --strip-components=1
fi
cat > "$matio/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME WASI)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_SYSROOT $SYSROOT)
set(CMAKE_AR $AR)
set(CMAKE_RANLIB $RANLIB)
set(CMAKE_C_FLAGS_INIT "$CPU -fvisibility=hidden -include $HERE/../wasi.h")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
TOOLCHAIN
cmake -S "$matio/src" -B "$matio/build" -DCMAKE_TOOLCHAIN_FILE="$matio/toolchain.cmake" -DCMAKE_BUILD_TYPE=Release \
  -DMATIO_SHARED=OFF -DMATIO_PIC=ON -DMATIO_MAT73=OFF \
  -DMATIO_WITH_HDF5=OFF -DMATIO_WITH_ZLIB=OFF -DMATIO_BUILD_TESTING=OFF
cmake --build "$matio/build" --parallel --target matio

"$CLANGXX" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=default $EH -nostdinc++ \
  -isystem "$SYSLIB_libcxx/include/c++/v1" -I"$src/C/include" -I"$matio/src/src" -I"$matio/build/src" \
  -c "$src/C/src/dsres.cpp" -o "$OUT/dsres.o"
"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=default -shared -nodefaultlibs \
  -Wl,--allow-undefined -I"$src/C/include" -I"$SYSLIB_hdf5/include" \
  -o "$OUT/dist/libModelicaSDF.wasm" "$src/C/src/ModelicaSDFFunctions.c" "$OUT/dsres.o" \
  "$matio/build/libmatio.a" "$SYSLIB_hdf5/lib/libhdf5_hl.a" "$SYSLIB_hdf5/lib/libhdf5.a" \
  "$SYSLIB_zlib/lib/libz.a" "$SYSLIB_libcxx/lib/libc++.so" "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"

cp "$src/C/include/ModelicaSDFFunctions.h" "$OUT/include/"
