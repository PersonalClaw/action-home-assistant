"""Contract + behaviour tests for the action-home-assistant provider.

Contract: personalclaw.sdk.action:ActionProvider

No network: behaviour tests stub ``urllib.request.urlopen`` at the module seam.
Community-validation note: these lock the request SHAPE (URL, method, JSON
body) against HA's documented webhook contract — no live instance required.
"""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error

import provider as ha_module
from personalclaw.sdk.action import ActionContext
from provider import ActionHomeAssistantProvider, create_provider


def _ctx(event: str = "app:watched-source-github:new_release") -> ActionContext:
    return ActionContext(event=event, context={}, payload={})


def _run(provider, config, ctx=None):
    return asyncio.run(provider.execute(config, ctx or _ctx()))


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── Contract shape ────────────────────────────────────────────────────────


def test_factory_returns_the_provider() -> None:
    assert isinstance(create_provider({}), ActionHomeAssistantProvider)


def test_factory_accepts_no_config() -> None:
    assert isinstance(create_provider(None), ActionHomeAssistantProvider)


def test_nothing_abstract_is_left() -> None:
    assert not getattr(ActionHomeAssistantProvider, "__abstractmethods__", frozenset())


def test_registers_under_the_app_name() -> None:
    assert create_provider({}).name == "action-home-assistant"


def test_deterministic_provider_claims_no_dry_run_and_no_reversal() -> None:
    p = create_provider({})
    assert p.supports_dry_run is False
    assert p.reversal_kinds == ()


# ── Validation: error results, never raises ──────────────────────────────


def test_missing_base_url_is_an_error_result() -> None:
    result = _run(create_provider({}), {"webhook_id": "x"})
    assert result.success is False
    assert "base_url" in result.error


def test_missing_webhook_id_is_an_error_result() -> None:
    result = _run(create_provider({"base_url": "http://ha.local:8123"}), {})
    assert result.success is False
    assert "webhook_id" in result.error


def test_non_object_payload_is_an_error_result() -> None:
    result = _run(
        create_provider({"base_url": "http://ha.local:8123"}),
        {"webhook_id": "x", "payload": "not-an-object"},
    )
    assert result.success is False
    assert "payload" in result.error


# ── The fire: URL shape + body ────────────────────────────────────────────


def test_fires_the_documented_webhook_url(monkeypatch) -> None:
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(ha_module.urllib.request, "urlopen", fake_urlopen)
    p = create_provider({"base_url": "http://ha.local:8123/"})
    result = _run(p, {"webhook_id": "morning lights", "payload": {"scene": "wake"}})
    assert result.success is True
    assert result.exit_code == 0
    assert seen["url"] == "http://ha.local:8123/api/webhook/morning%20lights"
    assert seen["method"] == "POST"
    assert seen["body"]["scene"] == "wake"
    assert seen["body"]["event_text"]  # the triggering event rode along


def test_payload_owns_event_text_when_it_claims_the_key(monkeypatch) -> None:
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(ha_module.urllib.request, "urlopen", fake_urlopen)
    p = create_provider({"base_url": "http://ha.local:8123"})
    _run(p, {"webhook_id": "w", "payload": {"event_text": "mine"}})
    assert seen["body"]["event_text"] == "mine"


# ── Failure mapping ───────────────────────────────────────────────────────


def test_http_error_maps_to_error_result(monkeypatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(ha_module.urllib.request, "urlopen", fake_urlopen)
    result = _run(create_provider({"base_url": "http://ha.local:8123"}), {"webhook_id": "w"})
    assert result.success is False
    assert "404" in result.error


def test_unreachable_host_maps_to_error_result(monkeypatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(ha_module.urllib.request, "urlopen", fake_urlopen)
    result = _run(create_provider({"base_url": "http://ha.local:8123"}), {"webhook_id": "w"})
    assert result.success is False
    assert "reach" in result.error
