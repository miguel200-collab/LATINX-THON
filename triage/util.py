"""Small helpers: a hard timeout around any API call, and millisecond timing."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable


class ApiTimeout(Exception):
    """An API call did not answer within the allowed time."""


def call_with_timeout(fn: Callable[..., Any], timeout_s: float, *args: Any, **kwargs: Any) -> Any:
    """Run fn(*args, **kwargs); raise ApiTimeout if it takes longer than timeout_s seconds.

    The SDKs have their own HTTP timeouts; this is an outer guard so the pipeline can
    always fall back to the safety hold within a known time.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout as exc:
        raise ApiTimeout(f"no response within {timeout_s:.1f}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def now() -> float:
    return time.perf_counter()


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 1)


def mask_secrets(message: str, *secrets: str | None) -> str:
    """Remove API key values from any message before it is logged or shown."""
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message
