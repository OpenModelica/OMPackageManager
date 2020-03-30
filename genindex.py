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
      for libName in r["libs"]:
        lib = r["libs"][libName]
        if libName not in indexdata["libs"]:
          indexdata["libs"][libName] = {"git": "https://github.com/%s.git" % repos[firstKey]["github"], "versions": {}}
        libdict = indexdata["libs"][libName]["versions"]
        if lib['version'] in libdict.keys():
          if len(common.VersionNumber(refKey).prerelease)>0:
            continue
          print('Duplicate entry for %s %s (%s)' % (libName, lib['version'], refKey))
        entry = {}

        entry['sha'] = r['sha']
        entry['path'] = lib['path']
        entry['version'] = lib['version']
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
