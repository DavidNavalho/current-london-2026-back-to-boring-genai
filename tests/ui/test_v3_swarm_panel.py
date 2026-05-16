from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v3_launches_background_swarm_without_showing_dashboard_status():
    html = (ROOT / "web" / "v3" / "index.html").read_text(encoding="utf-8")

    assert 'id="swarmBtn"' not in html
    assert "launch_swarm=true" in html
    assert 'id="swarmPanel"' not in html
    assert "pollSwarm" not in html
    assert "/demo/swarm/" not in html
    assert "state.swarmId" not in html
    assert "Agents are running" not in html
    assert "Open Langfuse" in html
    assert "setRun(data.swarm_id)" not in html
    assert "setRun(result.swarm_id)" not in html
