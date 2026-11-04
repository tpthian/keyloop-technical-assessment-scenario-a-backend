"""AC-14 / TC-14: the layer dependency rule of design §4 (D-041), enforced on every commit.

domain -> standard library only; application -> domain; infrastructure -> application + domain;
interfaces -> application + domain; only ``scheduler.main`` may import both infrastructure and
interfaces. Third-party packages are allowed outside ``domain`` and ``application``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "scheduler"
PACKAGE = "scheduler"
STDLIB = set(sys.stdlib_module_names)

# layer -> internal layers it may import (itself is always allowed)
ALLOWED_INTERNAL: dict[str, set[str]] = {
    "domain": set(),
    "application": {"domain"},
    "infrastructure": {"application", "domain"},
    "interfaces": {"application", "domain"},
}
# layers that may import third-party packages
THIRD_PARTY_ALLOWED = {"infrastructure", "interfaces"}


def _layer_of(path: Path) -> str:
    rel = path.relative_to(SRC)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem  # top-level module -> its own name


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _layer_of_in(path: Path, src: Path) -> str:
    rel = path.relative_to(src)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _violations(src: Path = SRC) -> list[str]:
    found: list[str] = []
    for path in sorted(src.rglob("*.py")):
        layer = _layer_of_in(path, src)
        if layer not in ALLOWED_INTERNAL:
            continue  # main.py, settings.py and the package root are the composition root
        for name in _imports(path):
            root = name.split(".")[0]
            if root == PACKAGE:
                parts = name.split(".")
                target = parts[1] if len(parts) > 1 else PACKAGE
                if target != layer and target not in ALLOWED_INTERNAL[layer]:
                    found.append(f"{path.relative_to(src)}: {layer} -> {name}")
            elif root not in STDLIB and layer not in THIRD_PARTY_ALLOWED:
                found.append(f"{path.relative_to(src)}: {layer} -> third-party {name}")
    return found


def _both_outer_layers(src: Path = SRC) -> list[str]:
    """Modules other than the composition root ``src/main.py`` importing both outer layers."""
    found: list[str] = []
    composition_root = src / "main.py"
    for path in sorted(src.rglob("*.py")):
        if path == composition_root:
            continue
        names = _imports(path)
        if any(n.startswith("scheduler.infrastructure") for n in names) and any(
            n.startswith("scheduler.interfaces") for n in names
        ):
            found.append(str(path.relative_to(src)))
    return found


def test_layer_dependency_rule() -> None:
    assert _violations() == []


def test_only_main_imports_both_outer_layers() -> None:
    assert _both_outer_layers() == []


def test_rules_catch_violations(tmp_path: Path) -> None:
    """Regression probe: the checks reject what AC-14 forbids, including a nested main.py."""
    src = tmp_path / "scheduler"
    (src / "domain").mkdir(parents=True)
    (src / "application").mkdir()
    (src / "nested").mkdir()
    (src / "domain" / "bad.py").write_text("import fastapi\n")
    (src / "application" / "bad.py").write_text("from scheduler.infrastructure import x\n")
    (src / "nested" / "main.py").write_text(
        "import scheduler.infrastructure\nimport scheduler.interfaces\n"
    )
    (src / "main.py").write_text("import scheduler.infrastructure\nimport scheduler.interfaces\n")
    assert _violations(src) == [
        "application/bad.py: application -> scheduler.infrastructure",
        "domain/bad.py: domain -> third-party fastapi",
    ]
    assert _both_outer_layers(src) == ["nested/main.py"]
