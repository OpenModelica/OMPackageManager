# OpenModelica Package Manager

OpenModelica comes with an integrated Modelica package manager to handle the installation and updates of publicly
available open-source libraries, which are hosted on GIT repositories. The rationale and use of the package mananager is discussed in the
[User's Guide](https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/packagemanager.html). The package manager
is available both via API calls in the interactive environment, and via the OMEdit GUI using the _File | Manage Libraries_ menu.

## Configuration of the Package Manager server

The database of managed libraries is kept in the [repos.json](repos.json) file, which is edited manually. If you want to add
your own open-source library to the OpenModelica package manager, please fork the OMPackageManager repository, add you library
to the [repos.json](repos.json) database and open a pull request, or request us to do it for you by opening a request on the
[OpenModelica issue tracker](https://github.com/OpenModelica/OpenModelica/issues/new/choose).

Starting from this information, the `updateinfo.py` script queries the repositories where the libraries are stored and
generates an up-to-date [rawdata.json](rawdata.json) file. This script is run on OSMC's servers multiple times a day to keep it up to date
with library developments. Note that the query includes advanced Modelica-specific features, e.g. determining dependencies
via the `uses` annotations, and determining backwards compatibility among versions via the `conversion` annotations.
The `genindex.py` script is then run to generate the `index.json` database, which is queried by OMC clients to
update the local package database.

The package manager preferably refers to official library releases, which are fetched automatically from the GitHub
server without the need of naming them explicitly in the [repos.json](repos.json)
file; whenever a new version of a library is released, the [repos.json](repos.json)
is automatically updated to make it available. However, it is also possible to manage versions of the library that are located on specific named
branches, e.g. master or maintenance branches. This is useful if you want to track development versions or you want to get the latest fixes
before the official release.

For each library, the [repos.json](repos.json) database contains several pieces of information:
- the name of the library(es) (`names` field); it is possible to collect a set of libraries that are found in the same GIT repository
  e.g. Modelica, ModelicaReference, ModelicaServices, Complex, ModelicaTest
- the location of the GIT repository on GitHub (`github` field), or the git URL in case other servers are used (`git` field)
- optional branches to be managed besides the official releases (`branches` field)
- optional tags to be ignored, if one wants to avoid them to be considered by the package manager (`ignore-tags` field)
- the level of support in OpenModelica of the various versions of the library.

## Library support levels in OpenModelica
There are five levels of support:
- `fullSupport`: The library is fully supported by OpenModelica, with over 95% runnable models in the library simulating correctly
- `support`: The library is partially supported by OpenModelica; most models and features work correctly, but some still don't
- `experimental`: The library is currently being tested with OpenModelica, but there is no guarantee of success when using it
- `noSupport`: The library is actively developed or maintained, but is not supported by OpenModelica
- `obsolete`: The library is no longer developed or maintained, or it has been completely superseded by more recent versions

Note that a library may not be fully supported because of OpenModelica limitations or bugs, but also because the library
is not fully compliant to the Modelica Language standard. In both cases, we are open to cooperation with open-source
Modelica library developers, to fix the OpenModelica issues on one hand, and to help them fix it so it is fully
compliant to the standard on the other hand. Please open an issue on the
[OpenModelica issue tracker](https://github.com/OpenModelica/OpenModelica/issues) if you want to start the process on your
open-source Modelica library.

The support field may contain multiple selection criteria that are applied sequentially. For example:
```json
"support": [
      ["prerelease", "noSupport"],
      [">=7.0.0", "fullSupport"],
      [">=5.1.0", "support"],
      ["*", "obsolete"]
    ]
```
means that all pre-release version are not supported, all _remaining_ versions with version number greater or equal to
7.0.0 are fully supported, all _remaining_ versions with version number greater or equal to 5.1.0 are partially supported,
and all _remaining_ versions are considered obsolete.

When the first string starts with `>=`, all versions with equal or higher release number according to semver get the attribute of the second string. The string
`prerelease` identifies all pre-release version, that have a semver metadata starting with `-`. It is also possible to start the first string with `+`, as in `+default.modelica.association` that matches `v3.2.1+default.modelica.association` and `v3.2.2+default.modelica.association`. The wildcard `*` matches any
version. In all other cases the first string must match verbatim the version number.

Some libraries in the package manager are regularly tested on the OSMC servers, see the OpenModelica Library Testing [README.md](https://github.com/OpenModelica/OpenModelicaLibraryTesting/blob/master/README.md).
