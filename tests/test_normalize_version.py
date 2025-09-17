import unittest
from ompackagemanager.updateinfo import normalize_version


class TestVersionNormalization(unittest.TestCase):

    def test_master_dev_version(self):
        """Test version on master branch"""
        version = "1.2.3"
        tagName = "master"
        entry = dict()

        normalized_version = normalize_version(
            version=version, tagName=tagName, entry=entry)
        self.assertEqual(normalized_version, "1.2.3-master")

    @unittest.expectedFailure
    def test_master_w_build_dev_version(self):
        """Test version with build on master branch"""
        version = "1.2.3 build"
        tagName = "master"
        entry = dict()

        normalized_version = normalize_version(
            version=version, tagName=tagName, entry=entry)
        self.assertEqual(normalized_version, "1.2.3-build")

    def test_empty_tag(self):
        """Test version with build without tag name"""
        version = "1.2.3 build"
        tagName = ""
        entry = dict()

        normalized_version = normalize_version(
            version=version, tagName=tagName, entry=entry)
        self.assertEqual(normalized_version, "1.2.3-build")


if __name__ == "__main__":
    unittest.main()
