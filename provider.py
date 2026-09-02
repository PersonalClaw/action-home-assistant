"""The action-home-assistant action provider.

Fires a Home Assistant **webhook** as a trigger action, via ``ActionProvider``
from ``personalclaw.sdk.action``. Bind it to any trigger and your automation
reaches the house: HA's webhook automations
(``POST {base_url}/api/webhook/{webhook_id}``) carry no separate auth — the
webhook id IS the credential, which is why it lives in the app's settings and
never in per-action config committed to trigger definitions.

Design notes worth copying into your own provider:

- **Validate, don't raise.** A missing/unknown field produces an
  ``ActionResult(success=False, error=…)``; raising is what MISBEHAVING
  providers do (core wraps it, but the envelope is better when you own it).
- **No dry-run claim.** This is a deterministic provider with real side
  effects and no observe mode, so ``supports_dry_run`` stays ``False`` and the
  dispatcher records a preview instead of executing (T9 honesty).
- **No reversal claim.** Firing a webhook cannot be taken back, so
  ``ActionResult.reversal`` stays empty and no undo is offered.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from personalclaw.sdk.action import ActionContext, ActionProvider, ActionResult

logger = logging.getLogger("action_home_assistant")


class ActionHomeAssistantProvider(ActionProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = dict(config or {})
        self._timeout = int(self._config.get("timeout_secs", 20))
        self._base_url = str(self._config.get("base_url", "") or "").rstrip("/")

    # ── Identity ──────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "action-home-assistant"

    @property
    def display_name(self) -> str:
        return "Home Assistant Webhook"

    # ── Contract ──────────────────────────────────────────────────────────

    async def execute(
        self,
        action_config: dict[str, Any],
        ctx: ActionContext,
        timeout: int = 30,
    ) -> ActionResult:
        """POST the webhook named by ``action_config["webhook_id"]``.

        Optional ``action_config["payload"]`` (an object) is sent as the JSON
        body; the triggering event's text rides along as ``event_text`` unless
        the payload already claims that key.
        """
        started = time.monotonic()
        if not self._base_url:
            return self._error("no base_url configured — set it in the app's settings")
        webhook_id = str(action_config.get("webhook_id", "") or "").strip()
        if not webhook_id:
            return self._error("action config needs a webhook_id")
        payload = action_config.get("payload") or {}
        if not isinstance(payload, dict):
            return self._error("payload must be an object when provided")
        body = dict(payload)
        body.setdefault("event_text", getattr(ctx, "event", "") or "")

        url = f"{self._base_url}/api/webhook/{urllib.parse.quote(webhook_id, safe='')}"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        effective_timeout = min(self._timeout, timeout) if timeout else self._timeout
        try:
            with urllib.request.urlopen(request, timeout=effective_timeout) as response:
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            return self._error(
                f"Home Assistant answered HTTP {exc.code} for webhook {webhook_id!r}",
                started,
            )
        except (urllib.error.URLError, OSError) as exc:
            return self._error(f"could not reach Home Assistant: {exc}", started)

        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("fired HA webhook %s (HTTP %s)", webhook_id, status)
        return ActionResult(
            success=True,
            exit_code=0,
            stdout=f"webhook {webhook_id} fired (HTTP {status})",
            duration_ms=duration_ms,
        )

    @staticmethod
    def _error(message: str, started: float | None = None) -> ActionResult:
        duration_ms = int((time.monotonic() - started) * 1000) if started else 0
        return ActionResult(
            success=False, exit_code=1, error=message, duration_ms=duration_ms
        )


def create_provider(config: dict[str, Any] | None = None) -> ActionHomeAssistantProvider:
    """Manifest factory — core calls this with this app's saved settings."""
    return ActionHomeAssistantProvider(config)
