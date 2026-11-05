#!/usr/bin/env python
"""
Token Tracker - LLM Token usage and cost tracking system (Advanced)
Uses tiktoken for precise token counting, supports multiple models and more accurate cost calculation
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from typing import Any

# Try importing tiktoken (if available)
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    tiktoken = None

LITELLM_AVAILABLE = False

# ── 汇率（用于在摘要中显示人民币计价） ──
CNY_PER_USD = 7.2  # 近似汇率，仅用于展示

# Model pricing table (price per 1K tokens, unit: USD)
# Data source: Official pricing from various vendors (November 2024)
# DeepSeek 支持缓存命中双定价（参考官方人民币定价: 缓存命中 ¥0.02/百万, 缓存未命中 ¥1/百万, 输出 ¥2/百万）
MODEL_PRICING = {
    # OpenAI GPT Series
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-32k": {"input": 0.06, "output": 0.12},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    # DeepSeek Series (支持缓存命中计费)
    "deepseek-chat": {
        "input": 0.00014,               # 缓存未命中价格 (USD/1K) ≈ ¥1/百万
        "output": 0.00028,              # 输出价格 (USD/1K)      ≈ ¥2/百万
        "cache_hit_input": 0.0000028,   # 缓存命中输入价格 (USD/1K) ≈ ¥0.02/百万
    },
    "deepseek-coder": {
        "input": 0.00014,
        "output": 0.00028,
        "cache_hit_input": 0.0000028,
    },
    # Anthropic Claude Series
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    # Google Gemini Series
    "gemini-pro": {"input": 0.0005, "output": 0.0015},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
}


def get_tiktoken_encoding(model_name: str):
    """
    Get tiktoken encoder (for precise token counting)

    Args:
        model_name: Model name

    Returns:
        tiktoken.Encoding object, returns None if not available
    """
    if not TIKTOKEN_AVAILABLE:
        return None

    try:
        # Try getting encoding based on model name
        if "gpt-4" in model_name.lower() or "gpt-3.5" in model_name.lower():
            return tiktoken.encoding_for_model(model_name)
        if "gpt-4o" in model_name.lower():
            return tiktoken.encoding_for_model("gpt-4o")
        # Default to cl100k_base (encoding for GPT-3.5/GPT-4)
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        # If fails, use default encoding
        return tiktoken.get_encoding("cl100k_base")


def count_tokens_with_tiktoken(text: str, model_name: str) -> int:
    """
    Precisely calculate token count using tiktoken

    Args:
        text: Text to calculate
        model_name: Model name (for selecting correct encoding)

    Returns:
        Token count
    """
    if not TIKTOKEN_AVAILABLE:
        return 0

    encoding = get_tiktoken_encoding(model_name)
    if encoding is None:
        return 0

    return len(encoding.encode(text))


def count_tokens_with_litellm(messages: list[dict], model_name: str) -> dict[str, int]:
    """Count tokens from messages using tiktoken (litellm removed)."""
    if not TIKTOKEN_AVAILABLE:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        text = "\n".join(str(m.get("content", "")) for m in messages)
        count = count_tokens_with_tiktoken(text, model_name)
        return {"prompt_tokens": count, "completion_tokens": 0, "total_tokens": count}
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def calculate_cost_with_litellm(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost using built-in pricing table."""
    return calculate_cost(model, prompt_tokens, completion_tokens)


def get_model_pricing(model_name: str) -> dict[str, float]:
    """
    Get model pricing information

    Args:
        model_name: Model name

    Returns:
        dict with keys 'input', 'output' (and optionally 'cache_hit_input') — price per 1K tokens (USD)
    """
    # Try exact match
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]

    # Try fuzzy match (handle model names with version numbers)
    model_lower = model_name.lower()
    for key, pricing in MODEL_PRICING.items():
        if key.lower() in model_lower or model_lower in key.lower():
            return pricing

    return MODEL_PRICING.get("gpt-4o-mini", {"input": 0.00015, "output": 0.0006})


def calculate_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    prompt_cache_hit_tokens: int = 0,
) -> float:
    """
    Calculate LLM call cost, supporting cache-hit pricing for models like DeepSeek.

    Args:
        model_name: Model name
        prompt_tokens: Total number of input tokens (cache hit + cache miss)
        completion_tokens: Number of output tokens
        prompt_cache_hit_tokens: Number of input tokens that hit cache (default 0)

    Returns:
        Cost (USD)
    """
    pricing = get_model_pricing(model_name)

    cache_hit_price = pricing.get("cache_hit_input", pricing["input"])
    cache_miss_tokens = max(0, prompt_tokens - prompt_cache_hit_tokens)

    input_cost = (
        (cache_miss_tokens / 1000.0) * pricing["input"]
        + (prompt_cache_hit_tokens / 1000.0) * cache_hit_price
    )
    output_cost = (completion_tokens / 1000.0) * pricing["output"]

    return input_cost + output_cost


