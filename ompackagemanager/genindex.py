import json

from ompackagemanager import common


class MissingUses(Exception):
    pass


class DuplicateVersions(Exception):
    pass


def onlyVersioninSemVer(ver):
    ver.prerelease = []
    ver.build = []
    return ver


def onlyMainVersion(ver):
    v = common.VersionNumber(ver)
    return "%d.%d.%d" % (v.major, v.minor, v.patch)


def allProvidesAndVersion(lib):
    res = set()
    for provides in lib.get('provides', []):
        res.add(onlyMainVersion(provides))
    res.add(onlyMainVersion(lib['version']))
    return res


def checkProvides2(worklist, visited, origLibName, origVisited, indexdata):
    while worklist:
        (libName, lib) = worklist.pop()
        wasVisited = False
        for (name, myset) in visited:
            if libName == name:
                if origLibName == name:
                    origVisited.add(onlyMainVersion(lib['version']))
                if onlyMainVersion(lib['version']) not in myset:
                    raise DuplicateVersions(
                        "%s needs to load both version %s and %s. Visited nodes:\n%s" %
                        (libName, lib['version'], myset, visited))
                wasVisited = True
                break
        if wasVisited:
            continue
        visited += [(libName, allProvidesAndVersion(lib))]
        uses = lib.get('uses', {})
        for usesName in uses.keys():
            usesVersion = uses[usesName]
            usesVersions = indexdata["libs"][usesName]["versions"].values()
            versionsThatProvideTheUses = [
                v for v in usesVersions if usesVersion in v.get(
                    'provides',
                    []) or onlyVersioninSemVer(
                    common.VersionNumber(usesVersion)) == onlyVersioninSemVer(
                    common.VersionNumber(
                        v['version']))]
            if len(versionsThatProvideTheUses) == 1:
                worklist += [((usesName, versionsThatProvideTheUses[0]))]
            elif not versionsThatProvideTheUses:
                allVersions = set()
                for v in usesVersions:
                    allVersions = allVersions.union(allProvidesAndVersion(v))
                raise MissingUses(
                    "%s %s depends on %s %s that does not exist. Existing versions: %s" %
                    (libName, lib["version"], usesName, usesVersion, allVersions))
            else:
                lst = []
                for ver in versionsThatProvideTheUses:
                    try:
                        res = checkProvides2(worklist.copy() + [(usesName, ver)],
                                             visited.copy(),
                                             origLibName,
                                             origVisited.copy(),
                                             indexdata)
                        lst += [res]
                    except DuplicateVersions:
                        pass
                    except MissingUses:
                        pass
                if not lst:
                    raise MissingUses(
                        "%d/%d provides worked for %s: %s with visited %s" %
                        (len(lst), len(versionsThatProvideTheUses), usesName,
                            [v["version"] for v in versionsThatProvideTheUses], visited))
                noConflict = False
                for l in lst:
                    if not l:
                        noConflict = True
                if noConflict:
                    continue
                for l in lst:
                    origVisited = origVisited.union(l)
    return origVisited


def checkProvides(libName, lib, indexdata):
    worklist = [(libName, lib)]
    visited = []
    origVisited = set()
    origVisited = checkProvides2(worklist, visited, libName, origVisited, indexdata)
    if origVisited:
        print("Found cycle. Changing provides to convertFromVersion: %s %s %s" % (libName, lib['version'], origVisited))
        lib['convertFromVersion'] = lib.get("convertFromVersion", []) + lib['provides']
        del lib['provides']


def main():
    """Generate `index.json` database from `rawdata.json`.
    """
    with open("repos.json", "r") as f:
        repos = json.load(f)
    with open("rawdata.json", "r") as f:
        rawdata = json.load(f)

    indexdata = {"libs": {}, "mirrors": ["https://libraries.openmodelica.org/cache/"]}
    for firstKey in rawdata.keys():
        data = rawdata[firstKey]
        for refKey in data["refs"].keys():
            r = data["refs"][refKey]
            if "broken" in r:
                continue
            if "libs" not in r:
                raise Exception(firstKey + " " + refKey)
            for libName in r["libs"]:
                lib = r["libs"][libName]
                isgit = False
                if libName not in indexdata["libs"]:
                    if "github" in repos[firstKey]:
                        indexdata["libs"][libName] = {
                            "git": "https://github.com/%s.git" %
                            repos[firstKey]["github"], "versions": {}}
                        isgit = True
                    elif "git" in repos[firstKey]:
                        indexdata["libs"][libName] = {"git": repos[firstKey]["git"], "versions": {}}
                        isgit = True
                    else:
                        indexdata["libs"][libName] = {"versions": {}}
                libdict = indexdata["libs"][libName]["versions"]
                if lib['version'] in libdict.keys():
                    prerelease = common.VersionNumber(refKey).prerelease
                    if prerelease is not None and len(prerelease) > 0 and prerelease[0] not in [
                            "master", "main", "trunk"]:
                        continue
                    print('Duplicate entry for %s %s (%s)' % (libName, lib['version'], refKey))
                entry = {}

                if isgit:
                    # If we have zip-file but no sha, we might use a releases zip for a tag we don't know the SHA of
                    if "sha" in r or "zip" not in r:
                        entry['sha'] = r['sha']
                entry['path'] = lib['path']
                entry['version'] = lib['version']
                if "zip" in r:
                    entry['zipfile'] = r["zip"]
                elif "github" in repos[firstKey]:
                    entry['zipfile'] = "https://github.com/%s/archive/%s.zip" % (repos[firstKey]["github"], r['sha'])
                elif "zipfile" in repos[firstKey]:
                    entry['zipfile'] = repos[firstKey]["zipfile"].format(r['sha'])
                else:
                    raise Exception(
                        "Entry does not list an entry \"zip\" (manually added zip-file), "
                        "\"github\" (project name), or \"zipfile\" URL from where to download "
                        "the git hash (gitlab/etc):\n" + str(r))
                if 'provides' in lib:
                    entry['provides'] = lib['provides']
                if 'uses' in lib:
                    entry['uses'] = lib['uses']
                if 'convertFromVersion' in lib:
                    entry['convertFromVersion'] = lib['convertFromVersion']
                if repos[firstKey].get('singleFileStructureCopyAllFiles'):
                    entry['singleFileStructureCopyAllFiles'] = True
                entry['support'] = common.getSupportLevel(lib['version'], repos[firstKey]['support'])

                libdict[lib['version']] = entry

                # Additional entry for main branch
                if refKey in ["master", "main", "trunk"]:
                    libdict[refKey] = entry

                # print(entry)
        # for lib in data["libs"].keys():

    for libName in indexdata["libs"].keys():
        versions = indexdata["libs"][libName]["versions"]
        for version in versions.keys():
            lib = versions[version]
            if 'provides' in lib:
                try:
                    checkProvides(libName, lib, indexdata)
                except MissingUses:
                    pass

    with open("index.json", "w") as io:
        json.dump(indexdata, io, sort_keys=True, indent=0)
