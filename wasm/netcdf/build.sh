#!/bin/sh
# netCDF-C for wasm32-wasip1 as a PIC dylink module: the classic formats, without
# netCDF-4/HDF5, DAP, NCZarr or plugins. SYSLIB_zlib is the zlib system library,
# linked in.
#
# Usage: build.sh OUT
#   OUT/dist     what ships: the module
#   OUT/include  the headers the code using it is compiled against
#
# OMC_WASI_SYSROOT and OMC_WASI_CLANG name the toolchain.
set -e

VERSION=4.9.3
OUT=$(realpath "$1")
SYSROOT=${OMC_WASI_SYSROOT:?}
CLANG=${OMC_WASI_CLANG:-clang}
CPU=${OMC_WASM_FEATURES:--mcpu=generic -msimd128 -mextended-const}
AR=${AR:-$(command -v llvm-ar || ls /usr/bin/llvm-ar-* | sort -V | tail -1)}

src=$OUT/src
build=$OUT/build
mkdir -p "$src" "$build" "$OUT/dist" "$OUT/include"
if [ ! -f "$src/CMakeLists.txt" ]; then
  curl -sSfL "https://github.com/Unidata/netcdf-c/archive/refs/tags/v$VERSION.tar.gz" | tar xz -C "$src" --strip-components=1
fi

# CMake links its probes as executables, and clang looks for the builtins under
# its resource directory, where Debian does not put the wasm32 ones.
res=$build/clang-resource
mkdir -p "$res/lib/wasm32-unknown-wasip1"
ln -sfn "$("$CLANG" -print-resource-dir)/include" "$res/include"
ln -sf "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a" "$res/lib/wasm32-unknown-wasip1/libclang_rt.builtins.a"

cat > "$build/toolchain.cmake" <<TOOLCHAIN
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER $CLANG)
set(CMAKE_C_COMPILER_TARGET wasm32-wasip1)
set(CMAKE_AR $AR)
set(CMAKE_SYSROOT $SYSROOT)
set(CMAKE_C_FLAGS_INIT "$CPU -fPIC -resource-dir=$res -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_GETPID -D_WASI_EMULATED_PROCESS_CLOCKS -D_S_IREAD=S_IRUSR -D_S_IWRITE=S_IWUSR")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
TOOLCHAIN

cmake -S "$src" -B "$build" -DCMAKE_TOOLCHAIN_FILE="$build/toolchain.cmake" -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DNETCDF_ENABLE_NETCDF4=OFF -DNETCDF_ENABLE_HDF5=OFF -DNETCDF_ENABLE_DAP=OFF \
  -DNETCDF_ENABLE_BYTERANGE=OFF -DNETCDF_ENABLE_NCZARR=OFF -DNETCDF_ENABLE_PLUGINS=OFF \
  -DNETCDF_ENABLE_FILTER_TESTING=OFF -DNETCDF_ENABLE_TESTS=OFF -DNETCDF_BUILD_UTILITIES=OFF \
  -DNETCDF_ENABLE_EXAMPLES=OFF -DNETCDF_ENABLE_MMAP=OFF -DNETCDF_ENABLE_LIBXML2=OFF -DNETCDF_ENABLE_S3=OFF \
  -DNETCDF_ENABLE_LOGGING=OFF -DNETCDF_ENABLE_DOXYGEN=OFF -DNETCDF_ENABLE_PARALLEL4=OFF \
  -DZLIB_LIBRARY="$SYSLIB_zlib/lib/libz.a" -DZLIB_INCLUDE_DIR="$SYSLIB_zlib/include"
cmake --build "$build" --target netcdf -j"$(nproc)"

"$CLANG" --target=wasm32-wasip1 $CPU --sysroot="$SYSROOT" -fPIC -shared -nodefaultlibs \
  -Wl,--export-all -Wl,--allow-undefined -o "$OUT/dist/libnetcdf.wasm" \
  -Wl,--whole-archive "$build/libnetcdf.a" -Wl,--no-whole-archive \
  "$SYSLIB_zlib/lib/libz.a" "$SYSROOT/lib/wasm32-wasip1/libclang_rt.builtins-wasm32.a"

cp "$src/include/netcdf.h" "$build/include/netcdf_meta.h" "$OUT/include/"
