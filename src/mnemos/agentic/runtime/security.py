"""Tool Security Hardening for the Mnemos agentic runtime.

Provides three security layers that sit between the dispatch and tool execution:
1. RateLimiter — per-tool, per-agent rate limiting with sliding window
2. OutputSanitizer — strips secrets, PII, and internal paths from tool output
3. InjectionDetector — detects prompt injection, SQL injection, XSS in tool args

All checks are non-blocking warnings by default. Set block=True to reject.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.security")


# ------------------------------------------------------------------ #
#  Rate Limiter
# ------------------------------------------------------------------ #
class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded and blocking is enabled."""

    def __init__(self, tool: str, agent: str, limit: int, window: float) -> None:
        self.tool = tool
        self.agent = agent
        self.limit = limit
        self.window = window
        super().__init__(
            f"Rate limit exceeded for tool '{tool}' by agent '{agent}': {limit} calls in {window}s"
        )


class RateLimitConfig(BaseModel):
    """Rate limit configuration for a specific tool."""

    max_calls: int = Field(default=50, ge=1, description="Max calls in window")
    window_seconds: float = Field(default=60.0, gt=0, description="Sliding window in seconds")


class RateLimiter:
    """Sliding-window rate limiter per (tool, agent) pair."""

    def __init__(
        self,
        default_config: RateLimitConfig | None = None,
        tool_configs: dict[str, RateLimitConfig] | None = None,
        block: bool = False,
    ) -> None:
        self._default_config = default_config or RateLimitConfig()
        self._tool_configs = tool_configs or {}
        self._block = block
        self._call_times: dict[tuple[str, str], list[float]] = defaultdict(list)

    def check(self, tool: str, agent: str) -> RateLimitCheckResult:
        now = time.time()
        config = self._tool_configs.get(tool, self._default_config)
        key = (tool, agent)
        cutoff = now - config.window_seconds

        self._call_times[key] = [t for t in self._call_times[key] if t > cutoff]
        current_count = len(self._call_times[key])

        if current_count >= config.max_calls:
            logger.warning(
                f"Rate limit hit: {tool} by {agent} ({current_count}/{config.max_calls} in {config.window_seconds}s)"
            )
            return RateLimitCheckResult(
                allowed=False,
                current_count=current_count,
                max_calls=config.max_calls,
                window_seconds=config.window_seconds,
                retry_after_seconds=config.window_seconds - (now - self._call_times[key][0])
                if self._call_times[key]
                else config.window_seconds,
            )

        return RateLimitCheckResult(
            allowed=True,
            current_count=current_count + 1,
            max_calls=config.max_calls,
            window_seconds=config.window_seconds,
        )

    def record(self, tool: str, agent: str) -> None:
        self._call_times[(tool, agent)].append(time.time())

    def reset(self, tool: str | None = None, agent: str | None = None) -> None:
        if tool and agent:
            self._call_times.pop((tool, agent), None)
        elif tool:
            keys = [k for k in self._call_times if k[0] == tool]
            for k in keys:
                del self._call_times[k]
        else:
            self._call_times.clear()

    def current_usage(self) -> dict[str, dict[str, int]]:
        now = time.time()
        usage: dict[str, dict[str, int]] = {}
        for (tool, agent), times in self._call_times.items():
            config = self._tool_configs.get(tool, self._default_config)
            cutoff = now - config.window_seconds
            recent = [t for t in times if t > cutoff]
            if recent:
                usage.setdefault(tool, {})[agent] = len(recent)
        return usage


class RateLimitCheckResult(BaseModel):
    allowed: bool
    current_count: int
    max_calls: int
    window_seconds: float
    retry_after_seconds: float | None = None


# ------------------------------------------------------------------ #
#  Output Sanitizer
# ------------------------------------------------------------------ #
class SanitizeAction(StrEnum):
    REDACT = "redact"
    MASK = "mask"
    REMOVE = "remove"


