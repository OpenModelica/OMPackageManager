import unittest

from ompackagemanager.genindex import mergeProvides


class TestMergeProvides(unittest.TestCase):
    def test_merges_and_sorts(self):
        self.assertListEqual(mergeProvides(["1.1.0"], ["1.0.0", "1.2.0"]),
                             ["1.0.0", "1.1.0", "1.2.0"])

    def test_no_conversion_annotation(self):
        self.assertListEqual(mergeProvides([], ["0.4.0", "0.4.1"]), ["0.4.0", "0.4.1"])

    def test_duplicates_are_dropped(self):
        self.assertListEqual(mergeProvides(["1.0.0", "1.1.0"], ["1.0.0"]), ["1.0.0", "1.1.0"])

    def test_sorted_by_version_not_string(self):
        self.assertListEqual(mergeProvides([], ["1.10.0", "1.9.0"]), ["1.9.0", "1.10.0"])

    def test_versions_are_normalized(self):
        self.assertListEqual(mergeProvides([], ["1.0", "v2"]), ["1.0.0", "2.0.0"])


if __name__ == "__main__":
    unittest.main()
