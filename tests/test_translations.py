"""Translation files: strings.json is the source of truth for the UI."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.fuelusagetracker import const
from tests.helpers import SENSOR_KEYS

COMPONENT_DIR = (
    Path(__file__).resolve().parents[1] / "custom_components" / "fuelusagetracker"
)

#: Everything that must stay in translation parity.
TRANSLATIONS = ("strings.json", "translations/en.json", "translations/hr.json")


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


def test_reconfigure_translations_exist_in_every_translation():
    for name in TRANSLATIONS:
        config = _load(name)["config"]
        assert config["step"]["reconfigure"]["title"], name
        assert config["abort"]["reconfigure_successful"], name
        assert config["error"]["name_exists"], name


def test_the_options_flow_translation_block_is_gone():
    """The reconfigure wizard replaced the options flow, block and all."""
    for name in TRANSLATIONS:
        assert "options" not in _load(name), name


def test_the_swapped_sensor_key_is_translated_everywhere():
    for name in TRANSLATIONS:
        names = _load(name)["entity"]["sensor"]
        assert names.get(const.SENSOR_DISTANCE_TO_LAST_FILL, {}).get("name"), name
        assert "km_since_last_fill" not in names, name


def test_the_consumed_sensor_keys_are_translated_everywhere():
    for name in TRANSLATIONS:
        names = _load(name)["entity"]["sensor"]
        for key in (const.SENSOR_CONSUMED_LITERS, const.SENSOR_CONSUMED_COST):
            assert names.get(key, {}).get("name"), f"{name}: entity.sensor.{key}.name"