@dataclass
class TokenUsage:
    """Token usage record for a single LLM call"""

    agent_name: str
    stage: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    calculation_method: str = "api"  # "api", "tiktoken", "litellm", "estimated"

    # ── 缓存命中统计 ──
    prompt_cache_hit_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenTracker:
    """
    Token Tracker (Advanced Version)
    Supports multiple token counting methods: API response > tiktoken > litellm > estimation
    """

    def __init__(self, prefer_tiktoken: bool = True, prefer_litellm: bool = False):
        """
        Initialize tracker.

        Args:
            prefer_tiktoken: If API doesn't return usage, prefer tiktoken calculation (default True)
            prefer_litellm: Whether to prefer litellm (requires litellm installation, default False)
        """
        self.usage_records: list[TokenUsage] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.prefer_tiktoken = prefer_tiktoken and TIKTOKEN_AVAILABLE
        self.prefer_litellm = prefer_litellm and LITELLM_AVAILABLE

        # ── 缓存命中聚合 ──
        self.total_prompt_cache_hit_tokens = 0

        # Callback for real-time updates (e.g., to display_manager)
        self._on_usage_added_callback = None

    def set_on_usage_added_callback(self, callback):
        """
        Set a callback to be called whenever usage is added.
        The callback receives the summary dict.

        Args:
            callback: Function that takes summary dict as argument
        """
        self._on_usage_added_callback = callback

    def add_usage(
        self,
        agent_name: str,
        stage: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        token_counts: dict[str, int] | None = None,
        # New parameters: for precise calculation
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        response_text: str | None = None,
        messages: list[dict] | None = None,
        usage: dict[str, int] | None = None,
    ):
        """
        Add token usage record (supports multiple calculation methods)

        Priority: usage (API raw dict) > token_counts > tiktoken > estimation

        Args:
            agent_name: Agent name
            stage: Stage name
            model: Model name
            prompt_tokens: Input tokens (fallback if no usage/token_counts)
            completion_tokens: Output tokens (fallback if no usage/token_counts)
            token_counts: Optional token count dictionary (from API response)
            system_prompt: System prompt (for tiktoken calculation)
            user_prompt: User prompt (for tiktoken calculation)
            response_text: Response text (for tiktoken calculation)
            messages: Message list (for litellm calculation)
            usage: Raw usage dict from complete_with_response — contains
                   provider-specific fields like ``prompt_cache_hit_tokens``
                   (DeepSeek) or ``cache_creation_input_tokens`` (Anthropic).
        """
        calculation_method = "api"
        prompt_cache_hit_tokens = 0

        # Priority 1: usage dict from complete_with_response (most accurate)
        if usage:
            prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
            completion_tokens = usage.get("completion_tokens", completion_tokens)
            calculation_method = "api"
            if "prompt_cache_hit_tokens" in usage:
                prompt_cache_hit_tokens = usage["prompt_cache_hit_tokens"]
        # Priority 2: token_counts (legacy parameter)
        elif token_counts:
            prompt_tokens = token_counts.get("prompt_tokens", prompt_tokens)
            completion_tokens = token_counts.get("completion_tokens", completion_tokens)
            calculation_method = "api"
            # ── 提取缓存命中数据（DeepSeek API 返回的字段） ──
            if "prompt_cache_hit_tokens" in token_counts:
                prompt_cache_hit_tokens = token_counts["prompt_cache_hit_tokens"]
        # If no API data, try using tiktoken for precise calculation
        elif self.prefer_tiktoken and system_prompt and user_prompt:
            prompt_tokens = count_tokens_with_tiktoken(system_prompt + "\n" + user_prompt, model)
            if response_text:
                completion_tokens = count_tokens_with_tiktoken(response_text, model)
            calculation_method = "tiktoken"
        # If litellm is available and messages are provided
        elif self.prefer_litellm and messages:
            result = count_tokens_with_litellm(messages, model)
            prompt_tokens = result["prompt_tokens"]
            completion_tokens = result.get("completion_tokens", completion_tokens)
            calculation_method = "litellm"
        # If none available, use estimation (fallback)
        elif system_prompt and user_prompt:
            # Simple estimation
            estimated_prompt_tokens = int(
                (len(system_prompt.split()) + len(user_prompt.split())) * 1.3
            )
            prompt_tokens = estimated_prompt_tokens
            if response_text:
                completion_tokens = int(len(response_text.split()) * 1.3)
            calculation_method = "estimated"

        total_tokens = prompt_tokens + completion_tokens

        # ── 计算成本（传入缓存命中 token 数） ──
        if self.prefer_litellm and LITELLM_AVAILABLE:
            cost_usd = calculate_cost_with_litellm(model, prompt_tokens, completion_tokens)
        else:
            cost_usd = calculate_cost(
                model,
                prompt_tokens,
                completion_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            )

        # Create usage record
        usage = TokenUsage(
            agent_name=agent_name,
            stage=stage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            calculation_method=calculation_method,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        )

        self.usage_records.append(usage)

        # Update totals
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.total_cost_usd += cost_usd
        self.total_prompt_cache_hit_tokens += prompt_cache_hit_tokens

        # Invoke callback for real-time updates
        if self._on_usage_added_callback:
            try:
                self._on_usage_added_callback(self.get_summary())
            except Exception:
                pass  # Don't let callback errors affect main flow

    def _has_cache_support(self, model_name: str) -> bool:
        """Check whether the model's pricing entry includes a cache_hit_input key."""
        pricing = get_model_pricing(model_name)
        return "cache_hit_input" in pricing

    def get_summary(self) -> dict[str, Any]:
        """
        Get usage summary

        Returns:
            dict with keys:
                total_prompt_tokens, total_completion_tokens, total_tokens,
                total_cost_usd, total_calls, total_prompt_cache_hit_tokens,
                by_agent, by_model, by_method,
                tiktoken_available, litellm_available
        """
        by_agent: dict[str, dict[str, Any]] = {}
        by_model: dict[str, dict[str, Any]] = {}
        by_method: dict[str, dict[str, Any]] = {}

        for usage in self.usage_records:
            # Statistics by Agent
            if usage.agent_name not in by_agent:
                by_agent[usage.agent_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                    "prompt_cache_hit_tokens": 0,
                }
            by_agent[usage.agent_name]["prompt_tokens"] += usage.prompt_tokens
            by_agent[usage.agent_name]["completion_tokens"] += usage.completion_tokens
            by_agent[usage.agent_name]["total_tokens"] += usage.total_tokens
            by_agent[usage.agent_name]["cost_usd"] += usage.cost_usd
            by_agent[usage.agent_name]["calls"] += 1
            by_agent[usage.agent_name]["prompt_cache_hit_tokens"] += usage.prompt_cache_hit_tokens

            # Statistics by model
            if usage.model not in by_model:
                by_model[usage.model] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                    "prompt_cache_hit_tokens": 0,
                }
            by_model[usage.model]["prompt_tokens"] += usage.prompt_tokens
            by_model[usage.model]["completion_tokens"] += usage.completion_tokens
            by_model[usage.model]["total_tokens"] += usage.total_tokens
            by_model[usage.model]["cost_usd"] += usage.cost_usd
            by_model[usage.model]["calls"] += 1
            by_model[usage.model]["prompt_cache_hit_tokens"] += usage.prompt_cache_hit_tokens

            # Statistics by calculation method
            method = usage.calculation_method
            if method not in by_method:
                by_method[method] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            by_method[method]["prompt_tokens"] += usage.prompt_tokens
            by_method[method]["completion_tokens"] += usage.completion_tokens
            by_method[method]["total_tokens"] += usage.total_tokens
            by_method[method]["cost_usd"] += usage.cost_usd
            by_method[method]["calls"] += 1

        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_calls": len(self.usage_records),
            "total_prompt_cache_hit_tokens": self.total_prompt_cache_hit_tokens,
            "by_agent": by_agent,
            "by_model": by_model,
            "by_method": by_method,
            "tiktoken_available": TIKTOKEN_AVAILABLE,
            "litellm_available": LITELLM_AVAILABLE,
        }

    def format_summary(self) -> str:
        """
        Format usage summary as readable string

        Returns:
            Formatted summary string
        """
        summary = self.get_summary()

        # ── 计算总体缓存命中率 ──
        total_cache_hit = summary["total_prompt_cache_hit_tokens"]
        total_input = summary["total_prompt_tokens"]
        cache_hit_rate = (total_cache_hit / total_input * 100) if total_input > 0 else 0.0

        lines = [
            "=" * 70,
            "💰 LLM Cost Statistics",
            "=" * 70,
            f"Total calls: {summary['total_calls']}",
            f"Total Tokens: {summary['total_tokens']:,}",
            f"  - Input: {summary['total_prompt_tokens']:,}",
            f"  - Output: {summary['total_completion_tokens']:,}",
            f"Total cost: ${summary['total_cost_usd']:.6f} USD",
            f"              ≈ ¥{summary['total_cost_usd'] * CNY_PER_USD:.4f} CNY",
        ]

        # ── 缓存命中统计（仅当有缓存数据时展示） ──
        if total_cache_hit > 0:
            cache_miss = total_input - total_cache_hit
            lines.append("")
            lines.append("📊 DeepSeek Cache Hit Statistics:")
            lines.append("-" * 70)
            lines.append(f"  Cache Hit Tokens:  {total_cache_hit:,} ({cache_hit_rate:.1f}%)")
            lines.append(f"  Cache Miss Tokens: {cache_miss:,} ({100 - cache_hit_rate:.1f}%)")
            # 计算节省：如果全部 miss 会比实际多花多少
            # 差别在于 (miss_price - hit_price) * hit_tokens / 1000
            # 用第一个 DeepSeek 定价段估算（deepseek-chat 和 deepseek-coder 一样）
            ds_pricing = get_model_pricing("deepseek-chat")
            miss_price = ds_pricing["input"]
            hit_price = ds_pricing.get("cache_hit_input", miss_price)
            saved_usd = (miss_price - hit_price) * (total_cache_hit / 1000.0)
            lines.append(f"  Cost Saved:        ~${saved_usd:.6f} USD")
            lines.append(f"                       ~¥{saved_usd * CNY_PER_USD:.4f} CNY")

        # If advanced features are used, show tool status and calculation method statistics
        if summary.get("tiktoken_available") or summary.get("litellm_available"):
            lines.append("")
            lines.append("Calculation Tool Status:")
            lines.append(
                f"  - tiktoken: {'✓ Available' if summary['tiktoken_available'] else '✗ Unavailable'}"
            )
            lines.append(
                f"  - litellm: {'✓ Available' if summary['litellm_available'] else '✗ Unavailable'}"
            )

            if summary.get("by_method"):
                lines.append("")
                lines.append("Statistics by Calculation Method:")
                lines.append("-" * 70)
                for method, stats in sorted(summary["by_method"].items()):
                    method_name = {
                        "api": "API Response",
                        "tiktoken": "tiktoken Precise Calculation",
                        "litellm": "litellm Calculation",
                        "estimated": "Estimation",
                    }.get(method, method)
                    lines.append(f"  {method_name}:")
                    lines.append(f"    Calls: {stats['calls']}")
                    lines.append(f"    Tokens: {stats['total_tokens']:,}")
                    lines.append(f"    Cost: ${stats['cost_usd']:.6f} USD")
                    lines.append("")

        lines.append("Statistics by Agent:")
        lines.append("-" * 70)
        for agent_name, stats in sorted(summary["by_agent"].items()):
            lines.append(f"  {agent_name}:")
            lines.append(f"    Calls: {stats['calls']}")
            lines.append(
                f"    Tokens: {stats['total_tokens']:,} (Input: {stats['prompt_tokens']:,}, Output: {stats['completion_tokens']:,})"
            )
            lines.append(f"    Cost: ${stats['cost_usd']:.6f} USD")
            # Per-agent cache hit rate
            agent_cache_hit = stats["prompt_cache_hit_tokens"]
            agent_input = stats["prompt_tokens"]
            if agent_cache_hit > 0 and agent_input > 0:
                agent_hit_rate = agent_cache_hit / agent_input * 100
                lines.append(
                    f"    Cache Hit: {agent_cache_hit:,} ({agent_hit_rate:.1f}%)"
                )
            lines.append("")

        lines.append("Statistics by Model:")
        lines.append("-" * 70)
        for model, stats in sorted(summary["by_model"].items()):
            lines.append(f"  {model}:")
            lines.append(f"    Calls: {stats['calls']}")
            lines.append(
                f"    Tokens: {stats['total_tokens']:,} (Input: {stats['prompt_tokens']:,}, Output: {stats['completion_tokens']:,})"
            )
            lines.append(f"    Cost: ${stats['cost_usd']:.6f} USD")
            # Per-model cache hit rate
            model_cache_hit = stats["prompt_cache_hit_tokens"]
            model_input = stats["prompt_tokens"]
            if model_cache_hit > 0 and model_input > 0:
                model_hit_rate = model_cache_hit / model_input * 100
                lines.append(
                    f"    Cache Hit: {model_cache_hit:,} ({model_hit_rate:.1f}%)"
                )
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def reset(self):
        """Reset all statistics"""
        self.usage_records.clear()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.total_prompt_cache_hit_tokens = 0

    def save(self, filepath: str):
        """
        Save usage records to file

        Args:
            filepath: Save path
        """
        data = {
            "summary": self.get_summary(),
            "records": [usage.to_dict() for usage in self.usage_records],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)