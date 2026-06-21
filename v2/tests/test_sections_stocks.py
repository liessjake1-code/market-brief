from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.sections.movers import MoversSection
from marketbrief.sections.watchlist import WatchlistSection
from marketbrief.compute.movers import compute_movers


def _ctx(watchlist=None, mover_board=None):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(watchlist=watchlist or []),
                        mover_board=mover_board)


def test_movers_quiet_with_no_data():
    vm = MoversSection().build(_ctx())
    assert vm.id == "movers" and vm.quiet is True
    assert vm.movers == []
    assert vm.mover_board is None


def test_movers_quiet_when_board_has_no_rows():
    board = compute_movers({"FLAT": [100.0, 100.0]})  # nothing moved
    vm = MoversSection().build(_ctx(mover_board=board))
    assert vm.quiet is True and vm.mover_board is None


def test_movers_populated_when_board_has_rows():
    board = compute_movers({"NVDA": [100.0, 105.0], "PFE": [100.0, 96.0]})
    vm = MoversSection().build(_ctx(mover_board=board))
    assert vm.quiet is False
    assert vm.mover_board is not None and vm.mover_board.has_rows
    day = next(p for p in vm.mover_board.periods if p.label == "Day")
    assert day.winners[0].ticker == "NVDA"
    assert day.losers[0].ticker == "PFE"


def test_watchlist_quiet_when_empty():
    vm = WatchlistSection().build(_ctx([]))
    assert vm.id == "watchlist" and vm.quiet is True
    assert "watchlist is empty" in vm.lead.text.lower()


def test_watchlist_rows_when_populated():
    vm = WatchlistSection().build(_ctx(["AAPL", "MSFT"]))
    assert vm.quiet is False
    assert [r.ticker for r in vm.movers] == ["AAPL", "MSFT"]
    assert vm.movers[0].source_url.endswith("AAPL")
