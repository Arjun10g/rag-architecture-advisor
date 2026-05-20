from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any


DEFAULT_HF_INFERENCE_MODEL = "HuggingFaceH4/zephyr-7b-beta"
DEFAULT_HF_INFERENCE_PROVIDER = "auto"


class LLMProviderUnavailable(RuntimeError):
    """Raised when a configured generation provider cannot produce text."""


@dataclass(frozen=True)
class GenerationConfig:
    provider: str = "hf"
    model: str = DEFAULT_HF_INFERENCE_MODEL
    hf_provider: str = DEFAULT_HF_INFERENCE_PROVIDER
    token: str | None = None
    timeout_seconds: float = 30.0
    max_tokens: int = 700
    temperature: float = 0.2
    retries: int = 1

    @classmethod
    def from_env(cls) -> "GenerationConfig":
        return cls(
            provider=os.getenv("LLM_PROVIDER", "hf"),
            model=os.getenv("HF_INFERENCE_MODEL") or DEFAULT_HF_INFERENCE_MODEL,
            hf_provider=os.getenv("HF_INFERENCE_PROVIDER", DEFAULT_HF_INFERENCE_PROVIDER),
            token=_first_env("HF_TOKEN", "HF_ACCESS_TOKEN"),
            timeout_seconds=_env_float("HF_INFERENCE_TIMEOUT_SECONDS", 30.0),
            max_tokens=_env_int("LLM_MAX_TOKENS", 700),
            temperature=_env_float("LLM_TEMPERATURE", 0.2),
            retries=_env_int("LLM_RETRIES", 1),
        )


class DisabledLLMProvider:
    name = "disabled"
    model: str | None = None

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        raise LLMProviderUnavailable("LLM generation is disabled.")


@dataclass
class HFInferenceProvider:
    config: GenerationConfig

    @property
    def name(self) -> str:
        return "hf"

    @property
    def model(self) -> str:
        return self.config.model

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:  # pragma: no cover - optional runtime dependency.
            raise LLMProviderUnavailable(
                "huggingface_hub is not installed; install requirements.txt or set "
                "LLM_PROVIDER=disabled."
            ) from exc

        client = InferenceClient(
            model=self.config.model,
            provider=self.config.hf_provider,
            token=self.config.token,
            timeout=self.config.timeout_seconds,
        )
        max_tokens = max_tokens or self.config.max_tokens
        temperature = self.config.temperature if temperature is None else temperature

        last_error: Exception | None = None
        attempts = max(1, self.config.retries + 1)
        for attempt in range(attempts):
            try:
                return _strip_generation(
                    _chat_completion(
                        client,
                        prompt,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                )
            except Exception as exc:  # pragma: no cover - network/provider dependent.
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(2.0, 0.4 * (attempt + 1)))

        try:
            return _strip_generation(
                _text_generation(
                    client,
                    prompt,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )
        except Exception as exc:  # pragma: no cover - network/provider dependent.
            raise LLMProviderUnavailable(
                f"HF generation failed for {self.config.model}: {last_error or exc}"
            ) from exc


def get_provider(config: GenerationConfig | None = None) -> DisabledLLMProvider | HFInferenceProvider:
    config = config or GenerationConfig.from_env()
    provider = config.provider.lower().strip()
    if provider in {"", "none", "off", "disabled", "deterministic"}:
        return DisabledLLMProvider()
    if provider in {"hf", "huggingface", "huggingface_hub"}:
        return HFInferenceProvider(config)
    raise LLMProviderUnavailable(f"Unknown LLM_PROVIDER {config.provider!r}; expected hf or disabled.")


def _chat_completion(
    client: Any,
    prompt: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat_completion(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return _extract_chat_content(response)


def _text_generation(
    client: Any,
    prompt: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float,
) -> str:
    formatted = f"{system.strip()}\n\n{prompt}" if system else prompt
    response = client.text_generation(
        formatted,
        max_new_tokens=max_tokens,
        temperature=temperature,
        return_full_text=False,
    )
    return str(response)


def _extract_chat_content(response: Any) -> str:
    choices = _get(response, "choices") or []
    if not choices:
        raise LLMProviderUnavailable("HF chat response did not include choices.")
    first = choices[0]
    message = _get(first, "message")
    content = _get(message, "content") if message is not None else _get(first, "text")
    if isinstance(content, list):
        content = "".join(str(_get(part, "text") or _get(part, "content") or part) for part in content)
    if not content:
        raise LLMProviderUnavailable("HF chat response did not include message content.")
    return str(content)


def _strip_generation(value: str) -> str:
    text = value.strip()
    if not text:
        raise LLMProviderUnavailable("LLM provider returned an empty response.")
    return text


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value
    return None


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return float(value)
