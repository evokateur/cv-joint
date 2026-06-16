"""
Unit tests for configuration loading.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile

from config.settings import (
    load_yaml_config,
    deep_merge,
    expand_tildes,
    get_merged_config,
)
from config.root import _load_merged_config


class TestDeepMerge:
    def test_merges_flat_dicts(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        deep_merge(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_merges_nested_dicts(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        deep_merge(base, override)
        assert base == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"a": 1}
        override = {"a": {"nested": True}}
        deep_merge(base, override)
        assert base == {"a": {"nested": True}}

    def test_override_replaces_dict_with_non_dict(self):
        base = {"a": {"nested": True}}
        override = {"a": 1}
        deep_merge(base, override)
        assert base == {"a": 1}


class TestExpandTildes:
    def test_expands_tilde_in_string_value(self):
        config = {"path": "~/some/path"}
        result = expand_tildes(config)
        assert not result["path"].startswith("~")
        assert result["path"].endswith("/some/path")

    def test_expands_tilde_in_nested_dict(self):
        config = {"outer": {"inner": "~/nested/path"}}
        result = expand_tildes(config)
        assert not result["outer"]["inner"].startswith("~")

    def test_expands_tilde_in_list(self):
        config = {"paths": ["~/first", "~/second", "no-tilde"]}
        result = expand_tildes(config)
        assert not result["paths"][0].startswith("~")
        assert not result["paths"][1].startswith("~")
        assert result["paths"][2] == "no-tilde"

    def test_ignores_non_path_strings(self):
        config = {"name": "hello", "count": 42}
        result = expand_tildes(config)
        assert result == {"name": "hello", "count": 42}

    def test_ignores_bare_tilde(self):
        config = {"value": "~"}
        result = expand_tildes(config)
        assert result["value"] == "~"


class TestLoadYamlConfig:
    def test_loads_settings_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.yaml"
            settings_file.write_text("key: value\n")

            config = load_yaml_config(Path(tmpdir))
            assert config["key"] == "value"

    def test_raises_if_settings_yaml_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                load_yaml_config(Path(tmpdir))

    def test_merges_settings_local_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.yaml"
            settings_file.write_text("a: 1\nb: 2\n")

            local_file = Path(tmpdir) / "settings.local.yaml"
            local_file.write_text("b: 3\nc: 4\n")

            config = load_yaml_config(Path(tmpdir))
            assert config["a"] == 1
            assert config["b"] == 3
            assert config["c"] == 4

    def test_merges_user_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.yaml"
            settings_file.write_text("a: 1\n")

            user_config_file = Path(tmpdir) / "user_settings.yaml"
            user_config_file.write_text("a: 2\nb: 3\n")

            with patch("config.settings.USER_CONFIG_FILE", user_config_file):
                config = load_yaml_config(Path(tmpdir))
                assert config == {"a": 2, "b": 3}

    def test_extracts_user_config_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.yaml"
            settings_file.write_text("agents:\n  analyst:\n    model: default\n")

            user_config_file = Path(tmpdir) / "user_settings.yaml"
            user_config_file.write_text(
                "crews:\n  cv_analysis:\n    agents:\n      analyst:\n        model: override\n"
            )

            with patch("config.settings.USER_CONFIG_FILE", user_config_file):
                config = load_yaml_config(
                    Path(tmpdir), user_config_path="crews.cv_analysis"
                )
                assert config["agents"]["analyst"]["model"] == "override"

    def test_user_config_path_missing_key_uses_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.yaml"
            settings_file.write_text("a: 1\n")

            user_config_file = Path(tmpdir) / "user_settings.yaml"
            user_config_file.write_text("other:\n  key: value\n")

            with patch("config.settings.USER_CONFIG_FILE", user_config_file):
                config = load_yaml_config(Path(tmpdir), user_config_path="missing.path")
                assert config == {"a": 1}


class TestGetMergedConfig:
    def test_returns_dict_with_expected_keys(self):
        config = get_merged_config()
        assert "chat" in config
        assert "mcpServers" in config
        assert "crews" in config
        assert "repositories" in config


class TestRootConfigPipeline:
    def teardown_method(self):
        _load_merged_config.cache_clear()

    def test_assembles_namespaced_defaults_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            crews_dir = tmp / "crews"
            repo_dir = tmp / "repositories"

            config_dir.mkdir()
            (crews_dir / "cv_analysis" / "config").mkdir(parents=True)
            (repo_dir / "config").mkdir(parents=True)

            (config_dir / "settings.yaml").write_text(
                "chat:\n  model: default-chat\nmcpServers:\n  rag-knowledge: null\n"
            )
            (crews_dir / "cv_analysis" / "config" / "settings.yaml").write_text(
                "agents:\n  cv_analyst:\n    model: default-crew\n"
            )
            (repo_dir / "config" / "settings.yaml").write_text(
                "filesystem:\n  data_dir: ./data\n"
            )

            user_config_file = tmp / "user_settings.yaml"
            user_config_file.write_text(
                "\n".join(
                    [
                        "chat:",
                        "  model: user-chat",
                        "mcpServers:",
                        "  rag-knowledge:",
                        "    command: uvx",
                        "    args: [rag-server]",
                        "    x-tool-name: rag_search",
                        "crews:",
                        "  cv_analysis:",
                        "    agents:",
                        "      cv_analyst:",
                        "        model: user-crew",
                        "repositories:",
                        "  filesystem:",
                        "    data_dir: ~/cv-data",
                    ]
                )
                + "\n"
            )

            (crews_dir / "cv_analysis" / "config" / "settings.local.yaml").write_text(
                "agents:\n  cv_analyst:\n    model: local-crew\n"
            )
            (repo_dir / "config" / "settings.local.yaml").write_text(
                "filesystem:\n  data_dir: ./local-data\n"
            )

            with patch("config.root.CONFIG_DIR", config_dir), patch(
                "config.root.CREWS_DIR", crews_dir
            ), patch("config.root.REPOSITORIES_DIR", repo_dir), patch(
                "config.settings.USER_CONFIG_FILE", user_config_file
            ), patch(
                "config.root.load_dotenv"
            ) as load_dotenv_mock:
                _load_merged_config.cache_clear()
                config = get_merged_config()

            assert config["chat"]["model"] == "user-chat"
            assert config["mcpServers"]["rag-knowledge"]["x-tool-name"] == "rag_search"
            assert (
                config["crews"]["cv_analysis"]["agents"]["cv_analyst"]["model"]
                == "local-crew"
            )
            assert config["repositories"]["filesystem"]["data_dir"] == "./local-data"
            load_dotenv_mock.assert_called_once_with()

    def test_returns_defensive_copy_from_cached_loader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            config_dir.mkdir()
            (config_dir / "settings.yaml").write_text(
                "chat:\n  model: default-chat\nmcpServers:\n  rag-knowledge: null\n"
            )
            user_config_file = tmp / "missing-user-settings.yaml"

            with patch("config.root.CONFIG_DIR", config_dir), patch(
                "config.root.CREWS_DIR", tmp / "crews"
            ), patch("config.root.REPOSITORIES_DIR", tmp / "repositories"), patch(
                "config.settings.USER_CONFIG_FILE", user_config_file
            ), patch(
                "config.root.load_dotenv"
            ):
                _load_merged_config.cache_clear()
                config = get_merged_config()
                config["chat"]["model"] = "mutated"
                refreshed = get_merged_config()

            assert refreshed["chat"]["model"] == "default-chat"
