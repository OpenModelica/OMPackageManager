#!/usr/bin/env python3

import argparse
import concurrent.futures
import datetime
import json
import os
import requests

parser = argparse.ArgumentParser(
                    prog = 'OpenModelica Library Cache',
                    description = 'Cache indexed libraries')

parser.add_argument('destination')
parser.add_argument('--clean', action='store_true')
args = parser.parse_args()

def filename(url):
    if url.startswith("https://"):
        return os.path.join(args.destination, url.removeprefix("https://"))
    raise Exception(url)


urls = set()
for index in [json.loads(requests.get("https://raw.githubusercontent.com/OpenModelica/OpenModelica/master/libraries/index.json").content) for branch in ["master", "maintenance/v1.20"]] + [json.load(open("index.json"))]:
    for lib in index["libs"].values():
        for version in lib["versions"].values():
            url = version["zipfile"]
            if url.startswith("https://build.openmodelica.org"):
                continue
            if url.startswith("https://"):
                fname = filename(url)
                if not os.path.exists(fname):
                    urls.add(url)
                else:
                    os.utime(filename(url), None)
                try:
                    os.makedirs(os.path.dirname(fname))
                except FileExistsError:
                    pass

def download_url(url):
    response = requests.get(url)
    fname = filename(url)
    try:
        with open(fname, "wb") as fout:
            fout.write(response.content)
    except:
        try:
            os.unlink(fname)
        except:
            pass
        raise

with concurrent.futures.ThreadPoolExecutor() as exector:
   for res in exector.map(download_url, urls):
       pass

today = datetime.datetime.today()
if args.clean:
    for root, dir, files in os.walk(args.destination):
        for file in files:
            fname = os.path.join(root, file)
            modified_date = datetime.datetime.fromtimestamp(os.path.getmtime(fname))
            duration = today - modified_date
            if duration.days > 90:
                os.unlink(fname)