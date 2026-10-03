"""AI agent — LLM integration for message reply generation."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional

import httpx

from app.config import settings
from app.logging_config import logger

logger = logging.getLogger("waa.agent")

SYSTEM_PROMPT = """你是微信AI自动回复助手。你的任务是帮助用户自动回复微信消息。

规则：
1. 回复要自然、友好、简洁
2. 不要暴露你是AI的事实
3. 不要回复金钱相关、密码相关、验证码相关的消息
4. 如果消息涉及敏感内容，礼貌地表示不方便回复
5. 回复长度控制在120字以内
6. 用中文回复，除非对方用其他语言"""

PROMPT_TEMPLATE = """{system_prompt}

当前对话上下文：
{context}

对方最新消息：{message}

请生成回复（只输出回复内容，不要解释）："""


class AIChatAgent:
    """AI chat agent for generating reply messages."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or settings.llm_api_key
        self._base_url = base_url or settings.llm_base_url
        self._model = model or settings.llm_model
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=settings.llm_timeout,
            )
        return self._client

    def generate_reply(self, context: str, message: str) -> Optional[str]:
        """Generate AI reply for a message."""
        if not self._api_key:
            logger.warning("LLM API key not configured")
            return None

        try:
            prompt = PROMPT_TEMPLATE.format(
                system_prompt=SYSTEM_PROMPT,
                context=context,
                message=message,
            )

            client = self._get_client()
            response = client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 150,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()

            logger.debug("AI reply generated: %.50s...", reply)
            return reply

        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP error: %s", e)
            return None
        except Exception as e:
            logger.error("LLM error: %s", e)
            return None

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
