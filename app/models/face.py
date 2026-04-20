from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.models import Base


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    grab_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    image_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id"), nullable=False)
    bbox: Mapped[dict] = mapped_column(JSON, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    image = relationship("Image", back_populates="face_embeddings")
