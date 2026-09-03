"""Transparent import-boundary checks for VALOR architectural layers."""

import ast
from dataclasses import dataclass
from pathlib import Path

PROHIBITED_LAYER_IMPORTS = {
    "domain": {"infrastructure", "presentation"},
    "shared_kernel": {"infrastructure", "presentation"},
    "application": {"infrastructure", "presentation"},
}
DOMAIN_EXTERNALS = {
    "aiohttp",
    "aiokafka",
    "azure",
    "boto3",
    "botocore",
    "confluent_kafka",
    "fastapi",
    "google.cloud",
    "httpx",
    "kafka",
    "opentelemetry.sdk",
    "openai",
    "pydantic",
    "pydantic_settings",
    "redis",
    "requests",
    "sqlalchemy",
    "starlette",
    "urllib3",
}
PROHIBITED_EXTERNAL_IMPORTS = {
    "domain": DOMAIN_EXTERNALS,
    "shared_kernel": DOMAIN_EXTERNALS,
    "application": {
        "aiokafka",
        "azure",
        "boto3",
        "botocore",
        "confluent_kafka",
        "fastapi",
        "google.cloud",
        "kafka",
        "openai",
        "sqlalchemy",
        "starlette",
    },
}


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    source_module: str
    layer: str
    imported_module: str
    rule: str
    line: int

    def describe(self) -> str:
        return (
            f"{self.source_module}:{self.line} ({self.layer}) must not import "
            f"{self.imported_module} [{self.rule}]"
        )


def module_name(source_root: Path, path: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def architectural_layer(source_root: Path, path: Path) -> str | None:
    parts = path.relative_to(source_root).parts[:-1]
    layers = [part for part in parts if part in PROHIBITED_LAYER_IMPORTS]
    return layers[-1] if layers else None


def resolve_import(source_module: str, is_package: bool, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    package_parts = source_module.split(".") if is_package else source_module.split(".")[:-1]
    ascend = node.level - 1
    base = package_parts[: len(package_parts) - ascend] if ascend else package_parts
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def imports_in(source_root: Path, path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    source_module = module_name(source_root, path)
    is_package = path.name == "__init__.py"
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = resolve_import(source_module, is_package, node)
            imports.extend(
                (".".join(part for part in (resolved, alias.name) if part), node.lineno)
                for alias in node.names
            )
    return imports


def matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def find_violations(source_root: Path) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for path in sorted(source_root.rglob("*.py")):
        layer = architectural_layer(source_root, path)
        if layer is None:
            continue
        source_module = module_name(source_root, path)
        for imported_module, line in imports_in(source_root, path):
            imported_parts = set(imported_module.split("."))
            forbidden_layers = PROHIBITED_LAYER_IMPORTS[layer] & imported_parts
            if forbidden_layers:
                violations.append(
                    ArchitectureViolation(
                        source_module,
                        layer,
                        imported_module,
                        f"{layer} cannot depend on {sorted(forbidden_layers)[0]}",
                        line,
                    )
                )
                continue
            for prefix in PROHIBITED_EXTERNAL_IMPORTS[layer]:
                if matches_prefix(imported_module, prefix):
                    violations.append(
                        ArchitectureViolation(
                            source_module,
                            layer,
                            imported_module,
                            f"{layer} must remain independent of {prefix}",
                            line,
                        )
                    )
                    break
    return violations
