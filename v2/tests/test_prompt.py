from marketbrief.core.models import Article, ComputedNumbers
from marketbrief.match.scorer import ScoredArticle
from marketbrief.narrate.prompt import SYSTEM_PROMPT, build_user, SECTION_SCHEMA


def test_system_prompt_states_the_rules():
    s = SYSTEM_PROMPT.lower()
    assert "no clear catalyst" in s
    assert "cause_source_id" in s
    assert "round" in s  # told to round/approximate numbers


def test_build_user_includes_numbers_and_scored_articles():
    matched = {"commodities": [ScoredArticle(
        Article(source_id="cnbc-1", title="Oil jumps", summary="opec"), 0.5)]}
    user = build_user(ComputedNumbers(values={"wti": 76.1}), matched)
    assert "wti" in user and "76.1" in user
    assert "cnbc-1" in user and "Oil jumps" in user


def test_schema_shape():
    props = SECTION_SCHEMA["schema"]["properties"]["sections"]["items"]["properties"]
    assert set(props) >= {"section_id", "prose", "cause", "cause_source_id", "confidence"}
