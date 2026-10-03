"""ha_safety._is_local_address and the URL checks in check_token_transport.

The HA token may only go over plaintext to this machine; these tests pin
how "this machine" is decided, with the socket layer stubbed out.
"""

import socket

import pytest

import ha_safety


class _FakeSock:
    """UDP socket whose 'source address' is fixed by the test."""

    source = "192.168.1.10"
    fail = False
    connected = []

    def __init__(self, family, kind):
        self.family = family

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self, addr):
        if _FakeSock.fail:
            raise OSError("network unreachable")
        _FakeSock.connected.append((self.family, addr))

    def getsockname(self):
        return (_FakeSock.source, 0)


@pytest.fixture
def fake_socket(monkeypatch):
    monkeypatch.setattr(_FakeSock, "fail", False)
    monkeypatch.setattr(_FakeSock, "connected", [])
    monkeypatch.setattr(_FakeSock, "source", "192.168.1.10")
    monkeypatch.setattr(socket, "socket", _FakeSock)
    return _FakeSock


@pytest.mark.parametrize("ip", ["127.0.0.1", "127.8.8.8", "::1"])
def test_loopback_is_local_without_touching_the_network(ip, fake_socket):
    assert ha_safety._is_local_address(ip) is True
    assert fake_socket.connected == []


@pytest.mark.parametrize("bad", ["", "not-an-ip", "999.1.1.1", "localhost"])
def test_non_addresses_are_not_local(bad, fake_socket):
    assert ha_safety._is_local_address(bad) is False


def test_own_address_is_local(fake_socket):
    assert ha_safety._is_local_address("192.168.1.10") is True
    assert fake_socket.connected == [(socket.AF_INET, ("192.168.1.10", 9))]


def test_other_machine_is_not_local(fake_socket):
    assert ha_safety._is_local_address("192.168.1.99") is False


def test_ipv6_scope_is_ignored_and_uses_inet6(fake_socket):
    fake_socket.source = "fe80::1"
    assert ha_safety._is_local_address("fe80::1%eth0") is True
    assert fake_socket.connected[-1][0] == socket.AF_INET6


def test_unroutable_address_fails_closed(fake_socket):
    fake_socket.fail = True
    assert ha_safety._is_local_address("10.0.0.5") is False


def test_unparseable_url_is_refused():
    ok, reason = ha_safety.check_token_transport("http://[::1")
    assert ok is False and reason == "unparseable URL"


@pytest.mark.parametrize("url", ["http:///api", "ws://:8123/api/websocket"])
def test_plaintext_url_without_host_is_refused(url):
    assert ha_safety.check_token_transport(url) == (False, "no host")


def test_encrypted_url_without_host_is_refused():
    assert ha_safety.check_token_transport("https:///api") == (False, "no host")


def test_empty_or_none_url_is_refused():
    assert ha_safety.check_token_transport(None)[0] is False
    assert ha_safety.check_token_transport("")[0] is False
