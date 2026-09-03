from pathlib import Path

from tests.architecture.dependency_checker import find_violations, imports_in

SOURCE = Path(__file__).parents[2] / "src"


def test_repository_dependency_boundaries() -> None:
    violations = find_violations(SOURCE)
    assert not violations, "Architecture violations:\n" + "\n".join(
        violation.describe() for violation in violations
    )


def test_ai_asset_registry_does_not_import_identity_tenancy_internals() -> None:
    context = SOURCE / "valor" / "ai_asset_registry"
    violations: list[str] = []
    for layer in ("domain", "application"):
        for path in (context / layer).rglob("*.py"):
            for imported_module, line in imports_in(SOURCE, path):
                if imported_module.startswith("valor.identity_tenancy"):
                    violations.append(
                        f"{path.relative_to(SOURCE)}:{line} imports {imported_module}"
                    )
    assert not violations, "Cross-context internal imports:\n" + "\n".join(violations)


def test_runtime_gateway_core_does_not_import_owning_context_internals() -> None:
    context = SOURCE / "valor" / "runtime_gateway"
    forbidden = ("valor.ai_asset_registry", "valor.identity_tenancy")
    violations: list[str] = []
    for layer in ("domain", "application"):
        for path in (context / layer).rglob("*.py"):
            for imported_module, line in imports_in(SOURCE, path):
                if imported_module.startswith(forbidden):
                    violations.append(
                        f"{path.relative_to(SOURCE)}:{line} imports {imported_module}"
                    )
    assert not violations, "Cross-context internal imports:\n" + "\n".join(violations)


def test_policy_risk_core_does_not_import_other_context_internals() -> None:
    context = SOURCE / "valor" / "policy_risk"
    forbidden = (
        "valor.ai_asset_registry",
        "valor.identity_tenancy",
        "valor.runtime_gateway",
    )
    violations: list[str] = []
    for layer in ("domain", "application"):
        for path in (context / layer).rglob("*.py"):
            for imported_module, line in imports_in(SOURCE, path):
                if imported_module.startswith(forbidden):
                    violations.append(
                        f"{path.relative_to(SOURCE)}:{line} imports {imported_module}"
                    )
    assert not violations, "Cross-context internal imports:\n" + "\n".join(violations)
