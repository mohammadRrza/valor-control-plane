from collections.abc import Callable

from valor.bootstrap.settings import RuntimeAuthenticationSettings
from valor.runtime_identity.application.ports import LegacyRuntimeConfiguration


class ConfiguredLegacyRuntimeIdentities:
    def __init__(self, settings: Callable[[], RuntimeAuthenticationSettings]) -> None:
        self._settings = settings

    def get(self, principal_id: str) -> LegacyRuntimeConfiguration | None:
        for value in self._settings().principals:
            if value.principal_id == principal_id:
                return LegacyRuntimeConfiguration(
                    value.principal_id,
                    value.tenant_id,
                    value.agent_id,
                    value.usage_limit,
                    value.per_invocation_allowance,
                )
        return None
