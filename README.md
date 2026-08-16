# OpenWebif Control

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant integration for **Enigma2 / OpenWebif** set-top boxes
(Vu+, Dreambox, Zgemma, and similar running OpenViX, OpenATV, etc.).

It talks **directly to your receiver's OpenWebif HTTP API** — the same
interface the box's own web UI uses. There is **no third-party EPG source** and
no SSH: your receiver is the single source of truth for channels, EPG,
recordings and timers.

This integration is designed to **complement** Home Assistant's built-in
[`enigma2`](https://www.home-assistant.io/integrations/enigma2/) integration
(which provides a `media_player` for power, volume, now-playing and channel
zapping). OpenWebif Control adds the pieces the core integration doesn't:
current/next programme sensors, recording & timer state, a recordings list, and
control services — the data layer for a richer, "Sky Q-style" TV dashboard.

> **Status: v0.1 (data + control layer).** A polished Lovelace dashboard /
> custom EPG-grid card is planned for a later release. See [Roadmap](#roadmap).

---

## Features (v0.1)

**Sensors**

| Entity | Description |
| --- | --- |
| `sensor.*_current_programme` | Title of what's on the current channel now (+ description, channel, start/end as attributes) |
| `sensor.*_next_programme` | What's on next on the current channel |
| `sensor.*_timers` | Number of scheduled timers (full list in attributes) |
| `sensor.*_recordings` | Number of recordings on the box's storage (list with name/channel/size/description in attributes) |

**Binary sensors**

| Entity | Description |
| --- | --- |
| `binary_sensor.*_recording` | On while the receiver is actively recording |
| `binary_sensor.*_standby` | On while the receiver is in standby |

**Services**

| Service | What it does |
| --- | --- |
| `openwebif_control.zap` | Change to a channel by service reference |
| `openwebif_control.send_message` | Show an on-screen message on the TV |
| `openwebif_control.remote_control` | Send a remote-control key code |
| `openwebif_control.add_timer` | Schedule a recording from an EPG event id |
| `openwebif_control.toggle_standby` | Toggle standby on/off |

---

## Installation (HACS)

1. In Home Assistant, go to **HACS → three-dot menu → Custom repositories**.
2. Add this repository URL:
   `https://github.com/kevpatts/OpenWebif-control`
   and choose category **Integration**.
3. Find **OpenWebif Control** in HACS, install it, and **restart Home Assistant**.
4. Go to **Settings → Devices & Services → Add Integration**, search for
   **OpenWebif Control**, and enter your box's address.

### Manual installation

Copy `custom_components/openwebif_control/` into your Home Assistant
`config/custom_components/` directory and restart.

---

## Configuration

The integration is configured entirely through the UI (config flow):

- **Host** — the receiver's IP or hostname (e.g. `10.0.7.40`)
- **Port** — OpenWebif port (default `80`)
- **Username / Password** — only if you've set OpenWebif auth (leave blank if not)
- **Use HTTPS / Verify SSL** — for boxes exposed over TLS

After setup, open the integration's **Configure** (options) to pick a **default
bouquet** for EPG and adjust the **update interval**.

### Recommended companion

Install the core **Enigma2** integration too, pointed at the same box, for the
`media_player` entity (power/volume/zap/now-playing transport). OpenWebif
Control focuses on the data and extra control surface around it.

---

## Channel logos (picons)

For a Sky Q-style look you'll want channel logos. This integration surfaces the
box-served picon URL for each service. If your receiver doesn't have a picon
pack installed, picons will 404 — install a FreeSat/DVB picon pack on the box
(e.g. via the image's picon downloader, or OpenViX/OpenATV feeds). A helper to
fetch a picon pack is planned for a future release.

---

## A note on EPG

OpenWebif serves a full multi-day EPG **as long as the box has harvested it**.
If your receiver has been in **deep standby for a long time**, the EPG cache can
go stale and appear nearly empty. Waking the box and letting its EPG importer /
OpenTV harvester run (most images do this on a schedule) repopulates a full
~7-day guide. This integration reads whatever EPG the box currently has.

---

## Roadmap

- **v0.2** — Lovelace dashboard: channel-tile zapper, recordings gallery, and a
  Sky Q-style EPG grid; optional bundled custom card.
- **v0.x** — picon pack fetch helper; media_source for streaming recordings;
  per-bouquet EPG sensors.

---

## Development

This integration has no external Python requirements beyond Home Assistant
itself. The API client lives in
[`api.py`](custom_components/openwebif_control/api.py) and is a thin async
wrapper over the OpenWebif JSON endpoints.

## License

[MIT](LICENSE)
