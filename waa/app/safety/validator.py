"""AI reply validator."""
from __future__ import annotations

import json
import re
from typing import Optional

from app.models import AiAction, RiskLevel
from app.safety.policy import SafetyPolicy


class ReplyValidator:
    """Validates AI-generated replies before sending."""

    def __init__(self, max_length: int = 120, safety_policy: Optional[SafetyPolicy] = None):
        self.max_length = max_length
        self.safety = safety_policy or SafetyPolicy()

    def validate(self, response_text: str, risk_level: str = "low") -> tuple[bool, str]:
        """Validate a reply. Returns (is_valid, error_reason)."""
        if not response_text or not response_text.strip():
            return False, "empty reply"

        if len(response_text) > self.max_length:
            return False, f"reply too long ({len(response_text)} > {self.max_length})"

        filtered, blocked = self.safety.filter_secrets(response_text)
        if blocked:
            return False, "secret detected in reply"

        if any(kw in response_text.lower() for kw in ["system prompt", "you are", "ignore"]):
            return False, "potential prompt leakage"

        dangerous = re.search(
            r"(同意|答应|承诺|保证).*(转账|付款|借钱|合同|签字)",
            response_text,
        )
        if dangerous:
            return False, "dangerous commitment detected"

        return True, ""

    def parse_ai_response(self, raw_text: str) -> Optional[dict]:
        """Parse JSON response from LLM, fallback to plain text."""
        try:
            data = json.loads(raw_text)
            if "action" in data and "reply" in data:
                return data
        except json.JSONDecodeError:
            pass

        json_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {"action": "reply", "reply": raw_text.strip(), "risk": "low", "reason": "fallback"}
