# tests/conftest.py
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))