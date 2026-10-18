"""Translation files: strings.json is the source of truth for the UI."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import SENSOR_KEYS

COMPONENT_DIR = (
    Path(__file__).resolve().parents[1] / "custom_components" / "fuelusagetracker"
)


def _key_tree(node, prefix: str = "") -> set[str]:
    """Every key path of a JSON document, values dropped."""
    keys: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.add(path)
            keys |= _key_tree(value, path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            keys |= _key_tree(value, f"{prefix}[{index}]")
    return keys


def _load(name: str):
    return json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))


def test_strings_json_is_byte_identical_to_the_english_translation():
    assert (COMPONENT_DIR / "strings.json").read_bytes() == (
        COMPONENT_DIR / "translations" / "en.json"
    ).read_bytes()


def test_strings_and_hr_translation_share_the_key_tree():
    assert _key_tree(_load("strings.json")) == _key_tree(_load("translations/hr.json"))


def test_every_sensor_key_has_a_translated_name():
    names = _load("strings.json")["entity"]["sensor"]

    for key in SENSOR_KEYS:
        assert names.get(key, {}).get("name"), f"entity.sensor.{key}.name is missing"
