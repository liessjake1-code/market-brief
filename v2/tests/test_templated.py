from marketbrief.core.models import ComputedNumbers
from marketbrief.narrate.templated import templated_why, templated_all
from marketbrief.match.keywords import SECTION_KEYWORDS


def test_templated_why_is_degraded_and_clean():
    w = templated_why("commodities", ComputedNumbers(values={"wti": 76.1}))
    assert w.section_id == "commodities"
    assert w.degraded is True
    assert w.causes == []
    assert "—" not in w.text          # no em dash
    assert all(ord(c) < 128 for c in w.text)  # no emoji / non-ascii


def test_templated_all_covers_every_section():
    out = templated_all(ComputedNumbers(values={}))
    assert set(out.keys()) == set(SECTION_KEYWORDS.keys())
