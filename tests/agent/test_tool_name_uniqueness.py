from __future__ import annotations

import ast
from pathlib import Path


def _tool_name_from_class(node: ast.ClassDef) -> str | None:
    # 1) class attribute: name = "..."
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "name"
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    return stmt.value.value
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "name"
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            return stmt.value.value

    # 2) property method:
    #    @property
    #    def name(self): return "..."
    for stmt in node.body:
        if not isinstance(stmt, ast.FunctionDef) or stmt.name != "name":
            continue
        is_property = any(isinstance(dec, ast.Name) and dec.id == "property" for dec in stmt.decorator_list)
        if not is_property:
            continue
        for body_stmt in stmt.body:
            if (
                isinstance(body_stmt, ast.Return)
                and isinstance(body_stmt.value, ast.Constant)
                and isinstance(body_stmt.value.value, str)
            ):
                return body_stmt.value.value

    return None


def test_tool_names_are_unique_and_resolvable():
    tools_root = Path("kabot/agent/tools")
    seen: dict[str, list[str]] = {}
    unresolved: list[str] = []

    for py_file in sorted(tools_root.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            if "Tool" not in bases:
                continue

            tool_name = _tool_name_from_class(node)
            ref = f"{py_file}:{node.name}"
            if not tool_name:
                unresolved.append(ref)
                continue
            seen.setdefault(tool_name, []).append(ref)

    duplicates = {name: refs for name, refs in seen.items() if len(refs) > 1}

    assert not unresolved, f"Unresolved tool names: {unresolved}"
    assert not duplicates, f"Duplicate tool.name detected: {duplicates}"

