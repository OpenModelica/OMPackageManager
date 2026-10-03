# OpenModelica Package Manager

OpenModelica comes with an integrated Modelica package manager to handle the
installation and updates of publicly available open-source libraries, which are
hosted on GIT repositories. The rationale and use of the package mananager is
discussed in the
[User's Guide](https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/packagemanager.html).
The package manager is available both via API calls in the interactive
environment, and via the OMEdit GUI using the _File | Manage Libraries_ menu.

## Adding a new library

If you want to add your own open-source library to the OpenModelica package
manager, please fork the OMPackageManager repository, add your library to the
[repos.json](repos.json) database, and open a pull request.

For each library, the [repos.json](repos.json) database contains several pieces
of information:

- The name of the library(es) (`names` field); it is possible to collect a set
  of libraries that are found in the same GIT repository e.g. Modelica,
  ModelicaReference, ModelicaServices, Complex, ModelicaTest.
- The location of the GIT repository on GitHub (`github` field), or the git URL
  in case other servers are used (`git` field).
- Optional locations within the git repository (`search-extra-paths` field) to
  search for libraries. This can be specified if the libraries are not located
  at the root of repository.
- Optional branches to be managed besides the official releases (`branches`
  field).
- Optional tags to be ignored, if one wants to avoid them to be considered by
  the package manager (`ignore-tags` field).
- Optionally use the zip-files attached to the GitHub releases instead of the
  source tree of the git tag (`github-releases` field), see below.
- Optional fixups for releases whose own version metadata is wrong
  (`semverTagOverridesAnnotation` and `extra-provides` fields), see below.
- The level of support in OpenModelica of the various versions of the library
  (`support` field), see below.

As an example, if you develop your library `MyLibrary` at
"<https://github.com/myGithubName/MyLibrary.git>", you can add a json object
like the following to [repos.json](repos.json)

```json
  "MyLibrary": {
    "names": ["MyLibrary"],
    "github": "myGithubName/MyLibrary",
    "support": [
      ["*", "noSupport"]
    ]
  },

```

### Using the zip-files from GitHub releases

By default a version is taken from the git tag it was released from, which
means it only contains what is checked into the repository. If the release
zip-file on GitHub contains more than that, e.g. pre-compiled binaries in
`Resources/Library`, add `"github-releases": true` to use it instead:

```json
  "MyLibrary": {
    "names": ["MyLibrary"],
    "github": "myGithubName/MyLibrary",
    "github-releases": true,
    "support": [
      ["*", "noSupport"]
    ]
  },
```

The releases are read from the GitHub API, so new releases are picked up
without editing [repos.json](repos.json). A tag whose release has no zip-file
attached keeps being taken from git, so old releases predating the practice
still work.

The asset to use is the one matching the glob pattern `*.zip`. If a release
has several of those, `updateinfo` fails and the pattern has to be narrowed by
giving it instead of `true`, e.g. `"github-releases": "MyLibrary-*.zip"`.

Libraries that are not on GitHub, or that are released somewhere else entirely,
can list the zip-files explicitly in a `zipfiles` field instead; those versions
are then not tied to a git tag.

### Working around wrong version metadata in a release

A released version is named by the `version` of its `package.mo` annotation, and
a `uses(MyLibrary(version="1.0.0"))` annotation resolves to that exact version,
or to one whose `conversion(noneFromVersion="1.0.0")` annotation declares it a
drop-in replacement. Neither can be corrected after the fact by the library
developers, so the package manager can override both.

If the version annotation was not bumped before tagging, the tag is the more
trustworthy of the two. Add `"semverTagOverridesAnnotation": true` to take the
version from the tag whenever it is the newer one, or
`"semverTagOverridesAnnotation": "alsoNewerVersions"` to always take it:

```json
  "MyLibrary": {
    "names": ["MyLibrary"],
    "github": "myGithubName/MyLibrary",
    "semverTagOverridesAnnotation": true,
    "support": [
      ["*", "noSupport"]
    ]
  },
```

If a release is a drop-in replacement for older versions but has no conversion
annotation saying so, `extra-provides` maps a version to the versions it
additionally provides. Nothing else can load those older versions then, so this
is also how a version that was never released on its own stays loadable:

```json
  "MyLibrary": {
    "names": ["MyLibrary"],
    "github": "myGithubName/MyLibrary",
    "extra-provides": {
      "1.2.0": ["1.0.0", "1.1.0"]
    },
    "support": [
      ["*", "noSupport"]
    ]
  },
```

These are merged with the versions from the conversion annotation, so an entry
can be dropped again once a later release declares it upstream. `genindex`
prints a line for every version listed here that no release has.

### Prebuilt wasm modules for external "C" code

The wasm-jit target of omc links external "C" code as WebAssembly modules, and
an omc without a C compiler (the one in a browser) has no other way to run it.
`build-wasm` prebuilds them for every version of every library in the index:
omc's `getExternalFunctions` describes a library's external functions, and the
package manager compiles their `Include` sources, with call wrappers from their
C signatures, plus what a `wasm` entry adds:

```json
  "MyLibrary": {
    "names": ["MyLibrary"],
    "github": "myGithubName/MyLibrary",
    "wasm": {
      "include": ["wasm/MyLibrary/prototypes.h"],
      "systemLibraries": ["ModelicaSDF"],
      "configure": {
        "Resources/src/config.h": {"from": "Resources/src/config.h.in", "values": {"VERSION": "1.0"}}
      },
      "common": {"includes": ["Resources/Include"], "defines": ["NDEBUG"]},
      "libraries": {
        "MyLibraryExternals": {
          "sources": ["Resources/src/*.c"],
          "exclude": ["Resources/src/win32.c"],
          "hidden": ["Resources/src/thirdparty/*.c"],
          "include": ["wasm/MyLibrary/wasi.h"],
          "systemLibraries": ["hdf5", "zlib"]
        }
      }
    },
    "support": [
      ["*", "noSupport"]
    ]
  },
```

`include` lists headers forced into the `Include` sources, for sources that do
not compile on their own (a function called without a prototype does not link
in wasm). `libraries` are recipes for the names of `Library` annotations, with
paths relative to the library (`sources` may be glob patterns). With
`latestRelease`, for a library whose C code stays backwards compatible such as
the MSL, every release gets the modules of the newest one; a version
without the sources, or one that ships `Resources/Library/wasm32-wasip1/<name>.wasm`
itself, skips the recipe. `common` is added to every recipe. A recipe's
`include` forces headers into its sources; `hidden` sources are linked in
without exporting their symbols (a private copy of code another module may also
define). `configure` writes files the way CMake's
`configure_file` does, from a file of the library. `systemLibraries` names
entries of [wasm-system-libraries.json](wasm-system-libraries.json), built once
by their script and shared by every library and version that needs them; at
the top level they provide `Library` names and headers that the library itself
does not. One with `archives` and no `module` ships nothing: the archives,
built with hidden symbols, are linked into each library using it. HDF5 is one,
so the HDF5 versions of two libraries in one simulation never clash. A system
library may use others (`systemLibraries` in its entry), whose output
directories its script gets as `SYSLIB_<name>`. C++ sources compile against
`libcxx` (libc++ with WebAssembly exceptions): its `cxxIncludes` are their
headers, and linking its `links` puts `libc++.so` in the module's NEEDED.

The modules of a version are zipped as
`omc-<generation>/<Library>-wasm32-wasip1-<hash>.zip`, the hash of everything
they were built from, so versions whose C code did not change share one
zip-file. A library without external "C" code gets none.

Everything is built against the package manager's own libc (the `libc` system
library, shipped with every bundle, as one libc is loaded per simulation) and
for a fixed set of wasm features that wasmtime, wasmer and V8 all run
(`WASM_FEATURES` in `buildwasm.py`). Together with the toolchain these make a
*generation* (`GENERATION`): omc installs a version's bundle under
`Resources/Library/wasm32-wasip1/omc-<generation>`, keeps older generations, and
runs a model with the newest generation all its libraries have. A new libc or
toolchain means a new generation and every bundle rebuilt at once; omc needs no
change for it. The index's `wasm` entries are keyed by the interface omc's
loader expects (manifest and wrappers), which changes only with omc itself.

