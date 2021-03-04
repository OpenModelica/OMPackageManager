#!/usr/bin/env python3

import json
import common

def main():
  repos = json.load(open("repos.json"))
  rawdata = json.load(open("rawdata.json"))

  indexdata = {"libs": {}}
  for firstKey in rawdata.keys():
    data = rawdata[firstKey]
    for refKey in data["refs"].keys():
      r = data["refs"][refKey]
      if "broken" in r:
        continue
      if "libs" not in r:
        raise Exception(refKey)
      for libName in r["libs"]:
        lib = r["libs"][libName]
        if libName not in indexdata["libs"]:
          if "github" in repos[firstKey]:
            indexdata["libs"][libName] = {"git": "https://github.com/%s.git" % repos[firstKey]["github"], "versions": {}}
            isgit = True
          elif "git" in repos[firstKey]:
            indexdata["libs"][libName] = {"git": repos[firstKey]["git"], "versions": {}}
            isgit = True
          else:
            indexdata["libs"][libName] = {"versions": {}}
            isgit = False
        libdict = indexdata["libs"][libName]["versions"]
        if lib['version'] in libdict.keys():
          if len(common.VersionNumber(refKey).prerelease)>0:
            continue
          print('Duplicate entry for %s %s (%s)' % (libName, lib['version'], refKey))
        entry = {}

        if isgit:
          if "sha" in r or "zip" not in r: # If we have zip-file but no sha, we might use a releases zip for a tag we don't know the SHA of
            entry['sha'] = r['sha']
        entry['path'] = lib['path']
        entry['version'] = lib['version']
        if "zip" in r:
          entry['zipfile'] = r["zip"]
        elif "github" in repos[firstKey]:
          entry['zipfile'] = "https://github.com/%s/archive/%s.zip" % (repos[firstKey]["github"], r['sha'])
        else:
          entry['zipfile'] = repos[firstKey]["zipfile"] % r['sha']
        if 'provides' in lib:
          entry['provides'] = lib['provides']
        if 'uses' in lib:
          entry['uses'] = lib['uses']
        if 'convertFromVersion' in lib:
          entry['convertFromVersion'] = lib['convertFromVersion']
        entry['support'] = common.getSupportLevel(lib['version'], repos[firstKey]['support'])

        libdict[lib['version']] = entry
        # print(entry)
    # for lib in data["libs"].keys():

  with open("index.json","w") as io:
    json.dump(indexdata, io, sort_keys=True, indent=0)

if __name__ == '__main__':
  main()
