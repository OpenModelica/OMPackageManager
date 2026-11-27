#!/bin/sh
# ExternalMedia's ExternalMediaLib with CoolProp for wasm32-wasip1 as a PIC dylink
# module against libc++. SYSLIB_libcxx is that system library.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: the module
#   OUT/include  the header
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=4.1.2
# What ExternalMedia's CMake project clones.
COOLPROP_VERSION=8.1.0
OUT=$(realpath "$1")
HERE=$(dirname "$(realpath "$0")")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CLANGXX=${OMC_WASI_CLANGXX:-$(dirname "$(command -v "$CLANG")")/$(basename "$CLANG" | sed 's/clang/clang++/')}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}
EH="-fwasm-exceptions -mllvm -wasm-use-legacy-eh=false"
CXXINC="-nostdinc++ -isystem $SYSLIB_libcxx/include/c++/v1"

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist" "$OUT/include"
rm -rf "$build/wasi-include"
cp -r "$HERE/include" "$build/wasi-include"
if [ ! -f "$src/Projects/CMakeLists.txt" ]; then
  curl -sSfL "https://github.com/modelica-3rdparty/ExternalMedia/archive/refs/tags/v$VERSION.tar.gz" |
    tar xz -C "$src" --strip-components=1
fi
# The release sources, unlike the git tag, carry the generated headers.
if [ ! -d "$build/CoolProp.sources" ]; then
  curl -sSfL --retry 5 --retry-all-errors -C - --speed-limit 10000 --speed-time 60 -o "$build/coolprop.zip" \
    "https://sourceforge.net/projects/coolprop/files/CoolProp/$COOLPROP_VERSION/source/CoolProp_sources.zip/download"
  (cd "$build" && unzip -q coolprop.zip && mv source CoolProp.sources && rm coolprop.zip)
fi

# CoolProp takes WASI for POSIX with __posix (REFPROP's dlopen then fails), and
# embeds its fluid data with .incbin, which wasm objects do not have.
cat > "$build/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME WASI)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_CXX_COMPILER $CLANGXX)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_CXX_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_SYSROOT $SYSROOT)
set(CMAKE_AR $AR)
set(CMAKE_C_FLAGS_INIT "$CPU -fPIC -fvisibility=hidden")
set(CMAKE_CXX_FLAGS_INIT "$CPU -fPIC -fvisibility=hidden $EH $CXXINC -D__posix -DCOOLPROP_NO_INCBIN -I$build/wasi-include")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
TOOLCHAIN
cmake -S "$HERE" -B "$build/cmake" -DCMAKE_TOOLCHAIN_FILE="$build/toolchain.cmake" -DCMAKE_BUILD_TYPE=Release \
  -DCOOLPROP_SOURCES="$build/CoolProp.sources" -DEXTERNALMEDIA_SOURCES="$src/Projects/Sources"
cmake --build "$build/cmake" -j"$(nproc)"

"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=hidden -c "$HERE/clock.c" -o "$build/clock.o"
"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -shared -nodefaultlibs -O2 \
  -Wl,--allow-undefined -o "$OUT/dist/libExternalMediaLib.wasm" \
  -Wl,--whole-archive "$build/cmake/libExternalMediaLib.a" -Wl,--no-whole-archive "$build/clock.o" \
  "$SYSLIB_libcxx/lib/libc++.so" "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"
cp "$src/Projects/Sources/externalmedialib.h" "$OUT/include/"
