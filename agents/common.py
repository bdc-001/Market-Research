"""
Common utilities for the agent ecosystem.

Primary LLM: Meta muse-spark-1.2 via POST /v1/responses.
Backup LLM:  NVIDIA Nemotron 3.5 Lightning via integrate.api.nvidia.com.
`generate_content(prompt).text` matches the old Gemini surface so agents
do not need to change.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict

import requests

PRIMARY_MODEL = "muse-spark-1.2"
BACKUP_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
# Same NVIDIA key; Lightning is currently DEGRADED on NIM (400).
NVIDIA_FALLBACK_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
NVIDIA_MODELS = (BACKUP_MODEL, NVIDIA_FALLBACK_MODEL)
MODEL_NAME = PRIMARY_MODEL

META_RESPONSES_URL = "https://api.meta.ai/v1/responses"

# Updated after each successful generate_content call.
LAST_MODEL_USED = PRIMARY_MODEL
LAST_PROVIDER = "meta"


_SECRETS_CACHE: dict[str, str] | None = None


def _file_secrets() -> dict[str, str]:
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None:
        return _SECRETS_CACHE
    loaded: dict[str, str] = {}
    try:
        import tomllib
        path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
        if path.exists():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(value, str):
                    loaded[key] = value
                elif isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, str):
                            loaded[nested_key] = nested_value
    except Exception:
        loaded = {}
    _SECRETS_CACHE = loaded
    return loaded


def _secret(name: str) -> str:
    val = os.getenv(name, "")
    if val:
        return val
    val = _file_secrets().get(name, "")
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(name, "") or "")
    except Exception:
        return ""


def get_api_key() -> str:
    key = _secret("MODEL_API_KEY") or _secret("META_API_KEY")
    if not key:
        raise ValueError(
            "MODEL_API_KEY not found. Add it to .streamlit/secrets.toml "
            "or the environment (Meta Model API bearer token)."
        )
    return key


def get_nvidia_api_key() -> str:
    return _secret("NVIDIA_API_KEY") or _secret("NGC_API_KEY")


def _system_instruction(with_memory: bool) -> str | None:
    if not with_memory:
        return None
    try:
        from agents.memory import system_instruction
        return system_instruction()
    except Exception:
        return None


def _extract_output_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in (None, "message"):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                chunks.append(str(part.get("text") or ""))
    return "\n".join(c for c in chunks if c).strip()


class _ModelReply:
    def __init__(self, text: str):
        self.text = text


def _mark_used(provider: str, model: str) -> None:
    global LAST_PROVIDER, LAST_MODEL_USED
    LAST_PROVIDER = provider
    LAST_MODEL_USED = model


class MetaModel:
    """Drop-in for google.generativeai GenerativeModel."""

    def __init__(self, instructions: str | None = None):
        self.instructions = instructions or None

    def generate_content(self, prompt: str) -> _ModelReply:
        payload: dict[str, Any] = {
            "model": PRIMARY_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": str(prompt or "")},
                    ],
                }
            ],
            "stream": False,
            "store": False,
        }
        if self.instructions:
            payload["instructions"] = self.instructions

        resp = requests.post(
            META_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {get_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"error": resp.text[:800]}
        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else data
            raise RuntimeError(f"Meta API {resp.status_code}: {err}")
        text = _extract_output_text(data) if isinstance(data, dict) else ""
        if not text:
            raise RuntimeError("Meta API returned an empty response")
        _mark_used("meta", PRIMARY_MODEL)
        return _ModelReply(text)


def _nvidia_should_try_next(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "not found",
        "404",
        "degraded",
        "410",
        "end of life",
        "cannot be invoked",
        "timeout",
        "timed out",
    )
    return any(m in text for m in markers)


class NvidiaModel:
    """NVIDIA NIM chat completions via the OpenAI-compatible SDK."""

    def __init__(self, instructions: str | None = None):
        self.instructions = instructions or None

    def generate_content(self, prompt: str) -> _ModelReply:
        key = get_nvidia_api_key()
        if not key:
            raise ValueError(
                "NVIDIA_API_KEY not found. Add it to .streamlit/secrets.toml "
                "for the Nemotron backup."
            )

        from openai import OpenAI

        messages: list[dict[str, str]] = []
        if self.instructions:
            messages.append({"role": "system", "content": self.instructions})
        messages.append({"role": "user", "content": str(prompt or "")})

        last_error: Exception | None = None
        for model in NVIDIA_MODELS:
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=key,
                timeout=20.0 if model == BACKUP_MODEL else 300.0,
            )
            try:
                return self._stream(client, model, messages)
            except Exception as exc:
                last_error = exc
                if model != NVIDIA_MODELS[-1] and _nvidia_should_try_next(exc):
                    print(f"NVIDIA {model} unavailable ({exc}); trying {NVIDIA_MODELS[-1]}")
                    continue
                raise
        raise last_error or RuntimeError("NVIDIA API failed")

    def _stream(self, client, model: str, messages: list[dict[str, str]]) -> _ModelReply:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 16384,
            },
            stream=True,
        )

        parts: list[str] = []
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                parts.append(str(content))

        text = "".join(parts).strip()
        if not text:
            raise RuntimeError(f"NVIDIA {model} returned an empty response")
        _mark_used("nvidia", model)
        return _ModelReply(text)


class FallbackModel:
    """Try Meta first; on failure use NVIDIA Nemotron."""

    def __init__(self, instructions: str | None = None):
        self.instructions = instructions or None
        self.primary = MetaModel(instructions)
        self.backup = NvidiaModel(instructions)

    def generate_content(self, prompt: str) -> _ModelReply:
        meta_key = bool(_secret("MODEL_API_KEY") or _secret("META_API_KEY"))
        nvidia_key = bool(get_nvidia_api_key())

        if meta_key:
            try:
                return self.primary.generate_content(prompt)
            except Exception as exc:
                if not nvidia_key:
                    raise
                print(f"Meta LLM failed ({exc}); falling back to NVIDIA Nemotron")

        if nvidia_key:
            return self.backup.generate_content(prompt)

        raise ValueError(
            "No LLM key found. Add MODEL_API_KEY (Meta) and/or "
            "NVIDIA_API_KEY to .streamlit/secrets.toml."
        )


def setup_gemini(with_memory: bool = True):
    """
    Returns the shared LLM client: Meta muse-spark-1.2, with NVIDIA
    Nemotron as backup. System instructions are GEMINI.md plus learned
    rules unless with_memory=False.
    """
    return FallbackModel(instructions=_system_instruction(with_memory))


def clean_json(text: str) -> Dict[str, Any]:
    """Extracts JSON from markdown fences."""
    try:
        if "```json" in text:
            raw = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            raw = text.split("```")[1].split("```")[0].strip()
        else:
            raw = text.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ JSON Parse Error: {e}")
        return {}


class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.model = setup_gemini()
        self.last_raw = ""
        self.last_prose = ""
        self.last_parsed = None
        self.last_snapshot = None

    def complete(self, prompt: str) -> str:
        """
        One model call: human prose plus a JSON prediction appendix.
        Returns prose only so downstream prompts and the UI stay readable.
        """
        from agents.prediction_format import (
            JSON_APPENDIX, UNKNOWN_PREDICTION, parse_dual_output,
        )
        try:
            response = self.model.generate_content(prompt + JSON_APPENDIX)
            raw = (response.text or "") if response is not None else ""
        except Exception as exc:
            raw = f"Generation failed: {exc}"
        self.last_raw = raw
        prose, parsed = parse_dual_output(raw)
        self.last_prose = prose
        self.last_parsed = parsed or dict(UNKNOWN_PREDICTION)
        return prose

    def record_failure(self, message: str) -> str:
        from agents.prediction_format import UNKNOWN_PREDICTION
        self.last_raw = message
        self.last_prose = message
        self.last_parsed = dict(UNKNOWN_PREDICTION)
        return message

    def run(self, context: str) -> str:
        """Executes the agent's core task."""
        raise NotImplementedError
