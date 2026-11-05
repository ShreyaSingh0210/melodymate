# conftest.py
# Adds the project root to sys.path so that `from core.xxx import ...`
# works in every test file without needing an installed package.

import sys
import pathlib

# Insert project root (the directory this file lives in) at the front
sys.path.insert(0, str(pathlib.Path(__file__).parent))
