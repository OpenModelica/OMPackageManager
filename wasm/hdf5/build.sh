#!/bin/sh
# HDF5 with its high-level library and the deprecated API for wasm32-wasip1 as
# PIC archives with hidden symbols: a library links its own copy in, so it does
# not depend on, or clash with, the HDF5 of whichever omc loads it. It calls
# zlib, which the library links in too; SYSLIB_zlib is the zlib system library.
#
# Usage: build.sh OUT
#   OUT/include  the headers the code using it is compiled against
#   OUT/lib      the archives
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=2.2.0
OUT=$(realpath "$1")
HERE=$(dirname "$(realpath "$0")")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build"
if [ ! -f "$src/CMakeLists.txt" ]; then
  curl -sSfL "https://github.com/HDFGroup/hdf5/archive/refs/tags/$VERSION.tar.gz" | tar xz -C "$src" --strip-components=1
fi

# CMake links its probes as executables, and clang looks for the builtins under
# its resource directory, where Debian does not put the wasm32 ones.
res=$build/clang-resource
mkdir -p "$res/lib/wasm32-unknown-wasip1"
ln -sfn "$("$CLANG" -print-resource-dir)/include" "$res/include"
ln -sf "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a" "$res/lib/wasm32-unknown-wasip1/libclang_rt.builtins.a"

# WASI has neither flock(2) nor fcntl(2) record locks; saying so makes HDF5 use
# its own Nflock(), which succeeds. -wasm-enable-sjlj only silences setjmp.h.
cat > "$build/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME WASI)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_SYSROOT $SYSROOT)
set(CMAKE_AR $AR)
set(CMAKE_C_FLAGS_INIT "$CPU -O2 -fPIC -fvisibility=hidden -resource-dir=$res -mllvm -wasm-enable-sjlj -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_PROCESS_CLOCKS -D_WASI_EMULATED_MMAN -D_WASI_EMULATED_GETPID -I$SYSLIB_zlib/include -include $HERE/wasi.h")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(H5_HAVE_FLOCK "" CACHE INTERNAL "")
set(H5_HAVE_FCNTL "" CACHE INTERNAL "")
TOOLCHAIN

# The try_run() probes cannot run when cross-compiling.
probes=""
for v in TEST_LFS_WORKS H5_PRINTF_LL_TEST H5_LDOUBLE_TO_LONG_SPECIAL H5_LONG_TO_LDOUBLE_SPECIAL \
         H5_LDOUBLE_TO_LLONG_ACCURATE H5_LLONG_TO_LDOUBLE_CORRECT H5_DISABLE_SOME_LDOUBLE_CONV \
         H5_NO_ALIGNMENT_RESTRICTIONS; do
  probes="$probes -D${v}_RUN=OFF -D${v}_RUN__TRYRUN_OUTPUT="
done

# shellcheck disable=SC2086
cmake -S "$src" -B "$build" -DCMAKE_TOOLCHAIN_FILE="$build/toolchain.cmake" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$OUT" -DCMAKE_INSTALL_LIBDIR=lib -DHDF5_NO_PACKAGES=ON \
  -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF -DHDF5_BUILD_TOOLS=OFF -DHDF5_BUILD_EXAMPLES=OFF \
  -DHDF5_BUILD_JAVA=OFF -DHDF5_BUILD_FORTRAN=OFF -DHDF5_BUILD_CPP_LIB=OFF -DHDF5_BUILD_UTILS=OFF \
  -DHDF5_ENABLE_PARALLEL=OFF -DHDF5_ENABLE_THREADSAFE=OFF -DHDF5_ENABLE_SZIP_SUPPORT=OFF \
  -DHDF5_ENABLE_PLUGIN_SUPPORT=OFF -DHDF5_BUILD_HL_LIB=ON -DHDF5_ENABLE_DEPRECATED_SYMBOLS=ON \
  -DHDF5_ENABLE_ZLIB_SUPPORT=ON -DH5_ZLIB_HEADER=zlib.h $probes
cmake --build "$build" -j"$(nproc)"
cmake --install "$build"
"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=hidden -c "$HERE/dl.c" -o "$build/dl.o"
"$AR" rs "$OUT/lib/libhdf5.a" "$build/dl.o"
