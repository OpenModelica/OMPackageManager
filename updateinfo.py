#!/usr/bin/env python3

import OMPython
import os
from github import Github
import json
import pygit2
import glob

import common

def removerepo(ghurl, repopath):
  print("Removing repository " + ghurl)
  os.path.rmtree(repopath)

def main():
  gh_auth = os.environ["GITHUB_AUTH"]
  g = Github(gh_auth)

  omc = OMPython.OMCSessionZMQ()

  data = json.load(open("repos.json"))
  if os.path.exists("rawdata.json"):
    serverdata = json.load(open("rawdata.json"))
  else:
    serverdata = {}

  if not os.path.exists("cache"):
    os.mkdir("cache")

  namesInFile = set()
  for key in data.keys():
    for name in data[key]["names"]:
      if name in namesInFile:
        raise Exception(key + " exists multiple times")
      namesInFile.add(name)

  for key in data.keys():
    entry = data[key]
    if "github" in entry:
      try:
        r = g.get_repo(entry["github"])
      except:
        print("Failed to get github entry: %s" % entry["github"])
        raise()

      if key not in serverdata:
        serverdata[key] = {}
        print("Did not have stored data for " + key)
      if "refs" not in serverdata[key]:
        serverdata[key]["refs"] = {}
      ignoreTags = set()
      if "ignore-tags" in entry:
        ignoreTags = set(entry["ignore-tags"])
      branches = list(r.get_branches())
      tags = list(r.get_tags())
      objects = []
      for b in branches:
        if b.name in (entry.get("branches") or []):
          objects.append((entry["branches"][b.name], b.commit.sha))
      for t in tags:
        if t.name not in ignoreTags:
          objects.append((t.name, t.commit.sha))

      tagsDict = serverdata[key]["refs"]
      repopath = os.path.join("cache", key)

      for (tagName, sha) in objects:
        v = common.VersionNumber(tagName)
        # v3.2.1+build.0-beta.1 is not a pre-release...
        for build in v.build:
          if "-" in build:
            raise Exception("Release build string looks like a pre-release: %s" % v)
        if tagName not in tagsDict:
          tagsDict[tagName] = {}
        thisTag = tagsDict[tagName]

        if ("sha" not in thisTag) or (thisTag["sha"] != sha):
          ghurl = "https://github.com/%s.git" % entry["github"]
          if os.path.exists(repopath):
            gitrepo = pygit2.Repository(repopath)
            if len(gitrepo.remotes) != 1:
              removerepo(ghurl, repopath)
            else:
              gitrepo.remotes[0].fetch()
          if not os.path.exists(repopath):
            pygit2.clone_repository(ghurl, repopath)
          gitrepo = pygit2.Repository(repopath)
          try:
            gitrepo.checkout_tree(gitrepo.get(sha), strategy = pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)
          except:
            print("Failed to checkout %s with SHA %s" % (tagName, sha))
            raise
          omc.sendExpression("OpenModelica.Scripting.getErrorString()")

          provided = {}
          for libname in entry["names"]:
            hits = glob.glob(os.path.join(repopath,"package.mo"))
            if len(hits) == 1:
              if libname != entry["names"][0]:
                continue
            else:
              hits = (glob.glob(os.path.join(repopath,libname,"package.mo")) +
                glob.glob(os.path.join(repopath,libname+" *","package.mo")) +
                glob.glob(os.path.join(repopath,libname+".mo")) +
                glob.glob(os.path.join(repopath,libname+" *.mo")) +
                glob.glob(os.path.join(repopath,libname+"*",libname + ".mo")) +
                glob.glob(os.path.join(repopath,libname+"*",libname + " *.mo")))
            if len(hits) != 1:
              print(str(len(hits)) + " hits for " + libname + " in " + tagName)
              continue
            omc.sendExpression("clear()")
            if "standard" in entry:
              grammar = common.findMatchingLevel(tagName, entry["standard"])
              if grammar is None:
                grammar = "latest"
            else:
              grammar = "latest"
            omc.sendExpression("setCommandLineOptions(\"--std=%s\")" % grammar)

            if not omc.sendExpression("loadFile(\"%s\")" % hits[0]):
              print("Failed to load file %s in %s" % (hits[0], tagName))
              continue
            classNamesAfterLoad = omc.sendExpression("getClassNames()")
            if libname not in classNamesAfterLoad:
              print("Did not load the library? ")
              print(classNamesAfterLoad)
              continue
            version = omc.sendExpression("getVersion(%s)" % libname)
            if version == "":
              version = str(common.VersionNumber(tagName))
            else:
              v1 = common.VersionNumber(version)
              v2 = common.VersionNumber(tagName)
              if len(v2.prerelease) == 0 and entry.get("semverTagOverridesAnnotation") and v2 > v1:
                v1 = v2
              if len(v2.prerelease) > 0 and len(v1.prerelease) == 0:
                v1.prerelease = v2.prerelease
              if v1.major == v2.major and v1.minor == v2.minor and v1.patch == v2.patch and len(v1.prerelease) == 0 and len(v1.build) == 0:
                version = str(v2)
              else:
                version = str(v1)
            uses = sorted([[e[0],str(common.VersionNumber(e[1]))] for e in omc.sendExpression("getUses(%s)" % libname)])
            # Get conversions
            (withoutConversion,withConversion) = omc.sendExpression("getConversionsFromVersions(%s)" % libname)
            withoutConversion = list(filter(None, [str(ver) for ver in sorted([common.VersionNumber(v) for v in withoutConversion])]))
            withConversion = list(filter(None, [str(ver) for ver in sorted([common.VersionNumber(v) for v in withConversion])]))
            path = hits[0][len(repopath)+1:]
            if os.path.basename(hits[0]) == "package.mo":
              path = os.path.dirname(path)
            libentry = {"version": version, "path": path}
            if len(uses)>0:
              libentry["uses"] = dict(uses)
            if len(withoutConversion)>0:
              libentry["provides"] = withoutConversion
            if len(withConversion)>0:
              libentry["convertFromVersion"] = withConversion
            provided[libname] = libentry
          errorString = omc.sendExpression("OpenModelica.Scripting.getErrorString()")
          if len(provided) == 0:
            print("Broken for " + key + " " + tagName) # + ":" + errorString)
            thisTag["broken"]=True
            continue
          thisTag["libs"] = provided
          thisTag["sha"] = sha
        # level = getSupportLevel(tagName, entry["support"])
        # thisTag["support"] = level
      serverdata[key]["refs"] = tagsDict

  with open("rawdata.json","w") as io:
    json.dump(serverdata, io, sort_keys=True, indent=2)
if __name__ == '__main__':
  main()
