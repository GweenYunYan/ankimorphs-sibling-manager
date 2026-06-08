import json
import os
from typing import Any

# __file__ is a built-in Python variable - the path to this exact file
# os.path.dirname(__file__) fives us the folder containing it,
# which is the addon folder itself.

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def get_config() -> dict[str, Any]:
    """Reads and returns the addon config from config.json"""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(new_config: dict[str, Any]) -> None:
    """
       Writes a new config dict to config.json.
       ensure_ascii=False preserves Chinese characters as-is instead of
       writing them as unicode escape sequences.
    """
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(new_config, f, ensure_ascii=False, indent=2)

def get_decks() -> list[str]:
    return get_config().get("decks", ["中文"])

def get_tags() -> dict[str, str]:
    return get_config().get(
        "tags",
        {
            "auto_tag": "AM-sm::reviewed-sibling",
            "promote_tag": "AM-sm::promote",
            "never_promote_tag": "AM-sm::never-promote"
        }
    )

def get_daily_limit() -> int:
    return int(get_config().get("daily_limit", 10))

def is_enabled() -> bool:
    return get_config().get("enabled", True)