class SanitizeRule(BaseModel):
    pattern: str
    replacement: str = "[REDACTED]"
    action: SanitizeAction = SanitizeAction.REDACT


_DEFAULT_RULES: list[SanitizeRule] = [
    SanitizeRule(
        pattern=r"(?i)(password|passwd|pwd|secret|api_key|apikey|api[-_]?key)\s*[:=]\s*['\"]?[^\s'\"<>]+",
        replacement=r"\1=[REDACTED]",
    ),
    SanitizeRule(
        pattern=r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*",
        replacement="Bearer [REDACTED]",
    ),
    SanitizeRule(
        pattern=r"(?i)authorization:\s*['\"]?[^\s'\"<>]+",
        replacement="Authorization: [REDACTED]",
    ),
    SanitizeRule(
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        replacement="[EMAIL_REDACTED]",
    ),
    SanitizeRule(
        pattern=r"(?i)\/(?:home|users|etc)\/[^\s'\"<>]+",
        replacement="[PATH_REDACTED]",
    ),
    SanitizeRule(
        pattern=r"(?i)(neo4j|mysql|postgresql|mongodb):\/\/[^\s'\"<>]+",
        replacement="[CONNECTION_STRING_REDACTED]",
    ),
    SanitizeRule(
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        replacement="[SSN_REDACTED]",
    ),
]


