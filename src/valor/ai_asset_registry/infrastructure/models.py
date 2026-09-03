"""SQLAlchemy persistence representations for governed AI assets."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class AgentRow(SqlAlchemyBase):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "normalized_name",
            name="uq_agents_tenant_id_normalized_name",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_agents_tenant_id_tenants"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRow(SqlAlchemyBase):
    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "normalized_name",
            name="uq_models_tenant_id_normalized_name",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_models_tenant_id_tenants"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_model_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
