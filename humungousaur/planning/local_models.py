from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request
from typing import Any


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
PREFERRED_OLLAMA_MODELS = (
    "qwen2.5:7b",
    "qwen2.5:7b-instruct",
    "llama3.2:3b",
    "qwen2.5:3b",
)


@dataclass(frozen=True, slots=True)
class LocalMemoryInfo:
    total_bytes: int
    available_bytes: int


def ollama_base_url() -> str:
    base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("LOCAL_LLM_BASE_URL") or OLLAMA_BASE_URL
    return base.rstrip("/").removesuffix("/v1")


def ollama_available(timeout_seconds: float = 1.5) -> bool:
    return bool(list_ollama_models(timeout_seconds=timeout_seconds))


def list_ollama_models(timeout_seconds: float = 2.5) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{ollama_base_url()}/api/tags", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []
    models = payload.get("models", []) if isinstance(payload, dict) else []
    return [model for model in models if isinstance(model, dict)]


def recommended_ollama_model(default: str = "llama3.2:3b") -> str:
    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        return env_model
    models = list_ollama_models()
    installed = {str(model.get("name") or model.get("model") or ""): model for model in models}
    memory = local_memory_info()
    if _can_run_7b(memory):
        for name in PREFERRED_OLLAMA_MODELS:
            if name in installed:
                return name
    for name in ("llama3.2:3b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:7b-instruct"):
        if name in installed:
            return name
    return next(iter(installed), default)


def local_memory_info() -> LocalMemoryInfo:
    if os.name == "nt":
        return _windows_memory_info()
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        return LocalMemoryInfo(total_bytes=int(page_size * pages), available_bytes=int(page_size * available_pages))
    except (AttributeError, OSError, ValueError):
        return LocalMemoryInfo(total_bytes=0, available_bytes=0)


def _can_run_7b(memory: LocalMemoryInfo) -> bool:
    if memory.total_bytes <= 0:
        return True
    total_gb = memory.total_bytes / (1024**3)
    available_gb = memory.available_bytes / (1024**3)
    return total_gb >= 12 and (available_gb >= 3 or available_gb == 0)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_memory_info() -> LocalMemoryInfo:
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return LocalMemoryInfo(total_bytes=int(status.ullTotalPhys), available_bytes=int(status.ullAvailPhys))
    return LocalMemoryInfo(total_bytes=0, available_bytes=0)
