"""Shared fakes for the LLM provider client (no network, no keys).

sarvam_client._get_client returns an async OpenAI client used as
`async with client: await client.chat.completions.create(...)`. Tests write a
plain function `create(**kwargs)` that returns a reply or raises, and wrap it:

    monkeypatch.setattr(sarvam_client, "_get_client", lambda *a, **k: fake_client(create))
"""


def completion(content):
    """A minimal chat completion with `content` as the answer."""
    msg = type("Msg", (), {"content": content})()
    return type("Completion", (), {"choices": [type("Choice", (), {"message": msg})()]})()


class _Completions:
    def __init__(self, create):
        self._create = create

    async def create(self, **kwargs):
        # Runs the test's plain function inside the event loop; blocking in it
        # (sleep, Event.wait) blocks exactly like a slow provider would.
        return self._create(**kwargs)


class _Chat:
    def __init__(self, create):
        self.completions = _Completions(create)


class FakeClient:
    def __init__(self, create):
        self.chat = _Chat(create)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def fake_client(create):
    return FakeClient(create)
