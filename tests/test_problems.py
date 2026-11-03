import json
import os
import tempfile
import unittest

import OMPython

from ompackagemanager import common, genindex, updateinfo


class InTempDir(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()


class TestWriteProblems(InTempDir):
    def test_writes_list(self):
        common.write_problems("p.txt", "skipped:", ["A 1.0.0: broken", "B main: broken"])
        with open("p.txt") as f:
            self.assertEqual(f.read(), "skipped:\n\n- A 1.0.0: broken\n- B main: broken\n")

    def test_no_problems_removes_old_file(self):
        common.write_problems("p.txt", "skipped:", ["A 1.0.0: broken"])
        common.write_problems("p.txt", "skipped:", [])
        self.assertFalse(os.path.exists("p.txt"))


class TestGenindexSkipsRefWithoutLibs(InTempDir):
    def test_skipped_and_reported(self):
        # Issue #61: a ref without libraries (e.g. LEPSE v1.2.1) used to raise and stop the job
        repos = {"LEPSE": {"github": "example/LEPSE", "names": ["LEPSE"], "support": [["*", "support"]]}}
        rawdata = {"LEPSE": {"refs": {
            "v1.2.0": {"sha": "a" * 40, "libs": {"LEPSE": {"version": "1.2.0", "path": "LEPSE"}}},
            "v1.2.1": {"sha": "b" * 40}}}}
        with open("repos.json", "w") as f:
            json.dump(repos, f)
        with open("rawdata.json", "w") as f:
            json.dump(rawdata, f)
        genindex.main()
        with open("index.json") as f:
            index = json.load(f)
        self.assertEqual(list(index["libs"]["LEPSE"]["versions"]), ["1.2.0"])
        with open(genindex.PROBLEMS_FILE) as f:
            self.assertIn("- LEPSE v1.2.1 has no libraries in rawdata.json", f.read())


class FailingOMC:
    def sendExpression(self, expr):
        raise OMPython.OMCSessionException("[scripting:error:236] Expected the package to have name Co-simulation, "
                                           "but got Co_simulation.")


class TestUpdateinfoRecordsFailedLoads(unittest.TestCase):
    def setUp(self):
        updateinfo.failedLoads.clear()

    def tearDown(self):
        updateinfo.failedLoads.clear()

    def test_failed_load_recorded(self):
        self.assertFalse(updateinfo.load_library("LEPSE", "v1.2.1", "cache/LEPSE/package.mo", FailingOMC()))
        self.assertEqual(len(updateinfo.failedLoads), 1)
        path, tagName, error = updateinfo.failedLoads[0]
        self.assertEqual((path, tagName), ("cache/LEPSE/package.mo", "v1.2.1"))
        self.assertIn("Co_simulation", error)


if __name__ == "__main__":
    unittest.main()
