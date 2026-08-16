"""Load OpenWebif Control inside a real HA test instance with mocked box HTTP.

Uses real payloads captured from the live box (fixtures/) so the test is
deterministic but exercises the full HA path: config flow -> entry setup ->
coordinator -> entities -> services.
"""
import json
import sys
import types
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant import config_entries, data_entry_flow
from homeassistant.helpers import entity_registry as er

CC = Path(__file__).resolve().parent.parent / "custom_components"
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(CC.parent))
if "custom_components" not in sys.modules:
    pkg = types.ModuleType("custom_components")
    pkg.__path__ = [str(CC)]
    sys.modules["custom_components"] = pkg

from custom_components.openwebif_control.const import DOMAIN  # noqa: E402

HOST = "10.0.7.40"
BASE = f"http://{HOST}:80"


def _fix(name):
    return json.loads((FIX / name).read_text())


def _register_mocks(aioclient_mock):
    """Wire every OpenWebif endpoint the integration calls to a fixture."""
    aioclient_mock.get(f"{BASE}/api/about", json=_fix("about.json"))
    aioclient_mock.get(f"{BASE}/api/statusinfo", json=_fix("statusinfo.json"))
    aioclient_mock.get(f"{BASE}/api/bouquets", json=_fix("bouquets.json"))
    aioclient_mock.get(f"{BASE}/api/timerlist", json=_fix("timerlist.json"))
    aioclient_mock.get(f"{BASE}/api/movielist", json=_fix("movielist.json"))
    # EPG now/next and any zap/message/etc. — match by URL prefix via params
    aioclient_mock.get(f"{BASE}/api/epgnownext", json=_fix("epgnownext.json"))
    aioclient_mock.get(f"{BASE}/api/epgnow", json=_fix("epgnownext.json"))
    # Single-service EPG for the next-programme sensor (channel-change fetch).
    import time as _t
    aioclient_mock.get(
        f"{BASE}/api/epgservice",
        json={"events": [
            {"title": "Upcoming Show", "begin_timestamp": int(_t.time()) + 3600,
             "duration_sec": 1800, "shortdesc": "Later."},
        ]},
    )
    aioclient_mock.get(f"{BASE}/api/zap", json={"result": True})
    aioclient_mock.get(f"{BASE}/api/message", json={"result": True})
    aioclient_mock.get(f"{BASE}/api/remotecontrol", json={"result": True})
    aioclient_mock.get(f"{BASE}/api/powerstate", json={"result": True, "instandby": False})
    aioclient_mock.get(f"{BASE}/api/timeraddbyeventid", json={"result": True})
    # getservices is called per-bouquet by get_all_channels(); return a small
    # channel set regardless of the sRef param.
    aioclient_mock.get(
        f"{BASE}/api/getservices",
        json={
            "services": [
                {"servicename": "BBC One HD",
                 "servicereference": "1:0:19:287B:800:2:11A0000:0:0:0:"},
                {"servicename": "ITV1 HD",
                 "servicereference": "1:0:19:515E:842:2:11A0000:0:0:0:"},
                {"servicename": "<n/a>",
                 "servicereference": "1:64:0:0:0:0:0:0:0:0::marker"},
            ]
        },
    )


async def test_full_setup(hass: HomeAssistant, aioclient_mock):
    """Config flow -> setup -> entities + services, using real box payloads."""
    _register_mocks(aioclient_mock)

    # 1. Config flow user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # 2. Submit connection details
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": HOST, "port": 80, "ssl": False, "verify_ssl": True},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY, result
    entry = result["result"]
    print("\n[title]", entry.title, "[unique_id]", entry.unique_id)

    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED, entry.state

    # 3. Entities exist and have real values
    reg = er.async_get(hass)
    ents = sorted(
        e.entity_id for e in reg.entities.values() if e.platform == DOMAIN
    )
    print("[entities]")
    for eid in ents:
        st = hass.states.get(eid)
        print("   ", eid, "=>", st.state if st else "<none>")
    assert any("current_programme" in e for e in ents)
    assert any("next_programme" in e for e in ents)
    assert any("timers" in e or "timer" in e for e in ents)
    assert any("recording" in e for e in ents)
    assert any("standby" in e for e in ents)

    # 4. Sanity on real values
    cur = next(hass.states.get(e) for e in ents if "current_programme" in e)
    print("[current programme]", cur.state, "| channel:",
          cur.attributes.get("channel"))
    rec = next(hass.states.get(e) for e in ents if e.endswith("_recordings"))
    print("[recordings count]", rec.state)
    assert int(rec.state) > 0

    # Channels sensor should exist and have filtered out the marker.
    chan = next(hass.states.get(e) for e in ents if e.endswith("_channels"))
    print("[channels count]", chan.state)
    assert int(chan.state) == 2  # BBC One + ITV1, marker excluded
    names = [c["name"] for c in chan.attributes["channels"]]
    assert "<n/a>" not in names
    # bouquet_refs map is exposed for the EPG grid service.
    assert isinstance(chan.attributes.get("bouquet_refs"), dict)
    print("[bouquet_refs]", len(chan.attributes["bouquet_refs"]), "bouquets")

    # 5. Services registered
    for svc in ("zap", "send_message", "remote_control", "add_timer",
                "toggle_standby", "get_epg"):
        assert hass.services.has_service(DOMAIN, svc), f"missing {svc}"
    print("[services] all 6 registered")

    # get_epg returns response data from epgmulti (use a now-relative time so
    # the service's time-window keeps the real event and drops the N/A one).
    import time as _time
    _now = int(_time.time())
    aioclient_mock.get(
        f"{BASE}/api/epgmulti",
        json={"events": [
            {"sref": "1:0:19:287B:800:2:11A0000:0:0:0:", "sname": "BBC One HD",
             "title": "News", "begin_timestamp": _now,
             "duration_sec": 1800, "shortdesc": "x", "id": 1},
            {"sref": "x", "sname": "x", "title": "N/A",
             "begin_timestamp": 0, "duration_sec": 0},
        ]},
    )
    epg_resp = await hass.services.async_call(
        DOMAIN, "get_epg",
        {"bouquet_reference": "1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"x\" ORDER BY bouquet"},
        blocking=True, return_response=True,
    )
    assert epg_resp and "events" in epg_resp
    assert len(epg_resp["events"]) == 1  # N/A filtered out
    print("[get_epg] returned", len(epg_resp["events"]), "event(s)")

    # 6. Exercise a service call end-to-end
    await hass.services.async_call(
        DOMAIN, "zap",
        {"service_reference": "1:0:19:287B:800:2:11A0000:0:0:0:"},
        blocking=True,
    )
    print("[zap service] call succeeded")

    # 7. Clean unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED
    print("[unload] clean")
