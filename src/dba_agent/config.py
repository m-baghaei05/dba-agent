"""Load and validate config.yaml + .env.

Design notes
- Non-secret settings (provider URL, model, limits) live in config.yaml, which is committed.
- Secrets (API keys) live in .env, which is git-ignored. The config only stores the *name*
  of the environment variable holding the key (`api_key_env`), never the key itself.
- The active profile can be overridden with the DBA_PROFILE environment variable, so the
  model/provider can be switched without editing any file (spec, Section 2).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

PROFILE_ENV_VAR = "DBA_PROFILE"


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


class ProviderProfile(BaseModel):
    base_url: str
    model: str
    api_key_env: str | None = None  # None = no key needed (e.g. local Ollama)
    json_mode: bool = False         # send response_format=json_object (only if the provider supports it)

    def api_key(self) -> str:
        """Return the API key from the environment, or fail with a clear message."""
        if self.api_key_env is None:
            return "not-needed"  # the OpenAI client requires a non-empty string
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise ConfigError(
                f"Environment variable {self.api_key_env} is empty. "
                f"Add it to your .env file (see .env.example)."
            )
        return key


class LLMSettings(BaseModel):
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_retries: int = Field(3, ge=1)
    timeout_seconds: int = Field(180, ge=1)


class WorkflowSettings(BaseModel):
    interview_min_followup_rounds: int = Field(1, ge=1)
    interview_max_rounds: int = Field(4, ge=2)
    sql_max_repair_attempts: int = Field(3, ge=1)


class PathSettings(BaseModel):
    output_dir: Path = Path("output")
    prompts_dir: Path = Path("prompts")


class AppConfig(BaseModel):
    active_profile: str
    profiles: dict[str, ProviderProfile]
    llm: LLMSettings = LLMSettings()
    workflow: WorkflowSettings = WorkflowSettings()
    paths: PathSettings = PathSettings()

    @model_validator(mode="after")
    def _check_active_profile(self) -> "AppConfig":
        if self.active_profile not in self.profiles:
            known = ", ".join(sorted(self.profiles))
            raise ValueError(
                f"Unknown profile '{self.active_profile}'. Known profiles: {known}"
            )
        return self

    @property
    def provider(self) -> ProviderProfile:
        return self.profiles[self.active_profile]


def load_config(path: str | Path = "config.yaml", env_file: str | Path | None = ".env") -> AppConfig:
    """Read config.yaml, load .env, apply the DBA_PROFILE override, and validate."""
    if env_file is not None:
        load_dotenv(env_file, override=False)  # real environment variables win over .env

    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path.resolve()}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    override = os.getenv(PROFILE_ENV_VAR, "").strip()
    if override:
        raw["active_profile"] = override

    try:
        return AppConfig.model_validate(raw)
    except ValueError as e:  # pydantic.ValidationError is a ValueError
        raise ConfigError(f"Invalid configuration in {path}:\n{e}") from e
