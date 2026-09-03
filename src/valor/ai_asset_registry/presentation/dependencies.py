"""Shared AI Asset Registry presentation dependencies."""

from collections.abc import Callable
from typing import cast

from fastapi import Request

from valor.ai_asset_registry.application.ports import TenantExistencePort

TenantExistenceFactory = Callable[[], TenantExistencePort]


def tenant_existence(request: Request) -> TenantExistencePort:
    factory = cast(TenantExistenceFactory, request.app.state.tenant_existence_factory)
    return factory()
