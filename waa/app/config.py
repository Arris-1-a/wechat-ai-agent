"""Settings and persona configuration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


DEFAULT_PERSONA = {
    "name": "小助手",
    "version": 1,
    "personality": "你是一个友好、热情的AI助手，帮助回复微信消息。",
    "tone": "friendly",
    "language": "auto",
    "emoji": True,
    "response_length": "short",
    "rules": [
        "回复要简洁，不超过120字",
        "用对方使用的语言回复",
        "遇到不确定的问题，诚实告知",
        "不透露AI身份以外的敏感信息",
        "保持友好和专业",
    ],
    "blacklist_topics": [
        "政治敏感",
        "暴力内容",
        "色情内容",
        "赌博相关",
        "非法活动",
    ],
    "system_behavior": {
        "max_reply_chars": 120,
        "cooldown_seconds": 30,
        "enable_thinking": False,
        "max_tokens": 500,
    },
}


class Persona:
    """Persona configuration with YAML persistence."""

    def __init__(self, data: dict | None = None, path: Path | None = None):
        self._data = data or DEFAULT_PERSONA.copy()
        self._path = path
        self._versions: list[dict] = []
        if path and path.exists():
            try:
                self._data = yaml.safe_load(path.read_text(encoding="utf-8")) or DEFAULT_PERSONA.copy()
            except Exception:
                pass

    @property
    def data(self) -> dict:
        return self._data

    def to_dict(self) -> dict:
        return self._data.copy()

    def get_system_prompt(self) -> str:
        personality = self._data.get("personality", DEFAULT_PERSONA["personality"])
        rules = self._data.get("rules", DEFAULT_PERSONA["rules"])
        behavior = self._data.get("system_behavior", DEFAULT_PERSONA["system_behavior"])
        max_chars = behavior.get("max_reply_chars", 120)
        rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules))
        return (
            f"你是微信AI助手「{self._data.get('name', '小助手')}」。\n\n"
            f"{personality}\n\n"
            f"回复规则：\n{rules_text}\n\n"
            f"限制：回复不超过{max_chars}字，用对方使用的语言回复。"
        )

    def update(self, updates: dict) -> None:
        self._data.update(updates)
        if self._path:
            self.save()

    def save(self) -> None:
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(yaml.dump(self._data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            self.save_version()

    def save_version(self) -> int:
        ver = self._data.get("version", 1) + 1
        self._data["version"] = ver
        self._versions.append({"version": ver, "timestamp": str(Path(self._path).stat().st_mtime if self._path else 0)})
        return ver


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

    safe_mode: bool = True
    auto_reply_enabled: bool = True
    allow_safe_mode_processing: bool = False  # Allow worker to process in safe_mode when True

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765

    log_level: str = "INFO"
    log_retention_days: int = 30

    config_dir: Path = Field(default=Path(__file__).parent.parent.parent / "config")
    data_dir: Path = Field(default=Path(__file__).parent.parent / "data")
    db_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "agent.db")
    logs_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "logs")
    persona_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "config" / "persona.yaml")
    pid_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "waa.pid")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def persona(self) -> Persona:
        return Persona(path=self.persona_path)

    def validate(self) -> list[str]:
        errors = []
        if not self.llm_api_key:
            errors.append("llm_api_key is empty")
        if not self.llm_base_url:
            errors.append("llm_base_url is empty")
        return errors


settings = Settings()
