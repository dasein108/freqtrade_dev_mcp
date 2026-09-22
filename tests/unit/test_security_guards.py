"""Tests for path, name and file-format guards on MCP commands."""

import json
import logging
import pickle
import sys

import pytest

from src.commands.base import validate_result_id, validate_strategy_name
from src.commands.create_strategy_wireframe import CreateStrategyWireframeCommand
from src.commands.create_userdir import CreateUserdirCommand
from src.commands.extract_hyperopt_data import ExtractHyperoptDataCommand
from src.commands.get_result import GetResultCommand
from src.config import Config
from src.logging_config import setup_mcp_logging
from strategy_agent.nodes.data_fetcher import read_ohlcv_cache_file


@pytest.fixture
def workspace(tmp_path):
    """Freqtrade root with a user_data directory."""
    (tmp_path / "user_data" / "strategies").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def workspace_config(workspace):
    """Config pointing at the temporary Freqtrade root."""
    return Config(freqtrade_path=workspace)


class TestNameValidation:
    """Strategy names and result IDs must not allow path traversal."""

    @pytest.mark.parametrize("name", ["MyStrategy", "_private", "Ema_2x"])
    def test_valid_strategy_names(self, name):
        assert validate_strategy_name(name) == name

    @pytest.mark.parametrize("name", ["../evil", "a/b", "1Strategy", "", "bad-name", "x.py"])
    def test_invalid_strategy_names(self, name):
        with pytest.raises(ValueError):
            validate_strategy_name(name)

    @pytest.mark.parametrize("result_id", ["backtest_Ema_20250101_120000", "hyperopt-1.2"])
    def test_valid_result_ids(self, result_id):
        assert validate_result_id(result_id) == result_id

    @pytest.mark.parametrize("result_id", ["../../etc/passwd", "a/b", "..", ""])
    def test_invalid_result_ids(self, result_id):
        with pytest.raises(ValueError):
            validate_result_id(result_id)


class TestWorkspacePaths:
    """Write operations are confined to the Freqtrade root."""

    def test_relative_path_resolves_inside_root(self, workspace_config, workspace):
        command = CreateUserdirCommand(workspace_config)
        assert command.resolve_workspace_path("config.json") == workspace.resolve() / "config.json"

    @pytest.mark.parametrize("path", ["../outside", "/tmp/elsewhere"])
    def test_paths_outside_root_rejected(self, workspace_config, path):
        command = CreateUserdirCommand(workspace_config)
        with pytest.raises(ValueError):
            command.resolve_workspace_path(path)

    async def test_create_userdir_outside_root_fails(self, workspace_config, tmp_path):
        command = CreateUserdirCommand(workspace_config)
        result = await command.execute(userdir=str(tmp_path.parent / "outside_userdir"))
        assert result["success"] is False
        assert "outside the Freqtrade root" in result["error"]

    async def test_reset_refuses_non_userdir(self, workspace_config, workspace):
        victim = workspace / "important"
        victim.mkdir()
        (victim / "keep.txt").write_text("data")

        command = CreateUserdirCommand(workspace_config)
        result = await command.execute(userdir="important", reset=True)

        assert result["success"] is False
        assert (victim / "keep.txt").exists()

    async def test_reset_refuses_root(self, workspace_config, workspace):
        command = CreateUserdirCommand(workspace_config)
        result = await command.execute(userdir=str(workspace), reset=True)
        assert result["success"] is False
        assert (workspace / "user_data").exists()

    async def test_wireframe_rejects_traversal_name(self, workspace_config):
        command = CreateStrategyWireframeCommand(workspace_config)
        result = await command.execute(strategy_name="../../evil")
        assert result["success"] is False

    async def test_wireframe_defaults_to_strategy_dir(self, workspace_config):
        command = CreateStrategyWireframeCommand(workspace_config)
        result = await command.execute(strategy_name="GuardTest")
        assert result["success"] is True
        assert (workspace_config.full_strategy_dir / "GuardTest.py").exists()

    async def test_get_result_rejects_traversal(self, workspace_config):
        command = GetResultCommand(workspace_config)
        result = await command.execute(result_id="../../secrets")
        assert result["success"] is False


class TestHyperoptFileLoading:
    """Legacy pickle hyperopt files must never be unpickled."""

    async def test_pickle_file_rejected(self, workspace_config, tmp_path):
        hyperopt_file = tmp_path / "legacy.fthypt"
        hyperopt_file.write_bytes(pickle.dumps([{"loss": 1.0}]))

        command = ExtractHyperoptDataCommand(workspace_config)
        result = await command.execute(hyperopt_path=str(hyperopt_file))

        assert result["success"] is False
        assert "pickle" in result["error"]

    async def test_json_lines_file_loaded(self, workspace_config, tmp_path):
        hyperopt_file = tmp_path / "run.fthypt"
        hyperopt_file.write_text(
            json.dumps({"loss": 1.0}) + "\n" + json.dumps({"loss": 0.5}) + "\n"
        )

        command = ExtractHyperoptDataCommand(workspace_config)
        data = await command._load_hyperopt_file(hyperopt_file)

        assert len(data["trials"]) == 2


class TestCandleCacheReader:
    """The agent reads candle cache files returned by download_candles."""

    def test_reads_freqtrade_json(self, tmp_path, sample_ohlcv_data):
        cache_file = tmp_path / "BTC_USDT-1h.json"
        cache_file.write_text(json.dumps(sample_ohlcv_data))

        ohlcv = read_ohlcv_cache_file(cache_file)

        assert set(ohlcv) == {"open", "high", "low", "close", "volume"}
        assert len(ohlcv["close"]) == 3
        assert list(ohlcv["close"].values()) == [50100.0, 50200.0, 50300.0]

    def test_rejects_unexpected_format(self, tmp_path):
        cache_file = tmp_path / "bad.json"
        cache_file.write_text(json.dumps({"not": "rows"}))
        with pytest.raises(ValueError):
            read_ohlcv_cache_file(cache_file)


def test_mcp_logging_keeps_stdout_clean(tmp_path, capsys):
    """stdout carries the MCP protocol, so logging must never write to it."""
    root_logger = logging.getLogger()
    saved_handlers = root_logger.handlers[:]
    try:
        setup_mcp_logging(log_to_file=False, log_dir=tmp_path)
        logging.getLogger("test").warning("hello")
        assert all(
            getattr(handler, "stream", None) is not sys.stdout for handler in root_logger.handlers
        )
    finally:
        root_logger.handlers = saved_handlers
