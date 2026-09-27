from paper2repro.config import Settings


def test_settings_reads_api_key_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("PAPER2REPRO_API_KEY", "test-key")

    assert Settings.from_env().api_key == "test-key"


def test_settings_allows_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("PAPER2REPRO_API_KEY", raising=False)

    assert Settings.from_env().api_key is None


def test_settings_uses_configurable_gemini_model(monkeypatch) -> None:
    monkeypatch.setenv("PAPER2REPRO_MODEL", "gemini-test-model")

    assert Settings.from_env().model == "gemini-test-model"


def test_settings_defaults_to_gemini_flash(monkeypatch) -> None:
    monkeypatch.delenv("PAPER2REPRO_MODEL", raising=False)

    assert Settings.from_env().model == "gemini-3.8-flash"
