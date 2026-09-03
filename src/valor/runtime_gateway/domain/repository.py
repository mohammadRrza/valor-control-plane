"""Invocation persistence port."""

from typing import Protocol

from valor.runtime_gateway.domain.identity import InvocationId
from valor.runtime_gateway.domain.invocation import Invocation


class InvocationRepository(Protocol):
    async def add(self, invocation: Invocation) -> None: ...

    async def get(self, invocation_id: InvocationId) -> Invocation | None: ...
