import unittest
from io import StringIO
import sys

from ompackagemanager import __main__


class TestCLI(unittest.TestCase):
    def test_run_check_missing(self):
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out

            __main__.main(["check-missing"])

            self.assertIn('''modelica-3rdparty/BuildSysPro
modelica-3rdparty/electrolytemedia
modelica-3rdparty/ExternalMedia
modelica-3rdparty/FluidSystemComponents
modelica-3rdparty/Greenhouses-Library
modelica-3rdparty/HeatTransferComponents
modelica-3rdparty/LCC_HVDC
modelica-3rdparty/MoSDH
modelica-3rdparty/NeuralNetwork
modelica-3rdparty/OpenHydraulics
modelica-3rdparty/ShipSIM
modelica-3rdparty/SMEHV
modelica-3rdparty/urdfmodelica
''', out.getvalue())
        finally:
            sys.stdout = saved_stdout


if __name__ == "__main__":
    unittest.main()
