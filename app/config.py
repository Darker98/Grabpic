from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str
    SUPABASE_S3_ENDPOINT: str
    SUPABASE_S3_ACCESS_KEY: str
    SUPABASE_S3_SECRET_KEY: str
    SUPABASE_S3_REGION: str = "ap-southeast-1"
    DATABASE_URL: str
    REDIS_URL: str
    ADMIN_API_KEY: str
    FACE_SIMILARITY_THRESHOLD: float = 0.82
    TOKEN_TTL_SECONDS: int = 3600
    WORKER_NAME: str = "worker-1"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
