import logging
import cv2
import numpy as np
from insightface.app import FaceAnalysis

logger = logging.getLogger(__name__)
app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))  


def _decode_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image bytes")
    return image


def get_face_embeddings(image_bytes: bytes) -> list[tuple[list[float], float, list[float]]]:
    image = _decode_image(image_bytes)
    faces = app.get(image)
    if not faces:
        raise ValueError("No faces found")

    results: list[tuple[list[float], float, list[float]]] = []
    for face in faces:
        embedding = face.embedding
        if embedding is None:
            continue
        bbox = getattr(face, "bbox", [])
        results.append((embedding.tolist(), float(getattr(face, "det_score", 0.0)), list(map(float, bbox))))

    if not results:
        raise ValueError("No faces found")

    return results


def get_face_embedding(image_bytes: bytes) -> tuple[list[float], float]:
    faces = get_face_embeddings(image_bytes)
    embedding, det_score, _ = faces[0]
    return embedding, det_score