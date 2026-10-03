from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = "production"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    llm_timeout: int = 45
    llm_max_retries: int = 3

    wechat_auto_reply: bool = True

    enable_private_chat: bool = True
    enable_group_chat: bool = False

    max_context_messages: int = 20
    max_reply_length: int = 120

    message_debounce_min: int = 3
    message_debounce_max: int = 8

    reply_min_delay: int = 3
    reply_max_delay: int = 8

    high_risk_mode: Literal["block", "warn"] = "block"

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765

    log_level: str = "INFO"

    data_dir: Path = Field(default=Path(__file__).parent.parent / "data")
    db_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "agent.db")
    logs_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "logs")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
