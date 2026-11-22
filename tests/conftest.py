"""Test-wide guards: no real API key and no outside network in any test.

Why: backend/config.py calls load_dotenv() on import, and .env on the owner's
machine holds real keys. Without this file a test that forgot to blank a key
could make a real, paid, network call.

1. Keys: set to "" in os.environ HERE, at conftest import, which pytest does
   before importing any test module (and so before any backend module).
   load_dotenv() defaults to override=False, so it never replaces a variable
   that already exists, even an empty one; the real values never get in.
   An autouse fixture also blanks the module-level copies, in case a module
   was imported some other way.
2. Network: every socket connection or DNS lookup to a non-loopback address
   raises NetworkBlocked. Loopback stays allowed for local servers.
   FastAPI's TestClient runs in-process and does not use sockets.
"""
import ipaddress
import os
import socket
import sys

import pytest

API_KEY_NAMES = ("SARVAM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")

for _name in API_KEY_NAMES:
    os.environ[_name] = ""

# Chroma's anonymous telemetry would otherwise try the network.
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Modules that keep their own copy of a key at import time.
KEY_HOLDERS = {
    "config": ("SARVAM_API_KEY", "GROQ_API_KEY"),
    "sarvam_client": ("SARVAM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"),
    "sarvam_speech": ("SARVAM_API_KEY",),
}


class NetworkBlocked(RuntimeError):
    """Raised when a test tries to reach a non-loopback address."""


_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", ""}


def _is_loopback(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    host = str(host).strip("[]").lower()
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _check_address(address):
    # AF_UNIX addresses are strings or bytes paths; only inet tuples matter.
    if isinstance(address, tuple) and address and not _is_loopback(address[0]):
        raise NetworkBlocked(f"tests may not open network connections (tried {address[0]!r})")


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _guarded_connect(self, address):
    _check_address(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    _check_address(address)
    return _real_connect_ex(self, address)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_loopback(host):
        raise NetworkBlocked(f"tests may not resolve outside hosts (tried {host!r})")
    return _real_getaddrinfo(host, *args, **kwargs)


@pytest.fixture(autouse=True)
def _no_real_keys(monkeypatch):
    for name in API_KEY_NAMES:
        monkeypatch.setenv(name, "")
    for module_name, attrs in KEY_HOLDERS.items():
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for attr in attrs:
            if hasattr(module, attr):
                monkeypatch.setattr(module, attr, "")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
