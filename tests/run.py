"""Tests offline (sin framework): python -m tests.run"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

TESTS_DIR = Path(__file__).resolve().parent


def load():
    suite = unittest.TestSuite()
    for f in sorted(TESTS_DIR.glob("test_*.py")):
        mod = __import__(f"tests.{f.stem}", fromlist=["*"])
        for name in dir(mod):
            if name.startswith("test_"):
                suite.addTest(unittest.FunctionTestCase(getattr(mod, name)))
    return suite


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(load())
    sys.exit(0 if result.wasSuccessful() else 1)
