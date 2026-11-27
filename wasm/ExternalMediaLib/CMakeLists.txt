# ExternalMediaLib's sources and CoolProp's objects in one archive, which
# build.sh links into the module. ExternalMedia's own project only knows
# native platforms.
cmake_minimum_required(VERSION 3.15)
project(ExternalMediaLib C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(COOLPROP_OBJECT_LIBRARY ON CACHE BOOL "" FORCE)
set(COOLPROP_FPIC ON CACHE BOOL "" FORCE)
set(FORCE_BITNESS_NATIVE ON CACHE BOOL "" FORCE)
set(COOLPROP_NO_EXAMPLES ON CACHE BOOL "" FORCE)
add_subdirectory("${COOLPROP_SOURCES}" CoolProp)
get_directory_property(COOLPROP_INCLUDE_DIRS DIRECTORY "${COOLPROP_SOURCES}" INCLUDE_DIRECTORIES)

file(GLOB sources "${EXTERNALMEDIA_SOURCES}/*.cpp")
list(FILTER sources EXCLUDE REGEX "/(FluidProp_[^/]*|fluidpropsolver|mingw_gcc_comutil)\\.cpp$")
add_library(ExternalMediaLib STATIC ${sources} $<TARGET_OBJECTS:CoolProp>)
target_include_directories(ExternalMediaLib PRIVATE ${COOLPROP_INCLUDE_DIRS} "${EXTERNALMEDIA_SOURCES}")
# Only the API is exported: the loader routes every call to an exported symbol,
# even from inside the module, through a host trampoline.
target_compile_definitions(ExternalMediaLib PRIVATE EXTERNALMEDIA_COOLPROP=1 EXTERNALMEDIA_FLUIDPROP=0
  "EXTERNALMEDIA_EXPORT=__attribute__((visibility(\"default\")))")
