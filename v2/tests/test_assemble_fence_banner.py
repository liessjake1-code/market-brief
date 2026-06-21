from datetime import datetime
from marketbrief.core.models import HealthReport
from marketbrief.assemble.fence import build_live_snapshot
from marketbrief.assemble.banner import banner_text


def test_premarket_label_before_open():
    snap = build_live_snapshot(datetime(2026, 6, 20, 8, 25), rows=[])
    assert snap.is_premarket is True and snap.as_of_label.startswith("Pre-market as of")
    assert "08:25 CT" in snap.as_of_label


def test_early_session_label_after_open():
    snap = build_live_snapshot(datetime(2026, 6, 20, 9, 5), rows=[])
    assert snap.is_premarket is False
    assert snap.as_of_label.startswith("Early session as of")


def test_banner_none_when_clean():
    assert banner_text(HealthReport(degraded=False)) is None


def test_banner_text_when_degraded():
    txt = banner_text(HealthReport(degraded=True))
    assert txt and "limited" in txt.lower()
