"""
Unit tests for configuration loading.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile

from config.settings import (
    deep_merge,
    expand_tildes,
    McpServerSettings,
    AgentSettings,
    CrewSettings,
)
from config.root import _load_merged_config, get_merged_config, get_settings, RootSettings
from repositories.config.settings import RepositoriesSettings, FilesystemRepositorySettings


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


class TestMcpServerSettings:
    def test_validates_from_yaml_alias(self):
        s = McpServerSettings.model_validate(
            {"command": "uvx", "args": [], "env": {}, "x-tool-name": "rag_search"}
        )
        assert s.tool_name == "rag_search"

    def test_constructs_with_python_field_name(self):
        s = McpServerSettings(command="uvx", tool_name="rag_search")
        assert s.tool_name == "rag_search"


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

    def test_raises_if_root_settings_yaml_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            empty_config_dir = tmp / "config"
            empty_config_dir.mkdir()
            with patch("config.root.CONFIG_DIR", empty_config_dir), patch(
                "config.root.CREWS_DIR", tmp / "crews"
            ), patch("config.root.REPOSITORIES_DIR", tmp / "repositories"), patch(
                "config.root.load_dotenv"
            ):
                _load_merged_config.cache_clear()
                with pytest.raises(FileNotFoundError):
                    get_merged_config()

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


class TestGetSettings:
    def setup_method(self):
        _load_merged_config.cache_clear()
        get_settings.cache_clear()

    def teardown_method(self):
        _load_merged_config.cache_clear()
        get_settings.cache_clear()

    def _patch_dirs(self, tmp: Path):
        config_dir = tmp / "config"
        config_dir.mkdir()
        (config_dir / "settings.yaml").write_text(
            "chat:\n  model: test-model\n  temperature: 0.5\n"
            "mcpServers:\n  rag-knowledge: null\n"
        )
        crews_dir = tmp / "crews"
        repo_dir = tmp / "repositories"
        return patch("config.root.CONFIG_DIR", config_dir), patch(
            "config.root.CREWS_DIR", crews_dir
        ), patch("config.root.REPOSITORIES_DIR", repo_dir), patch(
            "config.settings.USER_CONFIG_FILE", tmp / "no-user-settings.yaml"
        ), patch(
            "config.root.load_dotenv"
        )

    def test_returns_root_settings_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_dir = tmp / "repositories"
            (repo_dir / "config").mkdir(parents=True)
            (repo_dir / "config" / "settings.yaml").write_text(
                "filesystem:\n  data_dir: ./data\n"
            )
            p1, p2, p3, p4, p5 = self._patch_dirs(tmp)
            with p1, p2, p3, p4, p5:
                settings = get_settings()
        assert isinstance(settings, RootSettings)
        assert settings.chat.model == "test-model"
        assert settings.chat.temperature == 0.5
        assert settings.repositories.filesystem.data_dir == "./data"

    def test_get_settings_is_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_dir = tmp / "repositories"
            (repo_dir / "config").mkdir(parents=True)
            (repo_dir / "config" / "settings.yaml").write_text(
                "filesystem:\n  data_dir: ./data\n"
            )
            p1, p2, p3, p4, p5 = self._patch_dirs(tmp)
            with p1, p2, p3, p4, p5:
                s1 = get_settings()
                s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_allows_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_dir = tmp / "repositories"
            (repo_dir / "config").mkdir(parents=True)
            (repo_dir / "config" / "settings.yaml").write_text(
                "filesystem:\n  data_dir: ./data\n"
            )
            p1, p2, p3, p4, p5 = self._patch_dirs(tmp)
            with p1, p2, p3, p4, p5:
                s1 = get_settings()
                _load_merged_config.cache_clear()
                get_settings.cache_clear()
                s2 = get_settings()
        assert s1 is not s2
        assert s1.chat.model == s2.chat.model


class TestTypedConfigWrappers:
    def test_repository_config_uses_injected_settings(self):
        from repositories.config.settings import Config

        config = Config(
            RepositoriesSettings(
                filesystem=FilesystemRepositorySettings(data_dir="/tmp/cv-joint")
            )
        )

        assert config.data_dir == "/tmp/cv-joint"

    def test_cv_analysis_config_uses_injected_settings(self):
        from crews.cv_analysis.config.settings import Config

        config = Config(
            CrewSettings(
                agents={
                    "cv_analyst": AgentSettings(
                        model="test-model", temperature=0.2, max_tokens=123
                    )
                }
            )
        )

        assert config.cv_analyst_model == "test-model"
        assert config.cv_analyst_temperature == "0.2"
        assert config.cv_analyst_max_tokens == 123

    def test_cv_optimization_config_uses_injected_settings(self):
        from crews.cv_optimization.config.settings import Config

        config = Config(
            CrewSettings(
                agents={
                    "cv_strategist": AgentSettings(
                        model="test-model", temperature=0.5, max_tokens=256
                    )
                }
            )
        )

        assert config.cv_strategist_model == "test-model"

    def test_job_posting_analysis_config_uses_injected_settings(self):
        from crews.job_posting_analysis.config.settings import Config

        config = Config(
            CrewSettings(
                agents={
                    "job_analyst": AgentSettings(
                        model="test-model", temperature=0.1, max_tokens=512
                    )
                }
            )
        )

        assert config.job_analyst_model == "test-model"
