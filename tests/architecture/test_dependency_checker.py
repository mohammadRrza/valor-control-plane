from pathlib import Path

import pytest

from tests.architecture.dependency_checker import find_violations


def write_module(source_root: Path, module_path: str, content: str) -> None:
    path = source_root.joinpath(*module_path.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "prohibited_import", "expected_layer"),
    [
        (
            "valor.some_context.domain.policy",
            "from valor.some_context.infrastructure import models",
            "domain",
        ),
        (
            "valor.some_context.application.register",
            "from valor.some_context.presentation import schemas",
            "application",
        ),
        (
            "valor.some_context.domain.policy",
            "from ..infrastructure import models",
            "domain",
        ),
        (
            "valor.some_context.domain.policy",
            "from .infrastructure.repository import Repository",
            "domain",
        ),
        (
            "valor.some_context.application.register",
            "from valor.some_context import presentation",
            "application",
        ),
    ],
)
def test_detects_nested_and_relative_violations(
    tmp_path: Path,
    source: str,
    prohibited_import: str,
    expected_layer: str,
) -> None:
    write_module(tmp_path, source, prohibited_import)
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0].source_module == source
    assert violations[0].layer == expected_layer
    assert "must not import" in violations[0].describe()


def test_accepts_valid_nested_dependencies(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "valor.some_context.application.register",
        "from ..domain.policy import Policy\n",
    )
    write_module(
        tmp_path, "valor.some_context.domain.policy", "from dataclasses import dataclass\n"
    )
    assert find_violations(tmp_path) == []
