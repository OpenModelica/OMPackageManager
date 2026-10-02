"""Build the prebuilt wasm external "C" modules of the indexed libraries.

An omc without a C compiler (the one running in a browser) cannot compile the
sources the `Include` annotations of a library name. For every version of every
library in the index this builds:

- the `Include` sources, with omc's `buildWasmExternals`;
- the `Library` annotations the `wasm` entry of its repos.json entry has a
  recipe for;
- the system libraries those need, once each, from wasm-system-libraries.json.

Each bundle is a zip named `<Library>-wasm32-wasip1-<hash>.zip`, the hash of
everything it was built from, so versions whose C code did not change share one
file. A library without external "C" code gets no zip. The results are recorded
in wasmdata.json, which `genindex` adds to the index.
"""

import glob
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile

from .common import VersionNumber

MANIFEST = "omc-externals.json"
TARGET = "wasm32-wasip1"
# Everything built with one toolchain and libc. Bumped when either changes; omc
# installs generations side by side and never mixes them in one simulation.
GENERATION = 1
# The wasm features wasmtime, wasmer and V8 all run today, spelled out rather than
# clang's moving default; features are not dropped, so the set only grows.
WASM_FEATURES = ["-mcpu=mvp", "-mmutable-globals", "-msign-ext", "-mnontrapping-fptoint", "-mbulk-memory",
                 "-mbulk-memory-opt", "-mmultivalue", "-mreference-types", "-mcall-indirect-overlong",
                 "-msimd128", "-mextended-const"]
