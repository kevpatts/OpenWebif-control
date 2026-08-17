"""Verify the coordinator's background EPG cache: fetch-once, serve-from-cache."""
import sys, types, time
from pathlib import Path
import pytest
from unittest.mock import AsyncMock

CC = Path(__file__).resolve().parent.parent / "custom_components"
sys.path.insert(0, str(CC.parent))
if "custom_components" not in sys.modules:
    pkg = types.ModuleType("custom_components"); pkg.__path__=[str(CC)]
    sys.modules["custom_components"]=pkg

from custom_components.openwebif_control.coordinator import OpenWebifCoordinator

@pytest.mark.allow_hosts(["127.0.0.1"])
async def test_epg_cache_fetches_once(hass):
    coord = OpenWebifCoordinator.__new__(OpenWebifCoordinator)
    # minimal manual init of the bits async_get_epg uses
    coord.client = types.SimpleNamespace()
    now = int(time.time())
    events = [
        {"sref":"a","sname":"A","title":"Now Show","begin_timestamp":now,"duration_sec":1800,"shortdesc":"x","id":1},
        {"sref":"a","sname":"A","title":"Old","begin_timestamp":now-99999,"duration_sec":600},
        {"sref":"a","sname":"A","title":"Far","begin_timestamp":now+99*3600,"duration_sec":600},
        {"sref":"a","sname":"A","title":"N/A","begin_timestamp":now,"duration_sec":600},
    ]
    coord.client.get_epg_multi = AsyncMock(return_value=events)
    coord._epg_cache = {}
    coord.epg_horizon_hours = 5

    # First call fetches
    out1 = await coord.async_get_epg("bref-x")
    assert coord.client.get_epg_multi.call_count == 1
    titles = [e["title"] for e in out1]
    assert titles == ["Now Show"]  # old/far/N-A all filtered

    # Second call served from cache (no new fetch)
    out2 = await coord.async_get_epg("bref-x")
    assert coord.client.get_epg_multi.call_count == 1
    assert out2 == out1
    print("EPG cache: fetch-once verified, windowing correct")
