from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.sections.movers import MoversSection
from marketbrief.sections.watchlist import WatchlistSection


def _ctx(watchlist=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(watchlist=watchlist or []))


def test_movers_quiet_with_no_data():
    vm = MoversSection().build(_ctx())
    assert vm.id == "movers" and vm.quiet is True
    assert vm.movers == []


def test_watchlist_quiet_when_empty():
    vm = WatchlistSection().build(_ctx([]))
    assert vm.id == "watchlist" and vm.quiet is True
    assert "watchlist is empty" in vm.lead.text.lower()


def test_watchlist_rows_when_populated():
    vm = WatchlistSection().build(_ctx(["AAPL", "MSFT"]))
    assert vm.quiet is False
    assert [r.ticker for r in vm.movers] == ["AAPL", "MSFT"]
    assert vm.movers[0].source_url.endswith("AAPL")
