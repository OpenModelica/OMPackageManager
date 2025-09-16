import concurrent.futures
import datetime
import itertools
import json
import os
import requests


def filename(url, destination):
    if url.startswith("https://"):
        return os.path.join(destination, url.removeprefix("https://"))
    raise Exception(url)


def main(destination: str, clean: bool):
    """Cache indexed libraries in directory `destination`

    Args:
        destination (str): Directory to store cached libraries in.
        clean (bool): If `True` unlink files that are older than 90 days.
    """

    urls = set()
    for index in [
        json.loads(
            requests.get(
                "https://raw.githubusercontent.com/OpenModelica/OpenModelica/%s/libraries/%s" %
                branch_file).content) for branch_file in itertools.product(
                    [
                        "master", "maintenance/v1.20"], [
                            "index.json", "install-index.json"])] + [
                                json.load(
                                    open("index.json"))]:
        for lib in index["libs"].values():
            for version in lib["versions"].values():
                url = version["zipfile"]
                if url.startswith("https://build.openmodelica.org"):
                    continue
                if url.startswith("https://"):
                    fname = filename(url, destination)
                    if not os.path.exists(fname):
                        urls.add(url)
                    else:
                        os.utime(filename(url, destination), None)
                    try:
                        os.makedirs(os.path.dirname(fname))
                    except FileExistsError:
                        pass

    def download_url(url):
        response = requests.get(url)
        fname = filename(url, destination)
        try:
            with open(fname, "wb") as fout:
                fout.write(response.content)
        except BaseException:
            try:
                os.unlink(fname)
            except BaseException:
                pass
            raise

    with concurrent.futures.ThreadPoolExecutor() as exector:
        for res in exector.map(download_url, urls):
            pass

    today = datetime.datetime.today()
    if clean:
        for root, dir, files in os.walk(destination):
            for file in files:
                fname = os.path.join(root, file)
                modified_date = datetime.datetime.fromtimestamp(
                    os.path.getmtime(fname))
                duration = today - modified_date
                if duration.days > 90:
                    os.unlink(fname)
