import sys
import importlib.abc
import importlib.util
from pathlib import Path

class SourcelessPycFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not path:
            return None
        name = fullname.split(".")[-1]
        for p in path:
            py = Path(p) / f"{name}.py"
            pyc = Path(p) / "__pycache__" / f"{name}.cpython-313.pyc"
            if not py.is_file() and pyc.is_file():
                return importlib.util.spec_from_file_location(fullname, pyc)
        return None

if not any(isinstance(f, SourcelessPycFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, SourcelessPycFinder())
