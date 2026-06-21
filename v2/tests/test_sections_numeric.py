from datetime import date
from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.core.models import Field
from marketbrief.sections.rates import RatesSection
from marketbrief.sections.commodities import CommoditiesSection
from marketbrief.sections.crypto import CryptoSection
from marketbrief.sections.volatility import VolatilitySection


def _ctx(fields):
    return BriefContext(run_date=date(2026, 6, 20), mode=RunMode.NO_SEND,
                        config=Config(), resolved_fields=fields)


def _f(m, v):
    return {m: Field(metric=m, value=v, source="yfinance")}


def test_rates_full_and_quiet():
    vm = RatesSection().build(_ctx({**_f("ust10y", 4.3), **_f("ust2y", 4.0),
                                    **_f("dxy", 104.0)}))
    assert vm.id == "rates_and_dollar" and vm.quiet is False
    assert len(vm.stat_rows[0].cells) == 3
    assert RatesSection().build(_ctx({})).quiet is True


def test_commodities():
    vm = CommoditiesSection().build(_ctx({**_f("wti", 78.0), **_f("gold", 2300.0)}))
    assert vm.id == "commodities" and len(vm.stat_rows[0].cells) == 2


def test_crypto():
    vm = CryptoSection().build(_ctx({**_f("btc", 65000.0), **_f("eth", 3500.0)}))
    assert vm.id == "crypto" and len(vm.stat_rows[0].cells) == 2


def test_volatility():
    vm = VolatilitySection().build(_ctx(_f("vix", 14.0)))
    assert vm.id == "volatility_breadth" and len(vm.stat_rows[0].cells) == 1
    assert VolatilitySection().build(_ctx({})).quiet is True
