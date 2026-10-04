from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    code_version: str = "unknown"
    code_dirty: bool = True
    model_config = SettingsConfigDict(env_prefix="MM_", extra="ignore", hide_input_in_errors=True)

    database_url: str
    environment: Literal["local", "deployment"] = "local"
    deployment_mode: Literal["full", "demo"] | None = None
    artifact_root: Path = Path("artifacts")
    lease_seconds: int = Field(default=30, ge=3)
    heartbeat_seconds: float = Field(default=5, ge=0.1)
    poll_seconds: float = Field(default=1, ge=0.1)
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    max_rows: int = Field(default=50_000, ge=1)
    max_columns: int = Field(default=100, ge=1)
    max_features: int = Field(default=50, ge=1)
    max_categories: int = Field(default=100, ge=1, le=100)
    max_encoded_columns: int = Field(default=2_000, ge=1)

    @model_validator(mode="after")
    def valid_runtime(self) -> Self:
        if make_url(self.database_url).drivername != "postgresql+psycopg":
            raise ValueError("PostgreSQL with psycopg is required")
        if self.environment != "local" and self.deployment_mode is None:
            raise ValueError("Explicit deployment mode is required outside local development")
        if self.heartbeat_seconds >= self.lease_seconds / 2:
            raise ValueError("Heartbeat interval must be less than half the lease")
        return self
