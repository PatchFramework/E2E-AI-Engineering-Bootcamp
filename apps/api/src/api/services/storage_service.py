import boto3
import logging
from api.core.config import config

logger = logging.getLogger("api.services.storage_service")

class StorageService:
    @staticmethod
    def get_s3_client():
        return boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION,
        )

    @classmethod
    def upload_file(cls, file_bytes: bytes, s3_key: str, content_type: str = "application/pdf") -> None:
        """
        Uploads file bytes to MinIO/S3.
        """
        logger.info(f"Uploading file to S3 bucket '{config.S3_BUCKET}' with key '{s3_key}'")
        s3 = cls.get_s3_client()
        s3.put_object(
            Bucket=config.S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
        )

    @classmethod
    def download_file(cls, s3_key: str) -> bytes:
        """
        Downloads file bytes from MinIO/S3.
        """
        logger.info(f"Downloading file from S3 bucket '{config.S3_BUCKET}' with key '{s3_key}'")
        s3 = cls.get_s3_client()
        response = s3.get_object(
            Bucket=config.S3_BUCKET,
            Key=s3_key
        )
        return response["Body"].read()
