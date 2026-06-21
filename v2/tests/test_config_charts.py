from marketbrief.core.config import Config, ChartsConfig


def test_default_on_charts():
    c = Config()
    assert c.charts.equities is True and c.charts.rates is True and c.charts.commodities is True


def test_default_off_charts():
    c = Config()
    assert c.charts.vix is False and c.charts.movers is False and c.charts.crypto is False
    assert c.charts.scorecard is False and c.charts.sparklines is False
