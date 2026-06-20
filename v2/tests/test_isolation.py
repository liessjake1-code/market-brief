from marketbrief.core.isolation import run_isolated


def test_success_returns_result_and_no_error():
    result, err = run_isolated("ok", lambda: 42, fallback=0)
    assert result == 42
    assert err is None


def test_exception_returns_fallback_and_message(capsys):
    def boom():
        raise ValueError("kaboom")
    result, err = run_isolated("boom-source", boom, fallback="FALLBACK")
    assert result == "FALLBACK"
    assert "kaboom" in err
    captured = capsys.readouterr()
    assert "boom-source" in captured.err  # logged, not swallowed
