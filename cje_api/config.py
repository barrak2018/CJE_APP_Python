import json
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "database": {
        "user": "postgres",
        "host": "localhost",
        "port": "5432",
        "name": "CJE",
    },
    "auth": {
        "api_user": "admin",
        "token_expire_minutes": "1440",
    },
    "api": {
        "host": "127.0.0.1",
        "port": "8000",
        "reload": True,
        "url": "http://127.0.0.1:8000",
    },
}

# Valores que nunca deben usarse en producción: obligan a configurar los secretos
# reales en config.json o en variables de entorno antes de arrancar.
PLACEHOLDER_SECRETS = {
    "cambiar",
    "generar-clave-aleatoria",
    "dev-secret-cambiar-en-produccion",
}

# Secretos sin valor por defecto: si faltan o quedan como placeholder, la app se niega a arrancar.
REQUIRED_SECRETS = [
    ("database", "password"),
    ("auth", "api_password"),
    ("auth", "secret_key"),
]

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


def require_secret(section: str, key: str) -> str:
    """Devuelve el secreto requerido o lanza un error claro si falta o es placeholder.

    Los secretos (contraseña de BD, credenciales de la API, clave JWT) no tienen
    valores por defecto en el código. Si no se definen en config.json o en la
    variable de entorno correspondiente, la app debe detenerse (fail-fast) en
    lugar de arrancar con credenciales inseguras.
    """
    value = get_setting(section, key)
    if not value or str(value).strip().lower() in PLACEHOLDER_SECRETS:
        env_name = ENV_MAP.get(section, {}).get(key)
        hint = f"en la variable de entorno '{env_name}'" if env_name else "por variable de entorno"
        raise RuntimeError(
            f"[config] Falta el secreto requerido '{section}.{key}'. "
            f"Defínelo en '{config_path()}' o {hint}."
        )
    return str(value)
