#!/usr/bin/env python3

import OMPython
import os
from github import Github
from atlassian import Bitbucket
import json
import pygit2
import glob
import re
import shutil
import requests
import zipfile

import common

bitbucket = Bitbucket(url="https://api.bitbucket.org")

def removerepo(ghurl, repopath):
  print("Removing repository " + ghurl)
  shutil.rmtree(repopath)

tagregex = re.compile('^refs/tags')

def alltags(gitrepo):
  return list((remove_prefix(e, "refs/tags/"), str(gitrepo.lookup_reference_dwim(e).target)) for e in filter(lambda r: tagregex.match(r), gitrepo.listall_references()))

def remove_prefix(text, prefix):
  return text[text.startswith(prefix) and len(prefix):]

def allbranches(gitrepo):
  return [(remove_prefix(e, "origin/"),str(gitrepo.lookup_reference_dwim(e).target)) for e in gitrepo.branches.remote]

def getgitrepo(url, repopath):
  if os.path.exists(repopath):
    gitrepo = pygit2.Repository(repopath)
    if len(gitrepo.remotes) != 1 or gitrepo.remotes[0].url != url:
      removerepo(url, repopath)
    else:
      gitrepo.remotes[0].fetch()
  if not os.path.exists(repopath):
    pygit2.clone_repository(url, repopath)
  gitrepo = pygit2.Repository(repopath)
  return gitrepo

