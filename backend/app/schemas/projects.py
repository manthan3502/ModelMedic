from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class FeatureChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature_id: str
    type: Literal["numeric", "categorical"]


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    target_id: str
    positive_class: str | None = None
    features: list[FeatureChoice]
    classifier: Literal["logistic_regression", "random_forest", "gradient_boosting"] | None = None
    weighting: Literal["standard", "balanced"] | None = None
