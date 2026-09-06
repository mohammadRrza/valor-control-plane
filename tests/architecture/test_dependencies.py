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


def test_business_context_cores_do_not_depend_on_security_transport() -> None:
    violations: list[str] = []
    for context_name in (
        "identity_tenancy",
        "ai_asset_registry",
        "runtime_gateway",
        "policy_risk",
        "management_audit",
        "management_identity",
    ):
        context = SOURCE / "valor" / context_name
        for layer in ("domain", "application"):
            for path in (context / layer).rglob("*.py"):
                for imported_module, line in imports_in(SOURCE, path):
                    if imported_module.startswith("valor.security.presentation"):
                        violations.append(
                            f"{path.relative_to(SOURCE)}:{line} imports {imported_module}"
                        )
    assert not violations, "Security transport imports in business core:\n" + "\n".join(violations)


def test_management_audit_domain_is_independent_of_governed_contexts() -> None:
    context = SOURCE / "valor" / "management_audit" / "domain"
    forbidden = ("valor.policy_risk", "valor.runtime_gateway")
    violations: list[str] = []
    for path in context.rglob("*.py"):
        for imported_module, line in imports_in(SOURCE, path):
            if imported_module.startswith(forbidden):
                violations.append(f"{path.relative_to(SOURCE)}:{line} imports {imported_module}")
    assert not violations, "Cross-context audit-domain imports:\n" + "\n".join(violations)


def test_management_identity_domain_is_framework_and_context_independent() -> None:
    context = SOURCE / "valor" / "management_identity" / "domain"
    forbidden = (
        "valor.management_audit",
        "valor.identity_tenancy",
        "valor.policy_risk",
        "valor.runtime_gateway",
    )
    violations: list[str] = []
    for path in context.rglob("*.py"):
        for imported_module, line in imports_in(SOURCE, path):
            if imported_module.startswith(forbidden):
                violations.append(f"{path.relative_to(SOURCE)}:{line} imports {imported_module}")
    assert not violations, "Management identity domain imports:\n" + "\n".join(violations)


def test_runtime_gateway_does_not_import_management_identity() -> None:
    context = SOURCE / "valor" / "runtime_gateway"
    violations: list[str] = []
    for path in context.rglob("*.py"):
        for imported_module, line in imports_in(SOURCE, path):
            if imported_module.startswith("valor.management_identity"):
                violations.append(f"{path.relative_to(SOURCE)}:{line} imports {imported_module}")
    assert not violations, "Runtime Management identity imports:\n" + "\n".join(violations)
