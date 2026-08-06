import json
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "database": {
        "user": "postgres",
        "password": "Strider-1",
        "host": "localhost",
        "port": "5432",
        "name": "CJE",
    },
    "auth": {
        "api_user": "admin",
        "api_password": "admin123",
        "secret_key": "dev-secret-cambiar-en-produccion",
        "token_expire_minutes": "1440",
    },
    "api": {
        "host": "127.0.0.1",
        "port": "8000",
        "reload": True,
        "url": "http://127.0.0.1:8000",
    },
}

ENV_MAP = {
    "database": {
        "user": "CJE_DB_USER",
        "password": "CJE_DB_PASSWORD",
        "host": "CJE_DB_HOST",
        "port": "CJE_DB_PORT",
        "name": "CJE_DB_NAME",
    },
    "auth": {
        "api_user": "CJE_API_USER",
        "api_password": "CJE_API_PASSWORD",
        "secret_key": "CJE_SECRET_KEY",
        "token_expire_minutes": "CJE_TOKEN_EXPIRE_MINUTES",
    },
    "api": {
        "url": "CJE_API_URL",
    },
}

_CACHE = {}


def config_path() -> Path:
    env_path = os.environ.get("CJE_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return API_DIR / "config.json"


def _file_data() -> dict:
    path = config_path()
    if path in _CACHE:
        return _CACHE[path]
    data = {}
    if not path.exists():
        print(f"[config] No se encontró '{path}'; usando valores por defecto.",
              file=sys.stderr)
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = raw
            else:
                raise ValueError("el contenido debe ser un objeto JSON")
        except (OSError, ValueError) as e:
            print(f"[config] Error leyendo '{path}': {e}; usando valores por defecto.",
                  file=sys.stderr)
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
