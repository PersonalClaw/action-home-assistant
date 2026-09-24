# Home Assistant Webhook Action

A PersonalClaw **action** provider that fires a [Home Assistant webhook
automation](https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger)
— bind it to any trigger and your automation reaches the house. Implements
`ActionProvider` from `personalclaw.sdk.action`, stdlib-only.

## Setup

1. In Home Assistant, create an automation with a **webhook trigger**; note its
   webhook id.
2. Install this app (below) and set `base_url` in its settings.
3. Author a PersonalClaw trigger whose action uses this provider with
   `{"webhook_id": "<your id>"}`.

| App setting | Default | Meaning |
| --- | --- | --- |
| `base_url` | *(required)* | Your HA instance, e.g. `http://homeassistant.local:8123` |
| `timeout_secs` | `20` | HTTP timeout |

| Action config | Meaning |
| --- | --- |
| `webhook_id` | *(required)* — which HA webhook to fire |
| `payload` | optional JSON object sent as the body; the triggering event's text rides along as `event_text` unless the payload claims that key |

HA webhooks carry no separate auth — **the webhook id is the credential** —
which is why it belongs in settings/action config and never in code.

## Design notes worth copying into your own provider

- **Validate, don't raise.** Missing `base_url`/`webhook_id`, or a non-object
  payload, produce `ActionResult(success=False, error=…)` — raising is what
  misbehaving providers do.
- **No dry-run claim.** This provider is deterministic with real side effects
  and no observe mode, so `supports_dry_run` stays `False`; the dispatcher
  then previews instead of executing on dry runs.
- **No reversal claim.** A fired webhook cannot be taken back, so
  `ActionResult.reversal` stays empty and no undo is offered.

## Validation status

The test suite locks the request shape (URL, method, JSON body) against HA's
documented webhook contract with the HTTP seam stubbed — no live HA instance
required. Nobody has yet confirmed it against a **real** Home Assistant, so that
is the one claim this repo does not make. If you run it against yours, please say
so on [the validation tracking
issue](https://github.com/PersonalClaw/action-home-assistant/issues/1) — your HA
version and whether the automation fired is enough.

## Run the tests

```bash
pytest .
```

## Install it

From the dashboard: **Store → Add source**, point it at this repo's git URL (or
a local clone), then install and enable it.

## License

MIT
