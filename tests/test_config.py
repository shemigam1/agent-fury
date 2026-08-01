"""Key-loading regression tests.

Guards the bug where an installed CLI ignored the user's `.env`: python-dotenv's
default search starts from the package location, not the working directory.
"""

import os

from fury.config import Config


def test_env_loaded_from_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=cwd-key\n")
    monkeypatch.chdir(tmp_path)
    try:
        cfg = Config.load()
        assert cfg.key("openrouter") == "cwd-key"
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)


def test_env_loaded_from_global(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    genv = tmp_path / "global.env"
    genv.write_text("OPENAI_API_KEY=global-key\n")
    monkeypatch.setattr("fury.config.GLOBAL_ENV", genv)
    monkeypatch.chdir(tmp_path)  # no local .env here
    try:
        cfg = Config.load()
        assert cfg.key("openai") == "global-key"
    finally:
        os.environ.pop("OPENAI_API_KEY", None)


def test_real_env_var_wins_over_files(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=from-file\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    monkeypatch.chdir(tmp_path)
    cfg = Config.load()
    assert cfg.key("openrouter") == "from-env"
