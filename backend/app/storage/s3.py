"""Private, write-once S3 objects. No public URLs, ACLs or user-selected keys.

Credentials use the SDK environment/role chain. The operator must enforce bucket
privacy and narrowly scoped read/write roles; Demo additionally refuses writes here.
Conditional writes are required of the S3-compatible provider (no overwrite fallback).
"""

import re
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]


def storage_errors(method: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(method)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except (BotoCoreError, ClientError):
            raise OSError("Private artifact storage operation failed") from None

    return wrapped


def checked_key(key: str) -> str:
    if not key or any(
        not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) for part in key.split("/")
    ):
        raise ValueError("Invalid artifact key")
    return key


class S3ArtifactStore:
    def __init__(
        self,
        bucket: str,
        prefix: str,
        region: str,
        endpoint: str | None = None,
        *,
        addressing_style: str = "virtual",
        server_side_encryption: str | None = None,
        read_only: bool = False,
        client: Any = None,
    ):
        self.bucket, self.prefix = bucket, checked_key(prefix)
        self.read_only = read_only
        self.encryption = (
            {"ServerSideEncryption": server_side_encryption} if server_side_encryption else {}
        )
        self.client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint,
                config=Config(
                    connect_timeout=5,
                    read_timeout=30,
                    retries={"max_attempts": 3, "mode": "standard"},
                    s3={"addressing_style": addressing_style},
                ),
            )
        )

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{checked_key(key)}"

    def _writable(self) -> None:
        if self.read_only:
            raise PermissionError("Demo artifact storage is read-only")

    @storage_errors
    def put(self, key: str, content: bytes) -> None:
        self._writable()
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=content,
            IfNoneMatch="*",
            **self.encryption,
        )

    @storage_errors
    def put_file(self, key: str, source: Path) -> None:
        self._writable()
        with source.open("rb") as stream:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._key(key),
                Body=stream,
                IfNoneMatch="*",
                **self.encryption,
            )

    @storage_errors
    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        with response["Body"] as stream:
            return bytes(stream.read())

    @storage_errors
    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise  # Access denied is never treated as a missing object.

    @storage_errors
    def delete(self, key: str) -> None:
        self._writable()
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    @storage_errors
    def delete_prefix(self, prefix: str) -> None:
        self._writable()
        key = self._key(prefix.rstrip("/"))
        self.delete(prefix.rstrip("/"))
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket,
            Prefix=key + "/",
        )
        for page in pages:
            objects = [{"Key": entry["Key"]} for entry in page.get("Contents", [])]
            if objects:
                response = self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": objects, "Quiet": True},
                )
                if response.get("Errors"):
                    raise OSError("Private artifact cleanup did not complete")
