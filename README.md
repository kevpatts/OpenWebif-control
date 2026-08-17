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

> **Status: v0.5.x (data + control layer, with background EPG cache).** The
> companion Sky Q-style dashboard card is available:
> [OpenWebif Control Card](https://github.com/kevpatts/OpenWebif-control-card).

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
| `openwebif_control.get_epg` | Return a timeline EPG window for a bouquet (cached, windowed server-side) |
| `openwebif_control.play_recording` | Start playing a recording on the TV, optionally seeking to an approximate position |

---

## Receiver setup: disable the resume prompt

> **Required for `play_recording` to work reliably.** Do this once on the box.

When a movie/recording starts, Enigma2 can display an interactive
**“Resume from last position?”** dialog. That modal **blocks automated
playback and seeking** — the `play_recording` service (and the companion
card's ▶ Play / timeline scrubber) can't get past it. This integration
therefore **assumes the resume prompt is disabled** and does **not** try to
dismiss it; disable it once and playback starts cleanly every time.

**On the receiver (via its own on-screen menu / remote):**

1. **Menu → Setup → System → Recordings** (some images: **A/V settings** or
   **Recording paths / Playback**).
2. Find the movie **resume** behaviour option. Wording varies by image:
   - OpenViX / OpenATV: **“Ask about resuming a movie”** → set to **`no`**
     (equivalent settings key `config.usage.on_movie_start`).
   - Some images phrase it as **“Resume from last position” / “Behaviour when
     a movie is started”** → choose **“beginning”** or **“Do nothing”** rather
     than **“Ask user”**.
3. Save/exit. No reboot needed.

**Alternatively, over SSH (root):** the same setting is stored in
`/etc/enigma2/settings` as `config.usage.on_movie_start`. Set it to a
non-interactive value and restart Enigma2:

```sh
# Play recordings from the beginning, no prompt:
grep -q '^config.usage.on_movie_start=' /etc/enigma2/settings \
  && sed -i 's/^config.usage.on_movie_start=.*/config.usage.on_movie_start=beginning/' /etc/enigma2/settings \
  || echo 'config.usage.on_movie_start=beginning' >> /etc/enigma2/settings
init 4 && sleep 3 && init 3   # restart Enigma2 (or reboot)
```

> Valid `on_movie_start` values are typically `ask` (the prompt — avoid),
> `beginning`, `resume`, or `last`. Use `beginning` (always from start) or
> `resume` (auto-resume, no prompt) — anything except `ask`.

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

- ✅ **Done** — Sky Q-style EPG grid dashboard card
  ([OpenWebif Control Card](https://github.com/kevpatts/OpenWebif-control-card)):
  timeline guide, recordings gallery, favourites, header controls.
- ✅ **Done** — background EPG cache (fetches a bouquet once, refreshes in-use
  bouquets on a schedule, serves the card instantly).
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
