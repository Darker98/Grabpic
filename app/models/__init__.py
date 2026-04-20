from sqlalchemy.orm import declarative_base

Base = declarative_base()

from app.models.image import Image
from app.models.face import FaceEmbedding
from app.models.image_face_mapping import ImageFaceMapping

__all__ = ["Base", "Image", "FaceEmbedding", "ImageFaceMapping"]
