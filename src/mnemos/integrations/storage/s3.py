from __future__ import annotations

import asyncio

import boto3
from botocore.exceptions import ClientError

from mnemos.core.config import settings


class S3Storage:
    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    async def ensure_bucket(self) -> None:
        def work() -> None:
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError:
                self.client.create_bucket(Bucket=self.bucket)

        await asyncio.to_thread(work)

    async def create_presigned_upload(
        self, object_key: str, mime_type: str, expires_seconds: int
    ) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self.bucket, "Key": object_key, "ContentType": mime_type},
            ExpiresIn=expires_seconds,
        )

    async def object_exists(self, object_key: str) -> bool:
        def work() -> bool:
            try:
                self.client.head_object(Bucket=self.bucket, Key=object_key)
                return True
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code", "")) in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    return False
                raise

        return await asyncio.to_thread(work)

    async def object_size(self, object_key: str) -> int:
        response = await asyncio.to_thread(
            self.client.head_object, Bucket=self.bucket, Key=object_key
        )
        return int(response["ContentLength"])

    async def delete_object(self, object_key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=object_key)

    async def object_metadata(self, object_key: str) -> dict[str, object]:
        response = await asyncio.to_thread(
            self.client.head_object, Bucket=self.bucket, Key=object_key
        )
        return {
            "size_bytes": int(response["ContentLength"]),
            "content_type": str(response.get("ContentType") or ""),
            "etag": str(response.get("ETag") or "").strip('"'),
        }
