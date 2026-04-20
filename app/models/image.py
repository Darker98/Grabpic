from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models import Base


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bucket_key: Mapped[str] = mapped_column(String(512), nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    face_embeddings = relationship("FaceEmbedding", back_populates="image", cascade="all, delete-orphan")
    mappings = relationship("ImageFaceMapping", back_populates="image", cascade="all, delete-orphan")
