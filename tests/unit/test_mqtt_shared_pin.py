"""The hub must ship the same MQTT protocol package it is tested with: the exact
commit of a release tag (currently v1.1.0, the tag the vault pins). Commits, not
tags, because a tag can be moved (see test_supply_chain_pins)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^central-core-mqtt-shared @ git\+https://github\.com/elyobelyob/central-core-mqtt-shared(?:\.git)?@(\S+)$", re.M)


def _pin(path):
    found = PIN.findall((ROOT / path).read_text())
    assert len(found) == 1, f"{path}: expected one central-core-mqtt-shared pin, found {found}"
    return found[0]


def test_should_pin_the_same_mqtt_shared_tag_for_tests_and_the_shipped_hub():
    shipped = _pin("central-core-hub/requirements.txt")
    tested = _pin("requirements.txt")
    assert shipped == tested
    assert re.fullmatch(r"[0-9a-f]{40}", shipped), "pin the full commit of a release tag"
