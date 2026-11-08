import unittest

from ompackagemanager.genindex import checkProvidesUses


def index(libs, anyVersion=()):
    data = {"libs": {name: {"versions": {v: dict(e, version=v) for (v, e) in versions.items()}}
                     for (name, versions) in libs.items()}}
    for name in anyVersion:
        data["libs"][name]["anyVersion"] = True
    return data


def versions(indexdata, lib):
    return indexdata["libs"][lib]["versions"]


class TestCheckProvidesUses(unittest.TestCase):
    def test_dependency_not_provided(self):
        data = index({
            "Modelica": {"3.2.3": {}, "4.0.0": {}},
            "ExternalMedia": {"3.3.2": {"provides": ["3.3.1"], "uses": {"Modelica": "3.2.3"}},
                              "4.0.0": {"provides": ["3.3.1", "3.3.2"], "uses": {"Modelica": "4.0.0"}}}})
        checkProvidesUses(data)
        em = versions(data, "ExternalMedia")["4.0.0"]
        self.assertListEqual(em["convertFromVersion"], ["3.3.2"])
        self.assertListEqual(versions(data, "ExternalMedia")["3.3.2"]["provides"], ["3.3.1"])

    def test_unknown_old_version_is_kept(self):
        data = index({
            "Modelica": {"3.2.3": {}, "4.0.0": {}},
            "ExternalMedia": {"4.0.0": {"provides": ["3.3.1"], "uses": {"Modelica": "4.0.0"}}}})
        checkProvidesUses(data)
        self.assertListEqual(versions(data, "ExternalMedia")["4.0.0"]["provides"], ["3.3.1"])

    def test_dependency_provided(self):
        data = index({
            "Modelica": {"4.0.0+maint.om": {}, "4.1.0+maint.om": {"provides": ["4.0.0"]}},
            "Buildings": {"11.0.0": {"uses": {"Modelica": "4.0.0"}},
                          "11.1.0": {"provides": ["11.0.0"], "uses": {"Modelica": "4.1.0"}}}})
        checkProvidesUses(data)
        self.assertListEqual(versions(data, "Buildings")["11.1.0"]["provides"], ["11.0.0"])
        self.assertNotIn("convertFromVersion", versions(data, "Buildings")["11.1.0"])

    def test_newer_dependency_provides_both(self):
        data = index({
            "Modelica": {"3.2.1": {}, "3.2.2": {}, "3.2.3": {"provides": ["3.2.1", "3.2.2"]}},
            "L": {"2.3.1": {"uses": {"Modelica": "3.2.1"}},
                  "2.3.4": {"provides": ["2.3.1"], "uses": {"Modelica": "3.2.2"}}}})
        checkProvidesUses(data)
        self.assertListEqual(versions(data, "L")["2.3.4"]["provides"], ["2.3.1"])

    def test_only_the_broken_version_is_moved(self):
        data = index({
            "Modelica": {"3.2.3": {}, "4.0.0": {}},
            "L": {"1.0.0": {"uses": {"Modelica": "3.2.3"}},
                  "2.0.0": {"uses": {"Modelica": "4.0.0"}},
                  "2.1.0": {"provides": ["1.0.0", "2.0.0"], "uses": {"Modelica": "4.0.0"},
                            "convertFromVersion": ["0.9.0"]}}})
        checkProvidesUses(data)
        lib = versions(data, "L")["2.1.0"]
        self.assertListEqual(lib["provides"], ["2.0.0"])
        self.assertListEqual(lib["convertFromVersion"], ["0.9.0", "1.0.0"])

    def libsUsingDymolaCommands(self, anyVersion):
        data = index({
            "DymolaCommands": {"master": {"provides": ["1.0.0"]}},
            "LinearSystems": {"3.0.0": {"uses": {"DymolaCommands": "1.17.0"}},
                              "3.0.1": {"provides": ["3.0.0"], "uses": {"DymolaCommands": "1.20.0"}}}
        }, anyVersion)
        checkProvidesUses(data)
        return versions(data, "LinearSystems")["3.0.1"]

    def test_any_version_dependency(self):
        self.assertListEqual(self.libsUsingDymolaCommands(["DymolaCommands"])["provides"], ["3.0.0"])

    def test_unknown_dependency_version(self):
        self.assertListEqual(self.libsUsingDymolaCommands([])["convertFromVersion"], ["3.0.0"])

    def test_dependency_not_in_index(self):
        data = index({"L": {"1.0.0": {"uses": {"X": "1.0.0"}},
                            "1.1.0": {"provides": ["1.0.0"], "uses": {"X": "2.0.0"}},
                            "1.2.0": {"provides": ["1.1.0"], "uses": {"X": "2.0.0"}}}})
        checkProvidesUses(data)
        self.assertNotIn("provides", versions(data, "L")["1.1.0"])
        self.assertListEqual(versions(data, "L")["1.2.0"]["provides"], ["1.1.0"])

    def test_dependency_dropped_or_added(self):
        data = index({
            "A": {"1.0.0": {}, "2.0.0": {}},
            "B": {"1.0.0": {}},
            "L": {"1.0.0": {"uses": {"A": "1.0.0"}},
                  "1.1.0": {"provides": ["1.0.0"], "uses": {"B": "1.0.0"}}}})
        checkProvidesUses(data)
        self.assertListEqual(versions(data, "L")["1.1.0"]["provides"], ["1.0.0"])

    def test_transitive(self):
        data = index({
            "A": {"1.0.0": {"uses": {"B": "1.0.0"}},
                  "1.1.0": {"provides": ["1.0.0"], "uses": {"B": "1.1.0"}}},
            "B": {"1.0.0": {"uses": {"C": "1.0.0"}},
                  "1.1.0": {"provides": ["1.0.0"], "uses": {"C": "2.0.0"}}},
            "C": {"1.0.0": {}, "2.0.0": {}}})
        checkProvidesUses(data)
        self.assertNotIn("provides", versions(data, "B")["1.1.0"])
        self.assertNotIn("provides", versions(data, "A")["1.1.0"])
        self.assertListEqual(versions(data, "A")["1.1.0"]["convertFromVersion"], ["1.0.0"])

    def test_branch_alias_is_the_same_entry(self):
        data = index({
            "Modelica": {"3.2.3": {}, "4.0.0": {}},
            "L": {"1.0.0": {"uses": {"Modelica": "3.2.3"}},
                  "2.0.0-dev": {"provides": ["1.0.0"], "uses": {"Modelica": "4.0.0"}}}})
        versions(data, "L")["master"] = versions(data, "L")["2.0.0-dev"]
        checkProvidesUses(data)
        self.assertNotIn("provides", versions(data, "L")["master"])
        self.assertListEqual(versions(data, "L")["master"]["convertFromVersion"], ["1.0.0"])


if __name__ == "__main__":
    unittest.main()