The libc's sysroot is published too, as the index's `wasmToolchain`. omc's
`installWasmToolchain()` installs it under
`~/.openmodelica/wasm32-wasip1/omc-<generation>/sysroot`, and the wasm-jit target
compiles a model's own `Include` sources against it with the system clang. Its
`cxx` part adds libc++'s headers and `libc++.so` for C++ code
(`installWasmToolchain(cxx=true)`).

## Library support levels in OpenModelica

There are five levels of support:

- `fullSupport`: The library is fully supported by OpenModelica, with over 95%
  runnable models in the library simulating correctly.
- `support`: The library is partially supported by OpenModelica; most models and
  features work correctly, but some still don't.
- `experimental`: The library is currently being tested with OpenModelica, but
  there is no guarantee of success when using it.
- `noSupport`: The library is actively developed or maintained, but is not
  supported by OpenModelica.
- `obsolete`: The library is no longer developed or maintained, or it has been
  completely superseded by more recent versions.

Note that a library may not be fully supported because of OpenModelica
limitations or bugs, but also because the library is not fully compliant to the
Modelica Language standard. In both cases, we are open to cooperation with
open-source Modelica library developers, to fix the OpenModelica issues on one
hand, and to help them fix it so it is fully compliant to the standard on the
other hand. Please open an issue on the [OpenModelica issue
tracker](https://github.com/OpenModelica/OpenModelica/issues) if you want to
start the process on your open-source Modelica library.

The support field may contain multiple selection criteria that are applied
sequentially. For example:

```json
"support": [
      ["prerelease", "noSupport"],
      [">=7.0.0", "fullSupport"],
      [">=5.1.0", "support"],
      ["*", "obsolete"]
    ]
```

means that all pre-release versions are not supported, all _remaining_ versions
with version number greater or equal to 7.0.0 are fully supported, all
_remaining_ versions with version number greater or equal to 5.1.0 are partially
supported, and all _remaining_ versions are considered obsolete.

When the first string starts with `>=`, all versions with equal or higher
release number according to semver get the attribute of the second string. The
string `prerelease` identifies all pre-release version, that have a semver
metadata starting with `-`. It is also possible to start the first string with
`+`, as in `+default.modelica.association` that matches
`v3.2.1+default.modelica.association` and `v3.2.2+default.modelica.association`.
The wildcard `*` matches any version. In all other cases the first string must
match verbatim the version number.

Some libraries in the package manager are regularly tested on the OSMC servers,
see the OpenModelica Library Testing
[README.md](https://github.com/OpenModelica/OpenModelicaLibraryTesting/blob/master/README.md).

## Configuration of the Package Manager server

The database of managed libraries is kept in the [repos.json](repos.json) file,
which is edited manually. Starting from this information, the `updateinfo`
script queries the repositories where the libraries are stored and generates an
up-to-date [rawdata.json](rawdata.json) file.

```bash
python -m ompackagemanager updateinfo
```

This script is run by the
[Update Package Index job](https://test.openmodelica.org/jenkins/job/Update%20Package%20Index/)
on OSMC's Jenkins server four times a day to keep it up to date with library
developments. Note that the query includes advanced Modelica-specific features,
e.g. determining dependencies via the `uses` annotations, and determining
backwards compatibility among versions via the `conversion` annotations. The
`genindex` script is then run to generate the `index.json` database, which is
queried by OMC clients to update the local package database.

```bash
python -m ompackagemanager genindex
```

The package manager preferably refers to official library releases, which are
fetched automatically from the GitHub server without the need of naming them
explicitly in the [repos.json](repos.json) file; whenever a new version of a
library is released, the [repos.json](repos.json) is automatically updated to
make it available. However, it is also possible to manage versions of the
library that are located on specific named branches, e.g. master or maintenance
branches. This is useful if you want to track development versions or you want
to get the latest fixes before the official release.

The prebuilt wasm modules are built between the two, with an omc whose
`getExternalFunctions` describes what to build, and `genindex` is run again to
add them to the index:

```bash
python -m ompackagemanager build-wasm --omc /path/to/omc --output www-data/precompiled/wasm32-wasip1
python -m ompackagemanager genindex
```

`wasmdata.json` records what was built, so a version is only built again when
its source, its recipe or omc's wasm ABI changed. Building the system libraries
needs clang, wasm-ld and llvm-ar, CMake, and the Python version of CPython's
cross-build.

## Generate Package Index

Install dependencies:

- Python 3
- OpenModelica

```bash
pip install -r requirements.txt
```

Create a public_repo personal access token for GitHub and define an environment
variable `GITHUB_AUTH`:

```bash
export GITHUB_AUTH=<your PAT>
```

Generate index file `index.json`.

```bash
rm -rf cache/
rm -f index.json
python -m ompackagemanager updateinfo
python -m ompackagemanager genindex
```

To test the index file copy it into your OpenModelica libraries directory and
test it via OMEdit / scripting API:

```bash
cp index.json ~/.openmodelica/libraries/index.json
```

## Development

All Python code is formatted with
[autopep8](https://pypi.org/project/autopep8/):

```bash
autopep8 ompackagemanager/ tests/
```

Unit tests can be run with:

```bash
python -m unittest discover -s tests
```
