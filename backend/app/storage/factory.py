from backend.app.core.config import Settings
from backend.app.storage.base import ArtifactStore
from backend.app.storage.local import LocalArtifactStore


def artifact_store(settings: Settings) -> ArtifactStore:
    if settings.artifact_backend == "s3":
        from backend.app.storage.s3 import S3ArtifactStore

        assert settings.s3_bucket
        return S3ArtifactStore(
            settings.s3_bucket,
            settings.s3_prefix,
            settings.s3_region,
            settings.s3_endpoint_url,
            read_only=settings.deployment_mode == "demo",
            addressing_style=settings.s3_addressing_style,
            server_side_encryption=settings.s3_server_side_encryption,
        )
    return LocalArtifactStore(settings.artifact_root)