# The system library every module is built against and ships with: one libc is
# loaded per simulation.
LIBC = "libc"
# The C++ runtime C++ sources are compiled against, with exnref exceptions.
LIBCXX = "libcxx"
CXX_SOURCES = (".cpp", ".cc", ".cxx")
EH_FLAGS = ["-fwasm-exceptions", "-mllvm", "-wasm-use-legacy-eh=false"]
# What omc's own `Include` translation units start with: the spec's size_t.
INCLUDE_PREAMBLE = "#include <stddef.h> /* the spec's array-dimension type */\n"
OMC_TIMEOUT = 3600
DEFAULT_URL = "https://libraries.openmodelica.org/precompiled/wasm32-wasip1/"


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def write_zip(src: str, dest: str) -> None:
    """Zip the tree `src` reproducibly: sorted entries and fixed timestamps."""
    tmp = dest + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(root, name)
                info = zipfile.ZipInfo(os.path.relpath(path, src).replace(os.sep, "/"), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(path, "rb") as f:
                    z.writestr(info, f.read())
    os.replace(tmp, dest)


def make_words(rule: str) -> list[str]:
    """The words of a make rule, where `\\ ` is a space in a file name and a
    backslash before a newline continues the line."""
    words, word, i = [], "", 0
    while i < len(rule):
        c = rule[i]
        nxt = rule[i + 1] if i + 1 < len(rule) else ""
        if c == "\\" and nxt in (" ", "#"):
            word += nxt
            i += 1
        elif c == "$" and nxt == "$":
            word += "$"
            i += 1
        elif c == "\\" and nxt == "\n" or c.isspace():
            if word:
                words.append(word)
            word = ""
            i += 1 if c == "\\" else 0
        else:
            word += c
        i += 1
    if word:
        words.append(word)
    return words


class Toolchain:
    """The compiler, and the sysroot of the libc system library once it is built."""

    def __init__(self, omhome: str):
        self.omhome = omhome
        self.clang = os.environ.get("OMC_WASI_CLANG", "clang")
        self.clangxx = os.environ.get("OMC_WASI_CLANGXX", os.path.join(
            os.path.dirname(self.clang), os.path.basename(self.clang).replace("clang", "clang++", 1)))
        self.sysroot = ""
        self.includes = [os.path.join(omhome, "include", "omc", "c")]
        self.builtins = []

    def flags(self, includes: list[str], defines: list[str], forced: list[str] = [],
              isystem: list[str] = []) -> list[str]:
        return (["--target=wasm32-wasip1"] + WASM_FEATURES + ["--sysroot=" + self.sysroot] +
                ["-I" + d for d in self.includes + includes] + ["-D" + d for d in defines] +
                [a for h in forced for a in ("-include", os.path.realpath(h))] +
                [a for d in isystem for a in ("-isystem", d)])

    def compiler(self, src: str, cxx_includes: list[str]) -> list[str]:
        if not src.endswith(CXX_SOURCES):
            return [self.clang]
        return [self.clangxx, "-nostdinc++"] + [a for d in cxx_includes for a in ("-isystem", d)] + EH_FLAGS

    def deps(self, sources: list[str], includes: list[str], defines: list[str], forced: list[str] = [],
             isystem: list[str] = [], cxx_includes: list[str] = []) -> list[str]:
        words = []
        for src in sources:
            out = subprocess.run(
                self.compiler(
                    src,
                    cxx_includes) +
                ["-M"] +
                self.flags(
                    includes,
                    defines,
                    forced,
                    isystem) +
                [src],
                check=True,
                capture_output=True,
                text=True).stdout
            words += make_words(out)[1:]
        return sorted({os.path.realpath(w) for w in words if os.path.exists(w)})

    def use_sysroot(self, sysroot: str) -> None:
        """Build against the libc system library."""
        self.sysroot = sysroot
        builtins = os.path.join(sysroot, "lib", "wasm32-wasip1", "libclang_rt.builtins-wasm32.a")
        self.builtins = [builtins] if os.path.exists(builtins) else []

    def shared_library(self, sources: list[str], includes: list[str], defines: list[str], output: str,
                       links: list[str] = [], forced: list[str] = [], hidden: list[str] = [],
                       isystem: list[str] = [], optimize: str = "-O2", cxx_includes: list[str] = []) -> None:
        """Exports what `sources` define. `hidden` sources and the archives in
        `links` stay private to the module, as HDF5 is in a native build that
        links it statically, so another copy loaded beside it does not clash.
        Linking against a module omc ships puts it in NEEDED, so it is loaded
        beside this one. C++ sources are compiled against `cxx_includes`."""
        flags = [optimize, "-fPIC"] + self.flags(includes, defines, forced, isystem)
        with tempfile.TemporaryDirectory(prefix="om-wasm-hidden-") as tmp:
            objects = []
            own = []
            for i, src in enumerate(sources + [h for h in hidden if h not in sources]):
                if src not in hidden and not src.endswith(CXX_SOURCES):
                    own.append(src)
                    continue
                obj = os.path.join(tmp, "%d.o" % i)
                visibility = "-fvisibility=hidden" if src in hidden else "-fvisibility=default"
                subprocess.run(self.compiler(src, cxx_includes) + [visibility, "-c", src, "-o", obj] + flags,
                               check=True, capture_output=True, text=True)
                objects.append(obj)
            cmd = ([self.clang, "-fvisibility=default", "-shared", "-nodefaultlibs", "-Wl,--allow-undefined"] +
                   flags + ["-o", output] + own + objects + links + self.builtins)
            subprocess.run(cmd, check=True, capture_output=True, text=True)


def recipe_sources(root: str, lib: dict) -> list[str] | None:
    """The sources of a `libraries` recipe, with glob patterns expanded; None if
    any is missing from this version."""
    out = []
    for pattern in lib["sources"]:
        if glob.has_magic(pattern):
            found = sorted(glob.glob(os.path.join(glob.escape(root), pattern)))
            if not found:
                return None
            out += found
        elif os.path.exists(os.path.join(root, pattern)):
            out.append(os.path.join(root, pattern))
        else:
            return None
    excluded = {f for pattern in lib.get("exclude", []) for f in glob.glob(os.path.join(glob.escape(root), pattern))}
    return [f for f in out if f not in excluded]


def leb128(data: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7f) << shift
        shift += 7
        if b < 0x80:
            return result, pos


def wasm_exports(path: str) -> set[str]:
    """The export names of a wasm module."""
    with open(path, "rb") as f:
        data = f.read()
    names, pos = set(), 8
    while pos < len(data):
        section = data[pos]
        size, pos = leb128(data, pos + 1)
        end = pos + size
        if section == 7:
            count, p = leb128(data, pos)
            for _ in range(count):
                length, p = leb128(data, p)
                names.add(data[p:p + length].decode())
                _, p = leb128(data, p + length + 1)
        pos = end
    return names


def ext_wrappers(functions: list[dict]) -> str:
    """omc's call and address wrappers for external functions, from their C
    signatures: a static or inline function, or a macro, becomes callable."""
    out = []
    for f in functions:
        name, ret, params = f["name"], f.get("returns"), f.get("parameters")
        addr = "void (*omc_ext_addr_%s(void))(void) { return (void (*)(void)) %s; }\n" % (name, name)
        if ret is None or params is None:
            out.append(addr)
            continue
        if f.get("declare"):
            out.append("extern %s %s(%s);\n" % (ret, name, ", ".join(params) or "void"))
        typed = ", ".join("%s a%d" % (t, i) for i, t in enumerate(params))
        call = "%s%s(%s);" % ("" if ret == "void" else "return ", name,
                              ", ".join("a%d" % i for i in range(len(params))))
        out.append("%s omc_ext_call_%s(%s) { %s }\n#ifndef %s\n%s#endif\n" %
                   (ret, name, typed or "void", call, name, addr))
    return "".join(out)


def group_units(units: list[dict]) -> list[list[int]]:
    """Units that read a common file under their include directories, or spell the
    same sources, share a module, so their static variables stay shared as in the
    single translation unit the C target compiles."""
    parent = list(range(len(units)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner: dict[str, int] = {}
    for i, u in enumerate(units):
        roots = [os.path.realpath(d) + os.sep for d in u["includeDirectories"] if os.path.isdir(d)]
        keys = [d for d in u["deps"] if any(d.startswith(r) for r in roots)] + ["\0" + "\n".join(u["includes"])]
        for k in keys:
            if k in owner:
                a, b = find(i), find(owner[k])
                parent[max(a, b)] = min(a, b)
            else:
                owner[k] = i
    groups: dict[int, list[int]] = {}
    for i in range(len(units)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def build_include_modules(functions: list[dict], toolchain: "Toolchain", forced: list[str], isystem: list[str],
                          bundle: str, work: str) -> tuple[dict, dict, list[str]]:
    """Compile the `Include` sources of the described external functions to modules
    in `bundle`. Returns the manifest's functions and failures, and what the
    modules were built from."""
    units, failed = [], {}
    for f in functions:
        if not f["includes"]:
            continue
        if "unsupported" in f:
            failed[f["path"]] = f["unsupported"]
            continue
        tu = os.path.join(work, "deps.c")
        with open(tu, "w") as out:
            out.write(INCLUDE_PREAMBLE + "\n".join(f["includes"]) + "\n")
        try:
            deps = toolchain.deps([tu], f["includeDirectories"], [], forced, isystem)
        except subprocess.CalledProcessError as e:
            failed[f["path"]] = "the Include sources do not preprocess for wasm: " + (e.stderr or "").strip()
            continue
        units.append(dict(f, deps=[d for d in deps if d != os.path.realpath(tu)]))
    units.sort(key=lambda u: u["path"])
    os.makedirs(os.path.join(bundle, "omc-include"), exist_ok=True)
    entries, inputs = {}, []

    def compile_group(members: list[int]) -> bool:
        includes, dirs, sigs = [], [], {}
        for i in members:
            u = units[i]
            includes += [s for s in u["includes"] if s not in includes]
            dirs += [d for d in u["includeDirectories"] if d not in dirs]
            sigs.setdefault(u["name"], u)
        text = INCLUDE_PREAMBLE + "\n".join(includes) + "\n" + ext_wrappers(list(sigs.values()))
        tu = os.path.join(work, "group.c")
        with open(tu, "w") as out:
            out.write(text)
        module = os.path.join(work, "group.wasm")
        try:
            toolchain.shared_library([tu], dirs, [], module, forced=forced, isystem=isystem, optimize="-O1")
        except subprocess.CalledProcessError as e:
            for i in members:
                failed[units[i]["path"]] = "the Include sources did not compile for wasm: " + (e.stderr or "").strip()
            return False
        exports = wasm_exports(module)
        # An `Include` that only declares the function leaves it to a `Library`.
        defined = [i for i in members if units[i]["name"] in exports or
                   (any("usertab" in s for s in units[i]["includes"]) and "usertab" in exports)]
        for i in members:
            failed.pop(units[i]["path"], None)
        if not defined:
            return True
        name = "omc-include/%s.wasm" % sha256_file(module)[:16]
        shutil.copy(module, os.path.join(bundle, name))
        roots = [os.path.realpath(d) for d in dirs if os.path.isdir(d)]
        for i in defined:
            u = units[i]
            entries[u["path"]] = {"module": name, "name": u["name"], "includes": "\n".join(u["includes"])}
            inputs.extend("file %s %s" % (file_key(d, roots), sha256_file(d)) for d in u["deps"]
                          if not d.startswith(os.path.realpath(toolchain.sysroot)))
        inputs.append("tu " + text)
        return True

    for group in group_units(units):
        # Sources that cannot share a unit at all are never in one model either.
        if not compile_group(group) and len(group) > 1:
            for i in group:
                compile_group([i])
    return entries, failed, sorted(set(inputs))


def ships_wasm(root: str, name: str) -> bool:
    """Whether the library ships a wasm module for `Library="name"` itself."""
    return any(os.path.exists(os.path.join(root, "Resources", "Library", TARGET, f))
               for f in (name + ".wasm", "lib" + name + ".wasm"))


def file_key(path: str, roots: list[str]) -> str:
    for root in roots:
        root = os.path.realpath(root)
        if path.startswith(root + os.sep):
            return os.path.relpath(path, root)
    return os.path.basename(path)


def files_hash(paths: list[str], extra: object) -> str:
    """A hash of `extra` and the contents of `paths`, which decides when a build is stale."""
    h = hashlib.sha256(json.dumps(extra, sort_keys=True).encode())
    for p in sorted(set(paths)):
        h.update(p.encode())
        h.update(sha256_file(p).encode())
    return h.hexdigest()[:16]


def spec_hash(spec: dict) -> str:
    """A system library's spec, the files beside its build script and the WASI
    shims they may share."""
    here = os.path.dirname(spec["build"])
    files = sorted(os.path.join(root, f) for root, _, names in os.walk(here) for f in names)
    shared = os.path.join(os.path.dirname(here), "wasi.h")
    return files_hash(files + ([shared] if os.path.exists(shared) else []), spec)


def recipe_hash(recipe: dict, systemlibs: dict) -> str:
    """A recipe, the headers it forces in and the system libraries it uses."""
    forced = recipe.get("include", []) + recipe.get("common", {}).get("include", []) + \
        [h for lib in recipe.get("libraries", {}).values() for h in lib.get("include", [])]
    return files_hash(forced, [recipe, GENERATION, WASM_FEATURES, sorted(
        (n, l["entry"]["sha256"]) for n, l in systemlibs.items())])


def build_system_library(name: str, spec: dict, toolchain: Toolchain, output: str, state: dict, abi: int,
                         base_url: str, cachedir: str, deps: dict) -> dict:
    """Build a system library once per version and ABI. Its `build` script gets the
    omc installation and an output directory, and fills `dist/` with what ships
    and `include/` with the headers the libraries using it are compiled against.
    One without a `module` ships nothing: its `archives` are linked into the
    libraries using it. The system libraries it uses (`deps`) are named by
    `SYSLIB_<name>` directories, and `OMC_WASM_FEATURES` the wasm features to target."""
    old = state.get("systemLibraries", {}).get(name)
    workdir = os.path.join(cachedir, "%s-%s-abi%d" % (name, spec["version"], abi))
    key = files_hash(
        [], [
            spec_hash(spec), GENERATION, WASM_FEATURES, sorted(
                (n, d["entry"]["sha256"]) for n, d in deps.items())])
    if old and old.get("spec") == key and old.get("abi") == abi and os.path.isdir(workdir):
        return old
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    env = dict(os.environ, OPENMODELICAHOME=toolchain.omhome, OUT=workdir, OMC_WASM_FEATURES=" ".join(WASM_FEATURES),
               OMC_WASI_CLANG=toolchain.clang, OMC_WASI_SYSROOT=toolchain.sysroot,
               **{"SYSLIB_" + n.replace("-", "_"): d["workdir"] for n, d in deps.items()})
    subprocess.run([os.path.abspath(spec["build"]), workdir], check=True, env=env)
    if "module" not in spec:
        entry = {"abi": abi, "version": spec["version"], "spec": key,
                 "sha256": files_hash([os.path.join(workdir, a) for a in spec.get("archives", [])], name)}
        state.setdefault("systemLibraries", {})[name] = entry
        return entry
    zipdir = os.path.join(output, str(abi), "system")
    os.makedirs(zipdir, exist_ok=True)
    tmp = os.path.join(zipdir, name + ".zip")
    write_zip(os.path.join(workdir, "dist"), tmp)
    digest = sha256_file(tmp)
    zipname = "%s-%s-%s-%s.zip" % (name, spec["version"], TARGET, digest[:16])
    os.replace(tmp, os.path.join(zipdir, zipname))
    entry = {"abi": abi, "version": spec["version"], "sha256": digest, "spec": key,
             "zipfile": "%s%d/system/%s" % (base_url, abi, zipname)}
    state.setdefault("systemLibraries", {})[name] = entry
    return entry


def build_toolchain(libc: dict, libcxx: dict | None, output: str, base_url: str, state: dict) -> None:
    """Zip the sysroot everything is built against, which omc installs to compile
    a model's own external C code for this generation, and, for C++ code, what
    libc++ adds to it: its headers and `libc++.so`."""
    zipdir = os.path.join(output, "toolchain")
    os.makedirs(zipdir, exist_ok=True)

    def publish(src: str, stem: str) -> dict:
        tmp = os.path.join(zipdir, stem + ".zip")
        write_zip(src, tmp)
        digest = sha256_file(tmp)
        zipname = "%s-%s-%d-%s.zip" % (stem, TARGET, GENERATION, digest[:16])
        os.replace(tmp, os.path.join(zipdir, zipname))
        return {"sha256": digest, "zipfile": "%stoolchain/%s" % (base_url, zipname)}

    state["toolchain"] = dict(generation=GENERATION, **publish(os.path.join(libc["workdir"], "sysroot"), "sysroot"))
    if libcxx is not None:
        with tempfile.TemporaryDirectory(prefix="om-wasm-cxx-") as tmp:
            # Where clang++ --sysroot looks for them.
            shutil.copytree(os.path.join(libcxx["workdir"], "include", "c++", "v1"),
                            os.path.join(tmp, "include", TARGET, "c++", "v1"))
            os.makedirs(os.path.join(tmp, "lib", TARGET))
            shutil.copy(os.path.join(libcxx["workdir"], "lib", "libc++.so"), os.path.join(tmp, "lib", TARGET))
            state["toolchain"]["cxx"] = publish(tmp, "sysroot-cxx")


def omc_script(omc: str, home: str, script: str, cwd: str) -> str:
    path = os.path.join(cwd, "build.mos")
    with open(path, "w") as f:
        f.write(script)
    env = dict(os.environ, HOME=home)
    env.pop("OPENMODELICALIBRARY", None)
    try:
        res = subprocess.run([omc, path], cwd=cwd, env=env, capture_output=True, text=True, timeout=OMC_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        return "omc timed out after %d s\n%s" % (OMC_TIMEOUT, e.stdout or "")
    return res.stdout + res.stderr


def query_abi(omc: str) -> int:
    """The bundle interface this omc loads, from its description of an empty library."""
    with tempfile.TemporaryDirectory(prefix="om-wasm-") as work:
        log = omc_script(omc, work, """
loadString("package OMPackageManagerEmpty end OMPackageManagerEmpty;"); getErrorString();
writeFile("%s/externals.json", getExternalFunctions(OMPackageManagerEmpty)); getErrorString();
""" % work, work)
        try:
            with open(os.path.join(work, "externals.json")) as f:
                return json.load(f)["abi"]
        except (FileNotFoundError, ValueError):
            raise Exception("%s cannot describe external functions:\n%s" % (omc, log))


def build_library_version(libname: str, version: str, recipe: dict, systemlibs: dict, omc: str,
                          toolchain: Toolchain, index_path: str, output: str, base_url: str,
                          downloads: str) -> dict | None:
    with tempfile.TemporaryDirectory(prefix="om-wasm-") as work:
        home = os.path.join(work, "home")
        libdir = os.path.join(home, ".openmodelica", "libraries")
        os.makedirs(libdir)
        os.symlink(downloads, os.path.join(home, ".openmodelica", "cache"))
        shutil.copy(index_path, os.path.join(libdir, "index.json"))
        bundle = os.path.join(work, "bundle")
        os.makedirs(bundle)
        log = omc_script(omc, home, """
installPackage(%(lib)s, "%(ver)s", exactMatch=true); getErrorString();
loadModel(%(lib)s, {"%(ver)s"}, requireExactVersion=true); getErrorString();
writeFile("%(work)s/root.txt", uriToFilename("modelica://%(lib)s/"));
writeFile("%(work)s/externals.json", getExternalFunctions(%(lib)s)); getErrorString();
""" % {"lib": libname, "ver": version, "work": work}, work)
        try:
            with open(os.path.join(work, "externals.json")) as f:
                described = json.load(f)
            with open(os.path.join(work, "root.txt")) as f:
                root = f.read().strip()
        except (FileNotFoundError, ValueError):
            print("getExternalFunctions failed for %s %s:\n%s" % (libname, version, log))
            return None
        abi = described["abi"]
        forced = recipe.get("include", [])
        isystem = [os.path.join(systemlibs[s]["workdir"], d)
                   for s in recipe.get("systemLibraries", []) for d in systemlibs[s]["includes"]]
        functions, failed_fns, inputs = build_include_modules(described["functions"], toolchain, forced, isystem,
                                                              bundle, work)
        manifest = {"abi": abi, "functions": functions, "failed": failed_fns, "libraries": {}}
        manifest_path = os.path.join(bundle, MANIFEST)
        inputs = ["generation %d" % GENERATION, "features " + " ".join(WASM_FEATURES),
                  "functions " + json.dumps(functions, sort_keys=True)] + inputs
        needed: set[str] = set()
        # What the library's own build project configures (CMake's configure_file).
        for dest, conf in recipe.get("configure", {}).items():
            if os.path.exists(os.path.join(root, conf["from"])):
                with open(os.path.join(root, conf["from"])) as f:
                    text = f.read()
                for k, v in conf.get("values", {}).items():
                    text = text.replace("@%s@" % k, v)
                with open(os.path.join(root, dest), "w") as f:
                    f.write(text)
        common = recipe.get("common", {})
        for name, lib in sorted(recipe.get("libraries", {}).items()):
            lib = dict(lib, **{k: common.get(k, []) + lib.get(k, []) for k in ("includes", "defines", "include")})
            sources = recipe_sources(root, lib)
            if sources is None or ships_wasm(root, name):
                continue
            links = [os.path.join(systemlibs[s]["workdir"], a)
                     for s in lib.get("systemLibraries", []) for a in systemlibs[s].get("archives", [])]
            hidden = recipe_sources(root, dict(sources=lib.get("hidden", []))) or []
            uses = lib.get("systemLibraries", [])
            includes = [os.path.join(root, d) for d in lib.get("includes", [])]
            cxx_includes = []
            for s in uses:
                includes += [os.path.join(systemlibs[s]["workdir"], d) for d in systemlibs[s]["includes"]]
                cxx_includes += [os.path.join(systemlibs[s]["workdir"], d)
                                 for d in systemlibs[s].get("cxxIncludes", [])]
                links += [os.path.join(systemlibs[s]["workdir"], d) for d in systemlibs[s].get("links", [])]
            defines = lib.get("defines", [])
            forced = lib.get("include", [])
            try:
                files = toolchain.deps(sources, includes, defines, forced, cxx_includes=cxx_includes)
                toolchain.shared_library(sources, includes, defines, os.path.join(bundle, name + ".wasm"),
                                         links, forced, hidden, cxx_includes=cxx_includes)
            except subprocess.CalledProcessError as e:
                manifest.setdefault("failed", {})[name] = (e.stderr or "").strip()
                print("Library %s of %s %s did not compile:\n%s" % (name, libname, version, e.stderr))
                continue
            inputs.append("library %s %s" % (name, json.dumps(lib, sort_keys=True)))
            inputs += ["file %s %s" % (file_key(p, [root] + includes), sha256_file(p))
                       for p in files if not p.startswith(os.path.realpath(toolchain.sysroot))]
            inputs += ["link %s %s" % (os.path.basename(f), sha256_file(f)) for f in links]
            needed.update(s for s in uses if "module" in systemlibs[s])
        # A `Library` the bundle builds, or the library ships for wasm itself, is not
        # taken from a system library.

        def shadowed(alias: str) -> bool:
            return os.path.exists(os.path.join(bundle, alias + ".wasm")) or ships_wasm(root, alias)
        needed.update(s for s in recipe.get("systemLibraries", [])
                      if "module" in systemlibs[s] and not all(shadowed(a) for a in systemlibs[s]["provides"]))
        # The modules those load in turn (ModelicaSDF its libc++).
        todo = list(needed)
        while todo:
            for d in systemlibs[todo.pop()].get("systemLibraries", []):
                if "module" in systemlibs[d] and d not in needed:
                    needed.add(d)
                    todo.append(d)
        if [f for f in os.listdir(bundle) if f.endswith(".wasm")] or manifest["functions"]:
            needed.add(LIBC)
        for s in sorted(needed):
            spec = systemlibs[s]
            inputs.append("system %s %s" % (s, spec["entry"]["sha256"]))
            env = {k: os.path.normpath(os.path.join(s, v)) for k, v in spec.get("environment", {}).items()}
            for alias in spec["provides"]:
                if not shadowed(alias):
                    manifest["libraries"][alias] = {"module": "%s/%s" % (s, spec["module"]), "environment": env}

        failed = {"failed": sorted(manifest["failed"])} if manifest.get("failed") else {}
        if not manifest["functions"] and not [f for f in os.listdir(bundle) if f.endswith(".wasm")]:
            return dict(abi=abi, **failed)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")
        digest = hashlib.sha256("\n".join(inputs).encode()).hexdigest()
        zipdir = os.path.join(output, str(abi))
        os.makedirs(zipdir, exist_ok=True)
        zipname = "%s-%s-%s.zip" % (libname, TARGET, digest[:16])
        zippath = os.path.join(zipdir, zipname)
        if not os.path.exists(zippath):
            write_zip(bundle, zippath)
        entry = {"abi": abi, "generation": GENERATION, "zipfile": "%s%d/%s" % (base_url, abi, zipname),
                 "sha256": sha256_file(zippath)}
        if needed:
            entry["systemLibraries"] = sorted(needed)
        return dict(entry, **failed)


def main(
        output: str = "www-data/precompiled/wasm32-wasip1",
        omc: str = "omc",
        base_url: str = DEFAULT_URL,
        only: list[str] | None = None):
    """Build the wasm bundles of the libraries in index.json, or only those named in `only`."""
    with open("repos.json") as f:
        repos = json.load(f)
    with open("index.json") as f:
        index = json.load(f)
    systemspecs = {}
    if os.path.exists("wasm-system-libraries.json"):
        with open("wasm-system-libraries.json") as f:
            systemspecs = json.load(f)
    state = {}
    if os.path.exists("wasmdata.json"):
        with open("wasmdata.json") as f:
            state = json.load(f)
    omc = shutil.which(omc) or omc
    toolchain = Toolchain(os.path.dirname(os.path.dirname(os.path.realpath(omc))))
    cachedir = os.path.realpath(os.path.join("cache", "wasm-system"))
    downloads = os.path.realpath(os.path.join("cache", "wasm-downloads"))
    os.makedirs(downloads, exist_ok=True)
    output = os.path.realpath(output)
    base_url = base_url if base_url.endswith("/") else base_url + "/"
    abi = query_abi(omc)

    recipes = {name: repo["wasm"] for repo in repos.values() if "wasm" in repo for name in repo["names"]}
    systemlibs = {}

    def system_library(s: str) -> dict | None:
        """The built system library `s`, after the ones it uses; None if any did not build."""
        if s not in systemlibs:
            spec = systemspecs[s]
            deps = {d: system_library(d) for d in spec.get("systemLibraries", [])}
            systemlibs[s] = None
            if all(deps.values()):
                try:
                    entry = build_system_library(s, spec, toolchain, output, state, abi, base_url, cachedir, deps)
                    systemlibs[s] = dict(spec, entry=entry, workdir=os.path.join(
                        cachedir, "%s-%s-abi%d" % (s, spec["version"], entry["abi"])))
                except subprocess.CalledProcessError as e:
                    print("System library %s did not build: %s" % (s, e), flush=True)
        return systemlibs[s]

    libc = system_library(LIBC)
    if libc is None:
        raise Exception("the libc every module is built against did not build")
    toolchain.use_sysroot(os.path.join(libc["workdir"], "sysroot"))
    build_toolchain(libc, system_library(LIBCXX) if LIBCXX in systemspecs else None, output, base_url, state)
    for libname, lib in sorted(index["libs"].items()):
        if only and libname not in only:
            continue
        recipe = recipes.get(libname, {})
        uses = sorted({s for lib in recipe.get("libraries", {}).values() for s in lib.get("systemLibraries", [])} |
                      set(recipe.get("systemLibraries", [])))
        if not all([system_library(s) for s in uses]):
            print("Skipping %s: a system library it uses did not build" % libname, flush=True)
            continue
        key = recipe_hash(recipe, {s: systemlibs[s] for s in uses + [LIBC]})
        done = state.setdefault("libs", {}).setdefault(libname, {})
        versions = [(ver, v) for ver, v in sorted(lib["versions"].items()) if ver == v["version"]]
        # A library whose C sources stay backwards compatible (the MSL) gives every
        # release the modules of the newest one; prereleases and branches build their own.
        latest = None
        if recipe.get("latestRelease"):
            releases = [ver for ver, _ in versions if not VersionNumber(ver).prerelease]
            if releases:
                latest = max(releases, key=VersionNumber)
                versions.sort(key=lambda x: x[0] != latest)
        for version, v in versions:
            source = v.get("sha") or v["zipfile"]
            old = done.get(version)
            if latest is not None and version != latest and not VersionNumber(version).prerelease:
                built = done.get(latest)
                if built is not None and not (old and old.get("source") == source and
                                              old.get("zipfile") == built.get("zipfile")):
                    done[version] = dict(built, source=source)
                continue
            if old and old.get("source") == source and old.get("abi") == abi and old.get("recipe") == key:
                continue
            print("Building wasm externals of %s %s" % (libname, version), flush=True)
            entry = build_library_version(libname, version, recipe, systemlibs, omc, toolchain,
                                          os.path.realpath("index.json"), output, base_url, downloads)
            if entry is None:
                continue
            entry["source"] = source
            entry["recipe"] = key
            done[version] = entry
        if not done:
            del state["libs"][libname]
        write_state(state, abi)
    write_state(state, abi)


def write_state(state: dict, abi: int) -> None:
    state["abi"] = abi
    with open("wasmdata.json", "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
