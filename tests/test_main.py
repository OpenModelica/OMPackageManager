import unittest
from io import StringIO
from pathlib import Path
import sys

from ompackagemanager import __main__


class TestCaseBase(unittest.TestCase):
    def assertIsFile(self, path: Path):
        if not Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))


class TestCLI(TestCaseBase):
    def setUp(self) -> None:
        """Remove index.json"""
        self.index_file = Path(__file__).parents[1].joinpath("index.json")
        if self.index_file.is_file():
            self.index_file.unlink()

    def tearDown(self):
        """Remove index.json"""
        if self.index_file.is_file():
            self.index_file.unlink()

    def test_run_check_missing(self) -> None:
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out

            __main__.main(["check-missing"])

            out_string = out.getvalue()
            self.assertIn('modelica-3rdparty/BuildSysPro', out_string)
            self.assertIn('modelica-3rdparty/electrolytemedia', out_string)
            self.assertIn('modelica-3rdparty/ExternalMedia', out_string)
            self.assertIn('modelica-3rdparty/FluidSystemComponents', out_string)
            self.assertIn('modelica-3rdparty/Greenhouses-Library', out_string)
            self.assertIn('modelica-3rdparty/HeatTransferComponents', out_string)
            self.assertIn('modelica-3rdparty/LCC_HVDC', out_string)
            self.assertIn('modelica-3rdparty/MoSDH', out_string)
            self.assertIn('modelica-3rdparty/NeuralNetwork', out_string)
            self.assertIn('modelica-3rdparty/OpenHydraulics', out_string)
            self.assertIn('modelica-3rdparty/ShipSIM', out_string)
            self.assertIn('modelica-3rdparty/SMEHV', out_string)
            self.assertIn('modelica-3rdparty/ThermoSysPro', out_string)

        finally:
            sys.stdout = saved_stdout

    def test_run_genindex(self) -> None:
        __main__.main(["genindex"])

        self.assertIsFile(self.index_file)


if __name__ == "__main__":
    unittest.main()
