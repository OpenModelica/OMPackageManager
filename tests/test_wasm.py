import os
import tempfile
import unittest

from ompackagemanager.buildwasm import ext_wrappers, file_key, group_units, make_words, sha256_file, write_zip
from ompackagemanager.genindex import wasmEntry


class TestWasmEntry(unittest.TestCase):
    def test_keyed_by_abi(self):
        wasm = {"abi": 1, "zipfile": "https://example.org/wasm/1/ab.zip", "sha256": "ab",
                "systemLibraries": ["cpython"], "source": "0123"}

        self.assertDictEqual(wasmEntry(wasm), {"1": {"zipfile": "https://example.org/wasm/1/ab.zip", "sha256": "ab",
                                                     "systemLibraries": ["cpython"]}})

    def test_nothing_to_install(self):
        self.assertIsNone(wasmEntry({"abi": 1, "source": "0123"}))
        self.assertIsNone(wasmEntry(None))


class TestWriteZip(unittest.TestCase):
    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            os.makedirs(os.path.join(src, "omc-include"))
            with open(os.path.join(src, "omc-externals.json"), "w") as f:
                f.write("{}\n")
            with open(os.path.join(src, "omc-include", "a.wasm"), "wb") as f:
                f.write(b"\0asm")
            write_zip(src, os.path.join(d, "1.zip"))
            os.utime(os.path.join(src, "omc-externals.json"), (0, 0))
            write_zip(src, os.path.join(d, "2.zip"))

            self.assertEqual(sha256_file(os.path.join(d, "1.zip")), sha256_file(os.path.join(d, "2.zip")))


class TestMakeWords(unittest.TestCase):
    def test_escaped_spaces_and_continuations(self):
        rule = "deps.o: deps.c /lib/Buildings\\ 12.1.0/x.h\\\n  /usr/include/stdio.h\n"

        self.assertListEqual(make_words(rule),
                             ["deps.o:", "deps.c", "/lib/Buildings 12.1.0/x.h", "/usr/include/stdio.h"])


class TestFileKey(unittest.TestCase):
    def test_relative_to_the_root_it_is_under(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.realpath(d)
            self.assertEqual(file_key(os.path.join(root, "C-Sources", "x.c"), ["/elsewhere", root]),
                             os.path.join("C-Sources", "x.c"))
            self.assertEqual(file_key("/usr/include/stdio.h", [root]), "stdio.h")


class TestExtWrappers(unittest.TestCase):
    def test_call_and_address_wrappers(self):
        f = {"name": "f", "returns": "double", "parameters": ["void*", "const char*"], "declare": True}
        self.assertEqual(ext_wrappers([f]),
                         "extern double f(void*, const char*);\n"
                         "double omc_ext_call_f(void* a0, const char* a1) { return f(a0, a1); }\n"
                         "#ifndef f\n"
                         "void (*omc_ext_addr_f(void))(void) { return (void (*)(void)) f; }\n"
                         "#endif\n")

    def test_no_c_spelling_gets_only_the_address(self):
        f = {"name": "g", "returns": None, "parameters": None}
        self.assertEqual(ext_wrappers([f]), "void (*omc_ext_addr_g(void))(void) { return (void (*)(void)) g; }\n")

    def test_void_and_no_parameters(self):
        f = {"name": "h", "returns": "void", "parameters": []}
        self.assertIn("void omc_ext_call_h(void) { h(); }", ext_wrappers([f]))


class TestGroupUnits(unittest.TestCase):
    def test_units_sharing_a_library_file_share_a_group(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.realpath(d)
            def unit(inc, deps): return {"includes": [inc], "includeDirectories": [root], "deps": deps}
            units = [unit("a", [os.path.join(root, "x.h")]), unit("b", ["/usr/include/stdio.h"]),
                     unit("c", [os.path.join(root, "x.h"), "/usr/include/stdio.h"])]
            self.assertEqual(sorted(group_units(units)), [[0, 2], [1]])


if __name__ == "__main__":
    unittest.main()
