"""Check Python-cell syntax in computational notebooks."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
PYTHON_BLOCK = re.compile(r"```\{python\}\s*\n(.*?)\n```", re.DOTALL)


def qmd_cells(path: Path) -> list[str]:
    return PYTHON_BLOCK.findall(path.read_text(encoding="utf-8"))


def ipynb_cells(path: Path) -> list[str]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return [
        "".join(cell.get("source", []))
        if isinstance(cell.get("source", []), list)
        else cell.get("source", "")
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def main() -> None:
    total = 0
    notebook_paths = sorted(NOTEBOOKS.glob("*.qmd")) + sorted(NOTEBOOKS.glob("*.ipynb"))
    for path in notebook_paths:
        notebook_cells = qmd_cells(path) if path.suffix == ".qmd" else ipynb_cells(path)
        for number, source in enumerate(notebook_cells, start=1):
            ast.parse(source, filename=f"{path.name}:cell-{number}")
        if notebook_cells:
            print(f"SYNTAX_OK {path.name}: {len(notebook_cells)} Python cells")
        total += len(notebook_cells)

    print(f"Validated {total} Python cells.")


if __name__ == "__main__":
    main()
