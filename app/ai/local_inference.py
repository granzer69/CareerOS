from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Protocol

from app.core.config import settings

_BLOCKED_MODEL_SCHEMES: tuple[str, ...] = (
    "http://",
    "https://",
    "hf://",
    "s3://",
    "gs://",
)

_llama_cache: dict[str, object] = {}
_llama_thread_lock = threading.Lock()


class LocalModelNotFoundError(Exception):
    """Raised when configured local model weights are missing or not a file."""


class LocalInferenceError(Exception):
    """Raised when local inference cannot complete."""


class LocalInferenceAdapter(Protocol):
    async def complete(self, prompt: str) -> str:
        """Return raw completion text for a local weight file already on disk."""


def require_local_model_file(model_path: str) -> Path:
    """
    Validate that model_path is a local regular file.

    Does not download weights and does not import llama_cpp.
    """
    stripped = model_path.strip()
    if not stripped:
        raise LocalModelNotFoundError("LOCAL_MODEL_PATH is not set")

    lowered = stripped.lower()
    if any(lowered.startswith(scheme) for scheme in _BLOCKED_MODEL_SCHEMES):
        raise LocalModelNotFoundError("LOCAL_MODEL_PATH must be a local filesystem path")

    path = Path(stripped)
    if not path.is_file():
        raise LocalModelNotFoundError("Local model weights are not available")
    return path


def warm_local_model_weights() -> None:
    """
    Load GGUF weights into memory when configured.

    Called at API startup so the first analyze request is not blocked on load
    time behind a short reverse-proxy timeout.
    """
    try:
        adapter = build_local_adapter(settings.LOCAL_MODEL_PATH)
    except LocalModelNotFoundError:
        return
    if isinstance(adapter, LlamaCppAdapter):
        with _llama_thread_lock:
            adapter._load_llama()


def resolve_local_model_path(role: str = "default") -> str:
    """
    Resolve which on-disk GGUF path to use for a pipeline stage.

    Roles: default, jd (understanding + extraction), evidence (semantic matching).
    """
    if role == "jd":
        candidate = settings.LOCAL_MODEL_PATH_JD.strip() or settings.LOCAL_MODEL_PATH.strip()
    elif role == "evidence":
        candidate = settings.LOCAL_MODEL_PATH_EVIDENCE.strip() or settings.LOCAL_MODEL_PATH.strip()
    else:
        candidate = settings.LOCAL_MODEL_PATH.strip()
    return candidate


def build_local_adapter(model_path: str | None = None) -> LocalInferenceAdapter:
    """Build a local GGUF adapter after verifying the weight file exists."""
    path_str = (model_path or settings.LOCAL_MODEL_PATH).strip()
    path = require_local_model_file(path_str)
    return LlamaCppAdapter(
        model_path=path,
        n_ctx=settings.LOCAL_MODEL_CONTEXT,
        max_tokens=settings.LOCAL_MODEL_MAX_TOKENS,
        temperature=settings.LOCAL_MODEL_TEMPERATURE,
        timeout_seconds=settings.LOCAL_INFERENCE_TIMEOUT_SECONDS,
    )


class LlamaCppAdapter:
    """llama-cpp-python backend that loads an on-disk GGUF file only."""

    def __init__(
        self,
        *,
        model_path: Path,
        n_ctx: int,
        max_tokens: int,
        temperature: float,
        timeout_seconds: int,
    ) -> None:
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

    async def complete(self, prompt: str) -> str:
        """Generate completion text from the local GGUF file."""
        require_local_model_file(str(self._model_path))
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(self._complete_sync, prompt),
                timeout=self._timeout_seconds,
            )
        except LocalModelNotFoundError:
            raise
        except TimeoutError as exc:
            raise LocalInferenceError("Local inference timed out") from exc
        except LocalInferenceError:
            raise
        except Exception as exc:
            raise LocalInferenceError("Local inference failed") from exc

        if not text.strip():
            raise LocalInferenceError("Local inference returned empty output")
        return text

    def _load_llama(self) -> object:
        cache_key = str(self._model_path)
        cached = _llama_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise LocalInferenceError(
                "llama-cpp-python is not installed. See README for local model setup."
            ) from exc

        try:
            llm = Llama(
                model_path=str(self._model_path),
                n_ctx=self._n_ctx,
                n_gpu_layers=0,
                verbose=False,
            )
        except Exception as exc:
            raise LocalInferenceError("Failed to load local model weights") from exc

        _llama_cache[cache_key] = llm
        return llm

    def _complete_sync(self, prompt: str) -> str:
        with _llama_thread_lock:
            llm = self._load_llama()
            result = llm.create_completion(  # type: ignore[attr-defined]
                prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                echo=False,
            )
            choices = result.get("choices") or []
            if not choices:
                raise LocalInferenceError("Local inference returned no choices")
            text = choices[0].get("text")
            if not isinstance(text, str):
                raise LocalInferenceError("Local inference returned no text")
            return text
