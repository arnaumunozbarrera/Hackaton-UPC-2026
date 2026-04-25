from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"

for path in (REPO_ROOT, BACKEND_PATH):
    path_value = str(path)
    if path_value not in sys.path:
        sys.path.insert(0, path_value)
