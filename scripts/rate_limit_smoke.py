from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import _reset_rate_limiter_for_tests, advise_api


def _set_env(key: str, value: str, previous: dict[str, str | None]) -> None:
    previous[key] = os.environ.get(key)
    os.environ[key] = value


def _restore(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def main() -> None:
    previous: dict[str, str | None] = {}
    _set_env("ADVISOR_LATENCY_PROFILE", "quality", previous)
    _set_env("LLM_PROVIDER", "disabled", previous)
    _set_env("RATE_LIMIT_ENABLED", "true", previous)
    _set_env("RATE_LIMIT_MAX_REQUESTS", "1", previous)
    _set_env("RATE_LIMIT_WINDOW_SECONDS", "60", previous)
    try:
        _reset_rate_limiter_for_tests()
        advise_api("Build an internal API docs assistant over fast-moving SDK docs.")
        try:
            advise_api("Build an internal API docs assistant over fast-moving SDK docs.")
        except RuntimeError as exc:
            if "Rate limit exceeded" not in str(exc):
                raise
        else:
            raise AssertionError("rate limiter did not reject the second request")
    finally:
        _reset_rate_limiter_for_tests()
        _restore(previous)

    print("rate_limit_smoke=ok")


if __name__ == "__main__":
    main()
