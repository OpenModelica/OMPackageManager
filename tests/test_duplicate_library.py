import os
import tempfile
import unittest

from ompackagemanager.updateinfo import duplicate_library_warning, find_library_files


def touch(root, relpath):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("")


class TestDuplicateLibrary(unittest.TestCase):
    def setUp(self):
        # Layout of OpenModelica/CRML before CRMLtoModelica.mo was removed from the root
        self.tmp = tempfile.TemporaryDirectory()
        self.repopath = self.tmp.name
        touch(self.repopath, "CRMLtoModelica.mo")
        touch(self.repopath, "libraries/modelica/CRMLtoModelica.mo")
        touch(self.repopath, "libraries/modelica/CRML/package.mo")
        self.extraPaths = ["libraries/modelica"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_hit(self):
        hits = find_library_files(self.repopath, "CRML", self.extraPaths)
        self.assertEqual([os.path.relpath(h, self.repopath) for h in hits],
                         [os.path.join("libraries", "modelica", "CRML", "package.mo")])

    def test_duplicate_hits(self):
        hits = find_library_files(self.repopath, "CRMLtoModelica", self.extraPaths)
        self.assertEqual(len(hits), 2)
        warning = duplicate_library_warning("CRML", "CRMLtoModelica", "main", hits, self.repopath)
        self.assertIn("WARNING: library CRMLtoModelica of repos.json entry CRML is found 2 times in main", warning)
        self.assertIn("!!!   CRMLtoModelica.mo", warning)
        self.assertIn("!!!   " + os.path.join("libraries", "modelica", "CRMLtoModelica.mo"), warning)
        self.assertIn("CRMLtoModelica is SKIPPED", warning)

    def test_extra_path_only_searched_when_listed(self):
        hits = find_library_files(self.repopath, "CRMLtoModelica", None)
        self.assertEqual([os.path.relpath(h, self.repopath) for h in hits], ["CRMLtoModelica.mo"])


if __name__ == "__main__":
    unittest.main()
