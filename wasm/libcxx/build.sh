#!/bin/sh
# libc++, libc++abi and libunwind for wasm32-wasip1 as one PIC dylink module,
# with exnref exceptions. Every C++ module of a generation links against it, so
# one C++ runtime is loaded per simulation, as one libc is.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: libc++.so
#   OUT/include  the libc++ headers
#   OUT/lib      libc++.so to link against
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=21.1.8
OUT=$(realpath "$1")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CLANGXX=${OMC_WASI_CLANGXX:-$(dirname "$(command -v "$CLANG")")/$(basename "$CLANG" | sed 's/clang/clang++/')}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}
RANLIB=${RANLIB:-$(command -v llvm-ranlib || ls /usr/bin/llvm-ranlib-* | sort -V | tail -1)}
EH="-fwasm-exceptions -mllvm -wasm-use-legacy-eh=false"

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist" "$OUT/lib"
if [ ! -f "$src/libc/CMakeLists.txt" ]; then
  top=llvm-project-$VERSION.src
  curl -sSfL "https://github.com/llvm/llvm-project/releases/download/llvmorg-$VERSION/$top.tar.xz" |
    tar xJ -C "$src" --strip-components=1 \
      $top/runtimes $top/libcxx $top/libcxxabi $top/libunwind $top/cmake $top/llvm/cmake $top/llvm/utils/llvm-lit $top/third-party $top/libc
fi

# llvm/llvm-project#168449: libunwind exports with __declspec on wasm.
sed -i 's/^\(  #if !defined(__ELF__) && !defined(__MACH__) && !defined(_AIX)\)$/\1 \&\& !defined(__wasm__)/' \
  "$src/libunwind/src/config.h"
# Register save/restore is native unwinding; wasm unwinds in the engine.
: > "$src/libunwind/src/UnwindRegistersSave.S"
: > "$src/libunwind/src/UnwindRegistersRestore.S"

cat > "$build/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME WASI)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_CXX_COMPILER $CLANGXX)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_CXX_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_ASM_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_SYSROOT $SYSROOT)
set(CMAKE_AR $AR)
set(CMAKE_RANLIB $RANLIB)
set(CMAKE_C_FLAGS_INIT "$CPU $EH")
set(CMAKE_CXX_FLAGS_INIT "$CPU $EH")
set(CMAKE_ASM_FLAGS_INIT "$CPU")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
TOOLCHAIN

# Archives of PIC objects, linked into one module below: the three need each
# other, and an exception must find one copy of their state.
cmake -S "$src/runtimes" -B "$build" -DCMAKE_TOOLCHAIN_FILE="$build/toolchain.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$build/install" -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DLLVM_ENABLE_RUNTIMES="libunwind;libcxx;libcxxabi" -DLLVM_COMPILER_CHECKED=ON -DUNIX=ON \
  -DLIBCXX_ENABLE_SHARED=OFF -DLIBCXXABI_ENABLE_SHARED=OFF -DLIBUNWIND_ENABLE_SHARED=OFF \
  -DLIBCXX_ENABLE_EXCEPTIONS=ON -DLIBCXXABI_ENABLE_EXCEPTIONS=ON -DLIBCXXABI_USE_LLVM_UNWINDER=ON \
  -DLIBCXX_ENABLE_THREADS=ON -DLIBCXX_HAS_PTHREAD_API=ON -DLIBCXXABI_ENABLE_THREADS=ON \
  -DLIBCXXABI_HAS_PTHREAD_API=ON -DLIBUNWIND_ENABLE_THREADS=ON \
  -DLIBCXX_ENABLE_FILESYSTEM=ON -DLIBCXX_ENABLE_ABI_LINKER_SCRIPT=OFF -DLIBCXX_CXX_ABI=libcxxabi \
  -DLIBCXX_HAS_MUSL_LIBC=OFF -DLIBCXX_ABI_VERSION=2 -DLIBCXXABI_SILENT_TERMINATE=ON \
  -DLIBUNWIND_USE_COMPILER_RT=ON -DLIBCXX_INCLUDE_TESTS=OFF -DLIBCXX_INCLUDE_BENCHMARKS=OFF \
  -DLIBCXXABI_INCLUDE_TESTS=OFF -DLIBUNWIND_INCLUDE_TESTS=OFF -DLIBCXX_ENABLE_STATIC_ABI_LIBRARY=ON
cmake --build "$build" --parallel
cmake --install "$build"

"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -shared -nodefaultlibs -O2 \
  -Wl,--no-entry -Wl,--export-all -Wl,--allow-undefined -o "$OUT/dist/libc++.so" \
  -Wl,--whole-archive "$build/install/lib/libc++.a" "$build/install/lib/libunwind.a" -Wl,--no-whole-archive \
  "$SYSROOT/lib/wasm32-wasip1/libc.so" "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"
cp "$OUT/dist/libc++.so" "$OUT/lib/libc++.so"
rm -rf "$OUT/include"
cp -r "$build/install/include" "$OUT/include"
