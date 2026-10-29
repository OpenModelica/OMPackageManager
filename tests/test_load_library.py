import unittest

import OMPython

from ompackagemanager.updateinfo import load_library


class FakeOMC:
    def __init__(self, loadResult=True, classNames=None, loadError=None):
        self.loadResult = loadResult
        self.classNames = classNames if classNames is not None else []
        self.loadError = loadError

    def sendExpression(self, expr):
        if expr.startswith("loadFile("):
            if self.loadError:
                raise OMPython.OMCSessionException(self.loadError)
            return self.loadResult
        if expr == "getClassNames()":
            return self.classNames
        raise AssertionError("unexpected expression " + expr)


class TestLoadLibrary(unittest.TestCase):
    def test_loaded(self):
        omc = FakeOMC(classNames=["LEPSE"])
        self.assertTrue(load_library("LEPSE", "main", "cache/LEPSE/package.mo", omc))

    def test_load_returns_false(self):
        omc = FakeOMC(loadResult=False)
        self.assertFalse(load_library("LEPSE", "main", "cache/LEPSE/package.mo", omc))

    def test_load_raises(self):
        # OMPython 4 raises for an error in the omc log instead of returning False
        omc = FakeOMC(loadError="[scripting:error:236] Expected the package to have name Co-simulation, "
                                "but got Co_simulation.")
        self.assertFalse(load_library("LEPSE", "main", "cache/LEPSE/package.mo", omc))

    def test_library_not_among_loaded_classes(self):
        omc = FakeOMC(classNames=["Other"])
        self.assertFalse(load_library("LEPSE", "main", "cache/LEPSE/package.mo", omc))


if __name__ == "__main__":
    unittest.main()
