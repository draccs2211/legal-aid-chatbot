"""Prove the guards in conftest.py: no real key, no outside network, in any test."""
import os
import socket

import httpx
import openai
import pytest
from dotenv import load_dotenv

import config
import sarvam_client
import sarvam_speech
from conftest import API_KEY_NAMES, NetworkBlocked


@pytest.mark.parametrize("name", API_KEY_NAMES)
def test_api_keys_are_blank_in_the_environment(name):
    assert os.environ[name] == ""


def test_api_keys_are_blank_in_every_module_that_copies_them():
    assert config.SARVAM_API_KEY == "" and config.GROQ_API_KEY == ""
    assert sarvam_client.SARVAM_API_KEY == ""
    assert sarvam_client.GROQ_API_KEY == ""
    assert sarvam_client.OPENAI_API_KEY == ""
    assert sarvam_speech.SARVAM_API_KEY == ""


def test_a_dotenv_file_with_keys_cannot_override_the_blanks(tmp_path):
    # Same call config.py makes, pointed at a fake .env with fake keys.
    fake_env = tmp_path / ".env"
    fake_env.write_text("SARVAM_API_KEY=fake-sarvam\nGROQ_API_KEY=fake-groq\nOPENAI_API_KEY=fake-openai\n")
    load_dotenv(fake_env)
    assert all(os.environ[name] == "" for name in API_KEY_NAMES)


def test_raw_socket_to_an_outside_address_is_blocked():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        with pytest.raises(NetworkBlocked):
            s.connect(("8.8.8.8", 443))


def test_dns_lookup_of_an_outside_host_is_blocked():
    with pytest.raises(NetworkBlocked):
        socket.getaddrinfo("api.sarvam.ai", 443)


def test_httpx_cannot_reach_a_provider():
    with pytest.raises(NetworkBlocked):
        httpx.get("https://api.sarvam.ai/v1/models", timeout=2)


def test_openai_sdk_cannot_reach_a_provider():
    client = openai.OpenAI(api_key="fake", base_url="https://api.groq.com/openai/v1", max_retries=0)
    # NetworkBlocked is not an OSError, so the SDK does not mistake it for a
    # normal outage and retry; it surfaces as is.
    with pytest.raises(NetworkBlocked):
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])


def test_loopback_is_still_allowed():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2):
            pass
