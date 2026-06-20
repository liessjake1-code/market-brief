from marketbrief.core.symbols import SYMBOLS, SYMBOLS_BY_METRIC, SymbolMap
from marketbrief.core.health import CORE_FIELDS


def test_every_core_field_has_a_symbol():
    for k in CORE_FIELDS:
        assert k in SYMBOLS_BY_METRIC


def test_yields_have_fred_primary():
    assert SYMBOLS_BY_METRIC["ust10y"].fred == "DGS10"
    assert SYMBOLS_BY_METRIC["ust2y"].fred == "DGS2"


def test_oil_has_yf_primary_and_fred_crosscheck():
    wti = SYMBOLS_BY_METRIC["wti"]
    assert wti.yf == "CL=F"
    assert wti.fred == "DCOILWTICO"


def test_inflation_uses_pc1_units_transform():
    assert SYMBOLS_BY_METRIC["cpi_yoy"].fred_units == "pc1"


def test_indices_have_stooq_backup():
    for k in ("sp500", "nasdaq", "dow", "russell"):
        assert SYMBOLS_BY_METRIC[k].stooq is not None