class OutputSanitizer:
    """Strips secrets and sensitive data from tool output."""

    def __init__(self, extra_rules: list[SanitizeRule] | None = None) -> None:
        self._rules = list(_DEFAULT_RULES)
        if extra_rules:
            self._rules.extend(extra_rules)
        self._compiled: list[tuple[re.Pattern[str], str]] | None = None

    def _ensure_compiled(self) -> list[tuple[re.Pattern[str], str]]:
        if self._compiled is None:
            self._compiled = [(re.compile(r.pattern), r.replacement) for r in self._rules]
        return self._compiled

    def sanitize(self, data: str) -> tuple[str, list[str]]:
        compiled = self._ensure_compiled()
        redactions: list[str] = []
        result = data

        for pattern, replacement in compiled:
            matches = pattern.findall(result)
            if matches:
                redactions.extend(matches if isinstance(matches, list) else [matches])
                result = pattern.sub(replacement, result)

        return result, redactions

    def sanitize_dict(self, data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        sanitized = {}
        all_redactions: list[str] = []

        for key, value in data.items():
            if isinstance(value, str):
                clean, redactions = self.sanitize(value)
                sanitized[key] = clean
                all_redactions.extend(redactions)
            elif isinstance(value, dict):
                clean, redactions = self.sanitize_dict(value)
                sanitized[key] = clean
                all_redactions.extend(redactions)
            elif isinstance(value, list):
                clean_list, redactions = self.sanitize_list(value)
                sanitized[key] = clean_list
                all_redactions.extend(redactions)
            else:
                sanitized[key] = value

        return sanitized, all_redactions

    def sanitize_list(self, data: list[Any]) -> tuple[list[Any], list[str]]:
        sanitized = []
        all_redactions: list[str] = []

        for item in data:
            if isinstance(item, str):
                clean, redactions = self.sanitize(item)
                sanitized.append(clean)
                all_redactions.extend(redactions)
            elif isinstance(item, dict):
                clean, redactions = self.sanitize_dict(item)
                sanitized.append(clean)
                all_redactions.extend(redactions)
            else:
                sanitized.append(item)

        return sanitized, all_redactions

    def add_rule(self, rule: SanitizeRule) -> None:
        self._rules.append(rule)
        self._compiled = None

    @property
    def rule_count(self) -> int:
        return len(self._rules)


# ------------------------------------------------------------------ #
#  Injection Detector
# ------------------------------------------------------------------ #
class InjectionType(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"


class InjectionCheckResult(BaseModel):
    safe: bool = True
    detected_types: list[InjectionType] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    blocked_values: list[str] = Field(default_factory=list)


_PROMPT_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        "ignore previous instructions",
    ),
    (re.compile(r"(?i)you\s+are\s+now\s+a\s+", re.IGNORECASE), "role reassignment attempt"),
    (re.compile(r"(?i)system\s*:\s*you\s+are", re.IGNORECASE), "system prompt override"),
    (
        re.compile(r"(?i)forget\s+(all\s+)?prior\s+(context|instructions)", re.IGNORECASE),
        "forget prior context",
    ),
    (re.compile(r"(?i)new\s+instructions?\s*:", re.IGNORECASE), "new instructions injection"),
    (
        re.compile(r"(?i)act\s+as\s+if\s+you\s+have\s+no\s+restrictions", re.IGNORECASE),
        "restriction bypass",
    ),
    (re.compile(r"(?i)disregard\s+(all\s+)?previous", re.IGNORECASE), "disregard previous"),
    (re.compile(r"(?i)\\bDAN\\b.*\\bjailbreak\\b", re.IGNORECASE), "jailbreak attempt"),
    (re.compile(r"(?i)you\s+are\s+now\s+DAN", re.IGNORECASE), "DAN jailbreak"),
    (re.compile(r"(?i)do\s+anything\s+now", re.IGNORECASE), "DAN jailbreak"),
    (re.compile(r"(?i)override\s+safety", re.IGNORECASE), "safety override"),
    (re.compile(r"(?i)output\s+your\s+system\s+prompt", re.IGNORECASE), "system prompt extraction"),
    (
        re.compile(r"(?i)reveal\s+(your|the)\s+instructions", re.IGNORECASE),
        "instruction extraction",
    ),
    (
        re.compile(
            r"(?i)repeat\s+(all\s+)?(the\s+)?(above|preceding|previous)\s+(text|instructions?|prompt)",
            re.IGNORECASE,
        ),
        "prompt repeat attack",
    ),
    (re.compile(r"(?i)(?:<\|im_start\|>|<\|im_end\|>)", re.IGNORECASE), "delimiter injection"),
    (
        re.compile(r"(?i)\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
        "chat template injection",
    ),
]

_SQL_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(?:UNION\s+(?:ALL\s+)?SELECT)", re.IGNORECASE), "UNION SELECT"),
    (re.compile(r"(?i)(?:DROP\s+(?:TABLE|DATABASE|INDEX))", re.IGNORECASE), "DROP statement"),
    (re.compile(r"(?i)(?:DELETE\s+FROM)", re.IGNORECASE), "DELETE FROM"),
    (re.compile(r"(?i)(?:INSERT\s+INTO\s+\w+\s+VALUES)", re.IGNORECASE), "INSERT INTO"),
    (re.compile(r"(?i)(?:UPDATE\s+\w+\s+SET)", re.IGNORECASE), "UPDATE SET"),
    (re.compile(r"(?i)(?:;\s*DROP\b)", re.IGNORECASE), "stacked DROP"),
    (re.compile(r"(?i)(?:'\s*OR\s+'1'\s*=\s*'1)", re.IGNORECASE), "tautology injection"),
    (re.compile(r"(?i)(?:'\s*OR\s+1\s*=\s*1)", re.IGNORECASE), "numeric tautology"),
    (re.compile(r"(?i)(?:--\s*$|/\*.*\*/)", re.IGNORECASE), "comment-based injection"),
]

_XSS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"<\s*script[^>]*>", re.IGNORECASE), "script tag"),
    (re.compile(r"javascript\s*:", re.IGNORECASE), "javascript URI"),
    (re.compile(r"<\s*img[^>]*onerror\s*=", re.IGNORECASE), "onerror handler"),
    (re.compile(r"<\s*svg[^>]*onload\s*=", re.IGNORECASE), "onload handler"),
    (re.compile(r"<\s*iframe[^>]*>", re.IGNORECASE), "iframe tag"),
    (re.compile(r"<\s*object[^>]*>", re.IGNORECASE), "object tag"),
    (re.compile(r"<\s*embed[^>]*>", re.IGNORECASE), "embed tag"),
]

