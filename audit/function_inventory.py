"""Strumento di inventario per le funzioni Python della repo FAIR-III.

*Obiettivo*: produrre un elenco strutturato di tutte le ``def`` presenti nei
moduli così da monitorare la copertura dei test e pianificare i commenti in
italiano richiesti dalla roadmap.
*Uso*: eseguire ``python -m audit.function_inventory`` per generare il file
``audit/function_inventory.json`` con i metadati rilevanti.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

# Radice del progetto (cartella che contiene pyproject.toml)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Cartelle da analizzare per estrarre le funzioni: codice applicativo e test.
SOURCE_ROOTS = (PROJECT_ROOT / "fair3", PROJECT_ROOT / "tests")


@dataclass
class FunctionRecord:
    """Rappresenta una singola funzione o metodo individuato nel codice."""

    percorso: str
    qualifica: str
    tipo: str
    linea: int
    argomenti: list[str]
    ha_docstring: bool


def _iter_functions(path: Path) -> Iterator[FunctionRecord]:
    """Visita ricorsivamente il modulo e raccoglie tutte le definizioni."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:  # pragma: no cover - file non UTF-8
        raise RuntimeError(f"File non in UTF-8: {path}") from exc

    stack: list[str] = []
    records: list[FunctionRecord] = []

    class Visitor(ast.NodeVisitor):
        """Visitor AST che tiene traccia del contesto (moduli/classi)."""

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            record = FunctionRecord(
                percorso=str(path.relative_to(PROJECT_ROOT)),
                qualifica=".".join(stack + [node.name]),
                tipo="async" if isinstance(node, ast.AsyncFunctionDef) else "sync",
                linea=node.lineno,
                argomenti=[arg.arg for arg in node.args.args],
                ha_docstring=ast.get_docstring(node) is not None,
            )
            records.append(record)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

    Visitor().visit(tree)
    return iter(records)


def _walk_python_files() -> Iterable[Path]:
    """Scorre tutte le ``.py`` rilevanti per l'inventario."""

    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        yield from sorted(root.rglob("*.py"))


def build_inventory() -> list[FunctionRecord]:
    """Restituisce l'inventario completo come lista di ``FunctionRecord``."""

    inventory: list[FunctionRecord] = []
    for py_file in _walk_python_files():
        inventory.extend(_iter_functions(py_file))
    return inventory


def save_inventory(path: Path) -> None:
    """Salva l'inventario in formato JSON leggibile dal team QA."""

    inventory = [asdict(record) for record in build_inventory()]
    path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """Entry point CLI che scrive ``audit/function_inventory.json``."""

    destinazione = PROJECT_ROOT / "audit" / "function_inventory.json"
    save_inventory(destinazione)


if __name__ == "__main__":
    main()
