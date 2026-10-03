import sys
from pathlib import Path

# Garante que os testes encontrem os módulos em src/ sem precisar de instalação.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