_COMMAND_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?:;\s*(?:ls|cat|rm|chmod|chown|curl|wget|nc|bash|sh|python|perl|ruby)\s)"),
        "shell command chaining",
    ),
    (
        re.compile(r"(?:\|\s*(?:ls|cat|rm|chmod|chown|curl|wget|nc|bash|sh|python|perl|ruby)\s)"),
        "pipe to shell",
    ),
    (re.compile(r"(?:`[^`]+`)"), "backtick execution"),
    (re.compile(r"(?:\$\([^)]+\))"), "command substitution"),
    (
        re.compile(r"(?:&&\s*(?:ls|cat|rm|chmod|chown|curl|wget|nc|bash|sh|python|perl|ruby))"),
        "conditional execution",
    ),
]

_PATH_TRAVERSAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:\.\./){3,}"), "deep traversal"),
    (re.compile(r"(?:%2e%2e%2f){2,}", re.IGNORECASE), "URL-encoded traversal"),
    (re.compile(r"(?:/etc/(?:passwd|shadow|hosts))", re.IGNORECASE), "system file access"),
    (
        re.compile(r"(?:(?:c:\\windows|/root|/home/\w+/\.(?:ssh|gnupg|config)))", re.IGNORECASE),
        "sensitive directory",
    ),
]


class InjectionDetector:
    """Detects injection attacks in tool arguments."""

    def __init__(
        self,
        block_prompt_injection: bool = False,
        block_sql_injection: bool = False,
        block_xss: bool = False,
        block_command_injection: bool = False,
        block_path_traversal: bool = False,
    ) -> None:
        self._block_config = {
            InjectionType.PROMPT_INJECTION: block_prompt_injection,
            InjectionType.SQL_INJECTION: block_sql_injection,
            InjectionType.XSS: block_xss,
            InjectionType.COMMAND_INJECTION: block_command_injection,
            InjectionType.PATH_TRAVERSAL: block_path_traversal,
        }

    def check_arguments(self, arguments: dict[str, Any]) -> InjectionCheckResult:
        all_values = self._extract_all_string_values(arguments)
        combined = " ".join(all_values)

        result = InjectionCheckResult()

        for pattern, desc in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(combined):
                result.detected_types.append(InjectionType.PROMPT_INJECTION)
                result.details.append(f"Prompt injection: {desc}")
                result.safe = False

        for pattern, desc in _SQL_INJECTION_PATTERNS:
            if pattern.search(combined):
                result.detected_types.append(InjectionType.SQL_INJECTION)
                result.details.append(f"SQL injection: {desc}")
                result.safe = False

        for pattern, desc in _XSS_PATTERNS:
            if pattern.search(combined):
                result.detected_types.append(InjectionType.XSS)
                result.details.append(f"XSS: {desc}")
                result.safe = False

        for pattern, desc in _COMMAND_INJECTION_PATTERNS:
            if pattern.search(combined):
                result.detected_types.append(InjectionType.COMMAND_INJECTION)
                result.details.append(f"Command injection: {desc}")
                result.safe = False

        for pattern, desc in _PATH_TRAVERSAL_PATTERNS:
            if pattern.search(combined):
                result.detected_types.append(InjectionType.PATH_TRAVERSAL)
                result.details.append(f"Path traversal: {desc}")
                result.safe = False

        result.detected_types = list(dict.fromkeys(result.detected_types))

        return result

    def should_block(self, result: InjectionCheckResult) -> bool:
        for inj_type in result.detected_types:
            if self._block_config.get(inj_type, False):
                return True
        return False

    def _extract_all_string_values(self, data: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for key, value in data.items():
            values.append(str(key))
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, dict):
                values.extend(self._extract_all_string_values(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        values.append(item)
                    elif isinstance(item, dict):
                        values.extend(self._extract_all_string_values(item))
        return values
