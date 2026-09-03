"""SQLAlchemy Model repository adapter."""

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from valor.ai_asset_registry.application.errors import (
    ModelNameAlreadyExists,
    OwningTenantNotFound,
)
from valor.ai_asset_registry.domain.model import (
    Model,
    ModelId,
    ModelName,
    Provider,
    ProviderModelReference,
)
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.infrastructure.models import ModelRow

MODEL_NAME_UNIQUE_CONSTRAINT = "uq_models_tenant_id_normalized_name"
MODEL_TENANT_FOREIGN_KEY = "fk_models_tenant_id_tenants"


class SqlAlchemyModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, model: Model) -> None:
        self._session.add(
            ModelRow(
                id=model.id.value,
                tenant_id=model.tenant_id.value,
                name=model.name.value,
                normalized_name=model.name.normalized,
                provider=model.provider.value,
                provider_model_reference=model.provider_model_reference.value,
                created_at=model.created_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if (
                isinstance(error.orig, UniqueViolation)
                and error.orig.diag.constraint_name == MODEL_NAME_UNIQUE_CONSTRAINT
            ):
                raise ModelNameAlreadyExists from error
            if (
                isinstance(error.orig, ForeignKeyViolation)
                and error.orig.diag.constraint_name == MODEL_TENANT_FOREIGN_KEY
            ):
                raise OwningTenantNotFound(model.tenant_id) from error
            raise

    async def get(self, model_id: ModelId) -> Model | None:
        row = await self._session.scalar(select(ModelRow).where(ModelRow.id == model_id.value))
        if row is None:
            return None
        return Model(
            id=ModelId(row.id),
            tenant_id=OwningTenantId(row.tenant_id),
            name=ModelName(row.name),
            provider=Provider(row.provider),
            provider_model_reference=ProviderModelReference(row.provider_model_reference),
            created_at=row.created_at,
        )
