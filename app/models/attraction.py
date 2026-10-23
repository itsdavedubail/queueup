import uuid

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Attraction(TimestampMixin, Base):
    """Something guests line up for. Queue and booking endpoints arrive in weeks 2-3."""

    __tablename__ = "attractions"
    __table_args__ = (
        CheckConstraint("capacity_per_slot > 0", name="capacity_positive"),
        CheckConstraint("slot_minutes > 0", name="slot_minutes_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    capacity_per_slot: Mapped[int]
    slot_minutes: Mapped[int] = mapped_column(default=15)
    is_open: Mapped[bool] = mapped_column(default=True)
