# Tests

End-to-end test that loads the integration inside a real Home Assistant
instance (via `pytest-homeassistant-custom-component`) and drives the full
path: config flow → entry setup → coordinator → entities → services → unload.

The HTTP responses from the receiver are mocked using **real payloads captured
from a live box** (`tests/fixtures/*.json`), so the test is deterministic while
still exercising realistic data shapes.

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install homeassistant pytest-homeassistant-custom-component
pytest
```

## What it asserts

- The integration loads and is discoverable by Home Assistant.
- The config flow validates the connection and creates a config entry
  (device titled from `/api/about`, unique id from the box MAC).
- The entry sets up and reaches the `LOADED` state.
- All entities are created with sensible values:
  current programme, next programme, timers, recordings, recording, standby.
- All services are registered: `zap`, `send_message`, `remote_control`,
  `add_timer`, `toggle_standby`, and a `zap` call executes.
- The entry unloads cleanly.