def insensitive_glob(pattern):
  def either(c):
    return '[%s%s]' % (c.lower(), c.upper()) if c.isalpha() else c
  return glob.glob(''.join(either(char) for char in pattern))

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
    for name in data[key].get("names",[]):
      if name in namesInFile:
        raise Exception(key + " exists multiple times")
      namesInFile.add(name)

  for key in sorted(data.keys()):
    entry = data[key]
    repopath = os.path.join("cache", key)
    if "ignore" in entry:
      continue

    if len(insensitive_glob(repopath)) > 1:
      for d in insensitive_glob(repopath):
        print("Cleaning duplicate case-insensitive names")
        shutil.rmtree(d)

    if "github" in entry or "git" in entry or "zipfiles" in entry:
      if "github" in entry:
        try:
          r = g.get_repo(entry["github"])
          branches = list((b.name, b.commit.sha) for b in r.get_branches())
          tags = list((b.name, b.commit.sha) for b in r.get_tags())
          giturl = "https://github.com/%s.git" % entry["github"]
        except:
          print("Failed to get github entry: %s" % entry["github"])
          raise
      elif "git" in entry:
        giturl = entry["git"]
        gitrepo = getgitrepo(giturl, repopath+".git")
        branches = allbranches(gitrepo)
        if entry.get("bitbucket-api-downloads-instead-of-tags"):
          tags = []
          for download in bitbucket._get_paged("2.0/repositories/%s/downloads" % entry.get("bitbucket-api-downloads-instead-of-tags")):
            name = download["name"]
            if name.endswith(".zip") and name.startswith(key):
              ver = common.VersionNumber(name[len(key):-4].strip("-").strip(" "))
              if ver.major==0 and ver.minor==0 and ver.patch==0:
                continue
              tags.append(("v" + str(ver),download["links"]["self"]["href"]))
        else:
          tags = alltags(gitrepo)
      elif "zipfiles" in entry:
        branches = []
        tags = list(entry["zipfiles"].items())
        giturl = ""

      if key not in serverdata:
        serverdata[key] = {}
        print("Did not have stored data for " + key)
      if "refs" not in serverdata[key]:
        serverdata[key]["refs"] = {}
      ignoreTags = set()
      if "ignore-tags" in entry:
        ignoreTags = set(entry["ignore-tags"])
      objects = []
      for (name,sha) in branches:
        if name in (entry.get("branches") or []):
          objects.append((entry["branches"][name], sha))
      for (name,sha) in tags:
        if name not in ignoreTags:
          objects.append((name, sha))
          
      if not objects:
        raise Exception("No commits or zip-files found for %s" % key)

      tagsDict = serverdata[key]["refs"]

      for (tagName, sha) in objects:
        if not isinstance(tagName, str):
          names = tagName["names"]
          tagName = tagName["version"]
        else:
          names = entry["names"]
        v = common.VersionNumber(tagName)
        # v3.2.1+build.0-beta.1 is not a pre-release...
        for build in v.build:
          if "-" in build:
            raise Exception("Release build string looks like a pre-release: %s" % v)
        if tagName not in tagsDict:
          tagsDict[tagName] = {}
        thisTagBackup = tagsDict[tagName]
        thisTag = tagsDict[tagName]

        entrykind = "zip" if ("zipfiles" in entry or sha.startswith("http")) else "sha"

        if (entrykind not in thisTag) or (thisTag[entrykind] != sha):
          if entrykind == "zip":
            try:
              os.unlink(repopath)
            except:
              pass
            try:
              shutil.rmtree(repopath)
            except FileNotFoundError:
              pass
            os.mkdir(repopath)
            zipfilepath = repopath + "-" + tagName + ".zip"
            with open(zipfilepath, 'wb') as fout:
              fout.write(requests.get(sha, allow_redirects=True).content)
            with zipfile.ZipFile(zipfilepath, 'r') as zip_ref:
              zip_ref.extractall(repopath)
          else:
            gitrepo = getgitrepo(giturl, repopath+".git")
            try:
              gitrepo.checkout_tree(gitrepo.get(sha), strategy = pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)
              try:
                os.unlink(repopath)
              except:
                pass
              try:
                shutil.rmtree(repopath)
              except FileNotFoundError:
                pass
              shutil.copytree(repopath+".git", repopath)
            except:
              print("Failed to checkout %s with SHA %s" % (tagName, sha))
              raise
          omc.sendExpression("OpenModelica.Scripting.getErrorString()")

          provided = {}
          for libname in names:
            hits = insensitive_glob(os.path.join(repopath,"package.mo"))
            if len(hits) == 1:
              if libname != entry["names"][0]:
                continue
            else:
              hits = []
              for extraPath in ([""] + (entry.get("search-extra-paths") or [])):
                p = repopath
                if extraPath != "":
                  p = os.path.join(repopath, extraPath)
                else:
                  p = repopath
                hitsNew = (insensitive_glob(os.path.join(p,libname,"package.mo")) +
                  insensitive_glob(os.path.join(p,libname+" *","package.mo")) +
                  insensitive_glob(os.path.join(p,libname+"-*","package.mo")) +
                  insensitive_glob(os.path.join(p,libname+".mo")) +
                  insensitive_glob(os.path.join(p,libname+" *.mo")) +
                  insensitive_glob(os.path.join(p,libname+"-*.mo")) +
                  insensitive_glob(os.path.join(p,libname+"*",libname + ".mo")) +
                  insensitive_glob(os.path.join(p,libname+"*",libname + "-*.mo")) +
                  insensitive_glob(os.path.join(p,libname+"*",libname + " *.mo")))
                hits += hitsNew
            if len(hits) != 1:
              print(str(len(hits)) + " hits for " + libname + " in " + tagName + ": " + str(hits))
              continue
            omc.sendExpression("clear()")
            if "standard" in entry:
              grammar = common.findMatchingLevel(tagName, entry["standard"])
              if grammar is None:
                grammar = "latest"
            else:
              grammar = "latest"
            omc.sendExpression("setCommandLineOptions(\"--std=%s\")" % grammar)

            if not omc.sendExpression("loadFile(\"%s\", uses=false)" % hits[0]):
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
              if len(v2.prerelease) == 0 and entry.get("semverTagOverridesAnnotation") and (v2 > v1 or entry["semverTagOverridesAnnotation"] == "alsoNewerVersions"):
                v1 = v2
              if len(v2.prerelease) > 0 and (len(v1.prerelease) == 0 or entry.get("semverPrereleaseOverridesAnnotation") or tagName in ["master", "main", "trunk"]):
                v1.prerelease = v2.prerelease
                if tagName in ["master", "main", "trunk"] and len(v2.build) == 0:
                  v1.build = []
              if v1.major == v2.major and v1.minor == v2.minor and v1.patch == v2.patch and len(v1.prerelease) == 0 and len(v1.build) == 0:
                version = str(v2)
              else:
                version = str(v1)
            if version.startswith("0.0.0-"):
              version = version[6:]
            if version.startswith("+"):
              version = version[1:]
            uses = sorted([[e[0],str(common.VersionNumber(e[1]))] for e in omc.sendExpression("getUses(%s)" % libname)])
            for ignore in entry.get("ignore-uses", []):
              uses = [use for use in uses if use[0] != ignore]
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
          try:
            errorString = omc.sendExpression("OpenModelica.Scripting.getErrorString()")
          except UnicodeDecodeError:
            print("UnicodeDecodeError for %s %s" % (key, tagName))
            raise
          if len(provided) == 0:
            print("Broken for " + key + " " + tagName) # + ":" + errorString)
            tagsDict[tagName] = thisTagBackup
            continue
          thisTag["libs"] = provided
          thisTag[entrykind] = sha
          if "broken" in thisTag:
            del thisTag["broken"]
        # level = getSupportLevel(tagName, entry["support"])
        # thisTag["support"] = level
      serverdata[key]["refs"] = tagsDict
    else:
      raise Exception("Don't know how to handle entry for %s: %s" % (key, entry))
  with open("rawdata.json","w") as io:
    json.dump(serverdata, io, sort_keys=True, indent=2)
if __name__ == '__main__':
  main()
