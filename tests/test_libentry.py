import unittest
import json
import os
from pathlib import Path
import shutil
import pygit2
import OMPython

from ompackagemanager.updateinfo import new_libentry, getgitrepo


class TestNewLibentry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clone git repositories, start OMC session."""

        def checkout_repo(github_repo: str, refname: str) -> str:
            """Clone and checkout a git repository from GitHub"""
            giturl = "https://github.com/%s.git" % github_repo
            repopath = os.path.join(cls.cache_dir, github_repo.split("/")[-1])

            if not os.path.exists(repopath):
                pygit2.clone_repository(giturl, repopath)
            gitrepo = pygit2.Repository(repopath)

            if refname.startswith("refs/"):
                gitrepo.checkout(
                    gitrepo.lookup_reference(refname),
                    strategy=pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)
            else:
                gitrepo.checkout_tree(
                    gitrepo.get(refname),
                    strategy=pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)

            return os.path.normpath(os.path.join(gitrepo.path, os.pardir))

        cls.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp-cache")
        os.makedirs(cls.cache_dir, exist_ok=True)

        cls.omc = OMPython.OMCSessionZMQ()
        cls.omc.sendExpression('setCommandLineOptions("--std=latest")')

        cls.aixlib_path = checkout_repo("RWTH-EBC/AixLib", "refs/tags/v2.1.1")
        cls.msl_path = checkout_repo("modelica/ModelicaStandardLibrary", "478538e43d3c9f682b2a6fb667783e2b3760f9f3")

    @classmethod
    def tearDownClass(cls):
        """Remove git repositories, stop OMC session."""
        cls.omc.sendExpression("exit")
        shutil.rmtree(cls.cache_dir)

    def tearDown(self):
        """Clear omc session"""
        self.omc.sendExpression('clear()')

    def test_aixlib_tag_version(self):
        """Test libentry for AixLib v2.1.1"""

        libname = "AixLib"
        tagName = "v2.1.1"
        entry = json.loads(
            """
            {
                "names": ["AixLib"],
                "github": "RWTH-EBC/AixLib",
                "branches": {"development": "development", "main": "main"},
                "ignore-tags": ["v0.7.2", "v0.7.1", "v0.7.0", "v0.1.0"],
                "support": [
                ["prerelease", "noSupport"],
                [">=1.3.1", "support"],
                [">=0.9.1", "experimental"],
                ["*", "obsolete"]
                ]
            }
            """)

        # Load package.mo
        repopath = self.aixlib_path
        hits = [os.path.join(repopath, "AixLib", "package.mo")]
        self.omc.sendExpression('loadFile("%s", uses=false)' % hits[0])

        libentry = new_libentry(
            libname=libname,
            tagName=tagName,
            entry=entry,
            hits=hits,
            repopath=repopath,
            omc=self.omc
        )

        expected_libentry = {
            "version": "2.1.1",
            "path": "AixLib",
            "uses": {
                "Modelica": "4.0.0",
                "Modelica_DeviceDrivers": "2.1.1",
                "SDF": "0.4.2"
            },
            "convertFromVersion": [
                "2.1.0"
            ],
        }
        self.assertDictEqual(libentry, expected_libentry)

    def test_modelica_master_version(self):
        """Test libentry for Modelica master"""

        libname = "Modelica"
        branch = "master"
        entry = json.loads(
            """
            {
                "names": ["Modelica","ModelicaReference","ModelicaServices","ModelicaTest","ModelicaTestOverdetermined","Complex","ObsoleteModelica3","ObsoleteModelica4"],
                "github": "modelica/ModelicaStandardLibrary",
                "branches": {
                    "master": "master"
                },
                "standard": [
                    [">=3.4.0", "latest"],
                    ["*", "latest"]
                ],
                "support": [
                    [">=3.2.3", "fullSupport"],
                    ["*", "obsolete"]
                ]
            }
            """)

        # Load package.mo
        repopath = self.msl_path
        hits = [os.path.join(repopath, "Modelica", "package.mo")]
        self.omc.sendExpression('clear()')
        self.omc.sendExpression('loadFile("%s", uses=false)' % hits[0])

        libentry = new_libentry(
            libname=libname,
            tagName=branch,
            entry=entry,
            hits=hits,
            repopath=repopath,
            omc=self.omc
        )

        expected_libentry = {
            "version": "4.2.0-dev",
            "path": "Modelica",
            "uses": {
                "Complex": "4.2.0-dev",
                "ModelicaServices": "4.2.0-dev"
            },
            "provides": [
                "4.0.0",
                "4.1.0"
            ],
            "convertFromVersion": [
                "3.0.0",
                "3.0.1",
                "3.1.0",
                "3.2.0",
                "3.2.1",
                "3.2.2",
                "3.2.3"
            ]
        }
        self.assertDictEqual(libentry, expected_libentry)


if __name__ == "__main__":
    unittest.main()
