import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from damai_appium import config as config_module


@pytest.fixture
def bot_module(monkeypatch):
    for name in (
        "appium", "appium.options", "appium.options.common",
        "appium.options.common.base", "appium.webdriver",
        "appium.webdriver.common", "appium.webdriver.common.appiumby",
    ):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    path = Path(config_module.__file__).with_name("damai_app_v2.py")
    spec = importlib.util.spec_from_file_location("damai_appium.bot_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module


def make_bot(module, monkeypatch, flag=False, **overrides):
    config = dict(server_url="http://127.0.0.1:4723", city="深圳", users=[],
                  price_index=0, if_commit_order=flag, udid=None, platform_version=None)
    config.update(overrides)
    monkeypatch.setattr(module.Config, "load_config", Mock(return_value=SimpleNamespace(**config)))
    bot = module.DamaiBot()
    bot.driver.find_elements.return_value = []
    bot.smart_wait_and_click = Mock(return_value=True)
    bot.ultra_fast_click = Mock(return_value=True)
    bot.ultra_batch_click = Mock()
    return bot


@pytest.mark.parametrize("flag", [False, True, None, "false"])
def test_submit_requires_explicit_true(bot_module, monkeypatch, capsys, flag):
    bot = make_bot(bot_module, monkeypatch, flag)
    driver = bot.driver

    assert bot.run_ticket_grabbing() is True

    assert bot.smart_wait_and_click.call_count == (3 if flag is True else 2)
    if flag is True:
        selectors = str(bot.smart_wait_and_click.call_args)
        assert "立即提交" in selectors
        assert "提交订单" in selectors
        assert "textMatches" not in selectors
        assert "contains" not in selectors
    else:
        assert "已停在订单确认页，未提交订单" in capsys.readouterr().out
    driver.quit.assert_called_once()
    assert bot.driver is None


def test_missing_commit_flag_does_not_submit(bot_module, monkeypatch):
    bot = make_bot(bot_module, monkeypatch)
    del bot.config.if_commit_order
    assert bot.run_ticket_grabbing() is True
    assert bot.smart_wait_and_click.call_count == 2


@pytest.mark.parametrize("configured", [False, True])
def test_device_capabilities_are_optional(bot_module, monkeypatch, configured):
    make_bot(bot_module, monkeypatch,
             udid="emulator-5554" if configured else None,
             platform_version="14" if configured else None)
    options = bot_module.AppiumOptions.return_value
    caps = options.load_capabilities.call_args.args[0]
    assert "deviceName" not in caps
    if configured:
        assert caps["udid"] == "emulator-5554"
        assert caps["platformVersion"] == "14"
    else:
        assert "udid" not in caps
        assert "platformVersion" not in caps


def test_retry_quits_each_session_once(bot_module, monkeypatch):
    bot = make_bot(bot_module, monkeypatch)
    first = bot.driver
    second = MagicMock()
    second.find_elements.return_value = []
    bot_module.webdriver.Remote.side_effect = [second]
    bot.smart_wait_and_click.side_effect = [False, True, True]

    assert bot.run_with_retry() is True

    first.quit.assert_called_once()
    second.quit.assert_called_once()
    assert bot_module.webdriver.Remote.call_count == 2


def test_missing_submit_button_fails_and_closes(bot_module, monkeypatch):
    bot = make_bot(bot_module, monkeypatch, True)
    driver = bot.driver
    bot.smart_wait_and_click.side_effect = [True, True, False]
    assert bot.run_ticket_grabbing() is False
    driver.quit.assert_called_once()


def test_setup_failure_closes_created_session(bot_module, monkeypatch):
    driver = bot_module.webdriver.Remote.return_value
    driver.update_settings.side_effect = RuntimeError("settings failed")
    with pytest.raises(RuntimeError, match="settings failed"):
        make_bot(bot_module, monkeypatch)
    driver.quit.assert_called_once()


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    directory = tmp_path / "settings"
    directory.mkdir()
    monkeypatch.setattr(config_module, "__file__", str(directory / "config.py"))
    monkeypatch.chdir(tmp_path)
    return directory / "config.jsonc"


def test_config_comments_preserve_strings_and_defaults(config_path):
    config_path.write_text('''{
      // Appium URL
      "server_url": "http://127.0.0.1:4723/path/*literal*/", /* block
      comment */ "keyword": "say \\"hello\\" // literal",
      "users": [], "city": "深圳", "date": "12.06", "price": "799元"
    }''', encoding="utf-8")
    config = config_module.Config.load_config()
    assert config.server_url == "http://127.0.0.1:4723/path/*literal*/"
    assert config.keyword == 'say "hello" // literal'
    assert config.users == []
    assert config.if_commit_order is False
    assert config.price_index == 0
    assert config.udid is None
    assert config.platform_version is None


def test_config_explicit_options(config_path):
    config_path.write_text(json.dumps(dict(
        server_url="http://localhost:4723", keyword="show", users=["张三"],
        city="深圳", date="12.06", price="799", price_index=5,
        if_commit_order=True, udid="device", platform_version="14")), encoding="utf-8")
    config = config_module.Config.load_config()
    assert config.price_index == 5
    assert config.if_commit_order is True
    assert config.udid == "device"
    assert config.platform_version == "14"


@pytest.mark.parametrize("content", ["", "{ invalid }", "{}"])
def test_config_invalid_content_raises(config_path, content):
    config_path.write_text(content, encoding="utf-8")
    with pytest.raises((json.JSONDecodeError, KeyError)):
        config_module.Config.load_config()


def test_config_missing_file_raises(config_path):
    with pytest.raises(FileNotFoundError):
        config_module.Config.load_config()


@pytest.mark.parametrize("success, expected", [(False, 1), (True, 0)])
def test_main_exit_status(bot_module, monkeypatch, success, expected):
    bot = Mock()
    bot.run_with_retry.return_value = success
    monkeypatch.setattr(bot_module, "DamaiBot", Mock(return_value=bot))

    assert bot_module.main() == expected
    bot.run_with_retry.assert_called_once_with(max_retries=3)
