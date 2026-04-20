import asyncio
import logging
from botocore.client import Config
import boto3
from app.config import settings

logger = logging.getLogger(__name__)
_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.SUPABASE_S3_ENDPOINT,
            aws_access_key_id=settings.SUPABASE_S3_ACCESS_KEY,
            aws_secret_access_key=settings.SUPABASE_S3_SECRET_KEY,
            region_name=settings.SUPABASE_S3_REGION,
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


async def upload_bytes(bucket_key: str, content: bytes, content_type: str) -> None:
    client = get_s3_client()
    await asyncio.to_thread(
        client.put_object,
        Bucket=settings.SUPABASE_BUCKET,
        Key=bucket_key,
        Body=content,
        ContentType=content_type,
    )


async def download_bytes(bucket_key: str) -> bytes:
    client = get_s3_client()
    response = await asyncio.to_thread(
        client.get_object,
        Bucket=settings.SUPABASE_BUCKET,
        Key=bucket_key,
    )
    return await asyncio.to_thread(response["Body"].read)


async def generate_presigned_url(bucket_key: str, expires_in: int = 3600) -> str:
    client = get_s3_client()
    return await asyncio.to_thread(
        client.generate_presigned_url,
        "get_object",
        Params={"Bucket": settings.SUPABASE_BUCKET, "Key": bucket_key},
        ExpiresIn=expires_in,
    )
