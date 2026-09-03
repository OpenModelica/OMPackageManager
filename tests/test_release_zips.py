import unittest
from types import SimpleNamespace

from ompackagemanager.updateinfo import collect_release_zips


def release(tag, assets, draft=False):
    return SimpleNamespace(
        tag_name=tag,
        draft=draft,
        assets=[SimpleNamespace(name=name, browser_download_url="https://example.org/%s/%s" % (tag, name))
                for name in assets])


class Repo:
    full_name = "modelica-3rdparty/example"

    def __init__(self, releases):
        self.releases = releases

    def get_releases(self):
        return self.releases


class TestCollectReleaseZips(unittest.TestCase):
    def test_only_releases_with_a_zip_asset(self):
        repo = Repo([release("v0.2.0", ["MessagePack-0.2.0.zip"]),
                     release("v0.1", ["binaries.tar.gz", "msgpack-modelica-0.1.tar.gz"])])

        self.assertDictEqual(collect_release_zips(repo, "*.zip"),
                             {"v0.2.0": "https://example.org/v0.2.0/MessagePack-0.2.0.zip"})

    def test_drafts_are_ignored(self):
        repo = Repo([release("v2.0.0", ["Lib-2.0.0.zip"], draft=True)])

        self.assertDictEqual(collect_release_zips(repo, "*.zip"), {})

    def test_ambiguous_assets_raise(self):
        repo = Repo([release("v1.0.0", ["Lib-1.0.0.zip", "Lib-1.0.0-sources.zip"])])

        with self.assertRaises(Exception):
            collect_release_zips(repo, "*.zip")

    def test_pattern_disambiguates(self):
        repo = Repo([release("v1.0.0", ["Lib-1.0.0.zip", "Lib-1.0.0-sources.zip"])])

        self.assertDictEqual(collect_release_zips(repo, "Lib-*[0-9].zip"),
                             {"v1.0.0": "https://example.org/v1.0.0/Lib-1.0.0.zip"})


if __name__ == "__main__":
    unittest.main()
