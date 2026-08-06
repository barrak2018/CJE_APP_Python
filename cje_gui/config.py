import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_CONFIG = PROJECT_ROOT / "cje_api" / "config.json"

DEFAULTS = {
    "api": {
        "url": "http://127.0.0.1:8000",
    },
}

ENV_MAP = {
    "api": {
        "url": "CJE_API_URL",
    },
}

_CACHE = {}


def config_path() -> Path:
    env_path = os.environ.get("CJE_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return API_CONFIG


def _file_data() -> dict:
    path = config_path()
    if path in _CACHE:
        return _CACHE[path]
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            data = raw
    except (OSError, ValueError):
        data = {}
    _CACHE[path] = data
    return data


def get_setting(section: str, key: str):
    env_name = ENV_MAP.get(section, {}).get(key)
    if env_name:
        value = os.environ.get(env_name)
        if value is not None:
            return value
    file_data = _file_data()
    if key in file_data.get(section, {}):
        return file_data[section][key]
    return DEFAULTS.get(section, {}).get(key)
