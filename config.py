from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_url: str
    office_lat: float
    office_long: float
    emp_id: str
    password: str
    email: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_env_value(value.strip())

        if key and key not in os.environ:
            os.environ[key] = value


def get_config(env_file: str | Path = ".env") -> Config:
    load_dotenv(env_file)

    required_values = {
        "KVON_API_URL": os.getenv("KVON_API_URL"),
        "OFFICE_LAT": os.getenv("OFFICE_LAT"),
        "OFFICE_LONG": os.getenv("OFFICE_LONG"),
        "KVON_EMP_ID": os.getenv("KVON_EMP_ID"),
        "KVON_PASSWORD": os.getenv("KVON_PASSWORD"),
        "KVON_EMAIL": os.getenv("KVON_EMAIL"),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    }
    missing = [key for key, value in required_values.items() if not value]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    try:
        office_lat = float(required_values["OFFICE_LAT"])
        office_long = float(required_values["OFFICE_LONG"])
    except ValueError as exc:
        raise ConfigError("OFFICE_LAT and OFFICE_LONG must be valid numbers") from exc

    return Config(
        api_url=required_values["KVON_API_URL"].rstrip("/"),
        office_lat=office_lat,
        office_long=office_long,
        emp_id=required_values["KVON_EMP_ID"],
        password=required_values["KVON_PASSWORD"],
        email=required_values["KVON_EMAIL"],
        telegram_bot_token=required_values["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=required_values["TELEGRAM_CHAT_ID"],
    )


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
