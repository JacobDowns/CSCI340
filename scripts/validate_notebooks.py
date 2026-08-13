"""Check Python-cell syntax in computational notebooks."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
PYTHON_BLOCK = re.compile(r"```\{python\}\s*\n(.*?)\n```", re.DOTALL)


def cells(path: Path) -> list[str]:
    return PYTHON_BLOCK.findall(path.read_text(encoding="utf-8"))


def main() -> None:
    total = 0
    for path in sorted(NOTEBOOKS.glob("*.qmd")):
        notebook_cells = cells(path)
        for number, source in enumerate(notebook_cells, start=1):
            ast.parse(source, filename=f"{path.name}:cell-{number}")
        if notebook_cells:
            print(f"SYNTAX_OK {path.name}: {len(notebook_cells)} Python cells")
        total += len(notebook_cells)

    print(f"Validated {total} Python cells.")


if __name__ == "__main__":
    main()
