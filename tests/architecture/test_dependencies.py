from pathlib import Path

from tests.architecture.dependency_checker import find_violations

SOURCE = Path(__file__).parents[2] / "src"


def test_repository_dependency_boundaries() -> None:
    violations = find_violations(SOURCE)
    assert not violations, "Architecture violations:\n" + "\n".join(
        violation.describe() for violation in violations
    )
