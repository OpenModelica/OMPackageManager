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

VERSION=4.1.1
# What ExternalMedia's CMake project downloads itself.
COOLPROP_VERSION=6.7.0
OUT=$(realpath "$1")
HERE=$(dirname "$(realpath "$0")")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CLANGXX=${OMC_WASI_CLANGXX:-$(dirname "$(command -v "$CLANG")")/$(basename "$CLANG" | sed 's/clang/clang++/')}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
EH="-fwasm-exceptions -mllvm -wasm-use-legacy-eh=false"
CXXINC="-nostdinc++ -isystem $SYSLIB_libcxx/include/c++/v1"

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist" "$OUT/include"
if [ ! -f "$src/Projects/CMakeLists.txt" ]; then
  curl -sSfL "https://github.com/modelica-3rdparty/ExternalMedia/archive/refs/tags/v$VERSION.tar.gz" |
    tar xz -C "$src" --strip-components=1
fi
if [ ! -d "$build/CoolProp.sources" ]; then
  curl -sSfL -o "$build/coolprop.zip" \
    "https://sourceforge.net/projects/coolprop/files/CoolProp/$COOLPROP_VERSION/source/CoolProp_sources.zip/download"
  (cd "$build" && unzip -q coolprop.zip && mv source CoolProp.sources && rm coolprop.zip)
fi
# Compiled directly: both CMake projects assume a native platform. The sources
# are what they select, the CoolProp headers they generate ship in the zip.
# CoolProp takes WASI for POSIX with __posix (REFPROP's dlopen then fails).
cp=$build/CoolProp.sources
sources="$(ls "$src"/Projects/Sources/*.cpp | grep -v -e FluidProp_ -e fluidpropsolver -e mingw_gcc_comutil)
$(ls "$cp"/src/*.cpp | grep -v -e /CoolPropLib.cpp)
$(find "$cp/src/Backends" -name '*.cpp' | grep -e /Cubics/ -e /IF97/ -e /Helmholtz/ -e /REFPROP/ -e /Incompressible/ -e /Tabular/ -e /PCSAFT/)"
inc="-I$cp -I$cp/include -I$cp/src -I$cp/externals/Eigen -I$cp/externals/msgpack-c/include -I$cp/boost_CoolProp \
  -I$cp/externals/fmtlib/include -I$cp/externals/fmtlib -I$src/Projects/Sources -I$HERE/include"
mkdir -p "$build/obj"
export CLANGXX CPU EH CXXINC SYSROOT inc build HERE
echo "$sources" | xargs -P "$(nproc)" -I{} sh -c '
  o=$build/obj/$(echo "{}" | md5sum | cut -c1-16).o
  # shellcheck disable=SC2086
  "$CLANGXX" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=default $EH $CXXINC \
    -DEXTERNALMEDIA_COOLPROP=1 -DEXTERNALMEDIA_FLUIDPROP=0 -DMSGPACK_NO_BOOST -D__posix $inc -c "{}" -o "$o"'

"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -O2 -fPIC -fvisibility=hidden -c "$HERE/clock.c" -o "$build/clock.o"
"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -shared -nodefaultlibs -O2 \
  -Wl,--allow-undefined -o "$OUT/dist/libExternalMediaLib.wasm" "$build"/obj/*.o "$build/clock.o" \
  "$SYSLIB_libcxx/lib/libc++.so" "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"
cp "$src/Projects/Sources/externalmedialib.h" "$OUT/include/"
