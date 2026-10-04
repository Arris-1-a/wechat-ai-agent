"""Safety policy engine."""
from __future__ import annotations

import re
from typing import Optional

from app.config import settings


# Keywords that trigger risk levels
LOW_RISK_PATTERNS = [
    r"你好", r"在吗", r"最近", r"怎么样", r"忙什么", r"吃饭",
    r"你好", r"嗨", r"嘿", r"哈喽", r"hello", r"hi",
]

MEDIUM_RISK_PATTERNS = [
    r"什么时候.*回来", r"在哪里", r"什么位置", r"是不是很忙",
    r"最近.*怎样", r"在忙.*什么",
]

HIGH_RISK_PATTERNS = [
    r"借钱", r"借.*钱", r"借.*块", r"借.*元", r"借.*万",
    r"转账", r"付款", r"银行卡", r"密码", r"验证码",
    r"合同", r"同意.*合同", r"签字", r"承诺", r"答应.*钱",
    r"帮我.*付款", r"帮我.*转账", r"发.*验证码", r"把.*密码.*给",
    r"钱.*转", r"给.*钱", r"打.*钱", r"汇.*款",
]

CRITICAL_PATTERNS = [
    r"转账", r"红包", r"付款", r"密码", r"验证码",
    r"API.*Key", r"apikey", r"token", r"secret",
    r"身份认证", r"登录.*密码", r"账号.*密码",
]

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{10,}",
    r"password\s*[:=]\s*\S+",
    r"token\s*[:=]\s*\S+",
    r"api[_-]?key\s*[:=]\s*\S+",
    r"验证码[是：:]\s*\d+",
    r"\d{6,}",
]

PROMPT_INJECTION_PATTERNS = [
    r"忽略.*规则", r"忘记.*之前", r"system.?prompt",
    r"你是.*GPT", r"你是.*AI", r"执行.*命令",
    r"运行.*shell", r"读取.*文件",
]


class SafetyPolicy:
    """Evaluates message risk level and blocks dangerous content."""

    def __init__(self, high_risk_mode: str = "block", persona_data: dict | None = None):
        self.high_risk_mode = high_risk_mode
        self._persona_data = persona_data

    def _get_blacklist_topics(self) -> list[str]:
        if self._persona_data is not None:
            return self._persona_data.get("blacklist_topics", [])
        from app.config import settings
        return settings.persona.data.get("blacklist_topics", [])

    def assess_risk(self, message: str) -> tuple[str, str]:
        """Return (risk_level, reason)."""
        msg = message.strip()

        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return "critical", f"critical keyword matched: {pattern}"

        for pattern in HIGH_RISK_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return "high", f"high risk keyword: {pattern}"

        if self.check_prompt_injection(msg):
            return "critical", "potential prompt injection"

        if self.matches_blacklist_topic(msg):
            return "critical", "blacklist topic match"

        for pattern in MEDIUM_RISK_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return "medium", f"medium risk keyword: {pattern}"

        return "low", "normal conversation"

    def check_prompt_injection(self, text: str) -> bool:
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def matches_blacklist_topic(self, text: str) -> bool:
        blacklist = self._get_blacklist_topics()
        for topic in blacklist:
            if topic and topic in text:
                return True
        return False

    def filter_secrets(self, text: str) -> tuple[str, bool]:
        """Remove or flag sensitive data in text."""
        blocked = False
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                blocked = True
                text = re.sub(pattern, "****", text, flags=re.IGNORECASE)
        return text, blocked

    def is_safe(self, risk_level: str) -> bool:
        if risk_level == "low":
            return True
        if risk_level == "medium":
            return True
        if risk_level == "high":
            return self.high_risk_mode != "block"
        return False
