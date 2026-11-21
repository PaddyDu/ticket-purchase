import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

DAMAI_DIR = Path(__file__).resolve().parents[2] / "damai"


@pytest.fixture
def damai_main(monkeypatch):
    import damai  # bind the package before damai/ shadows it with damai.py
    monkeypatch.syspath_prepend(str(DAMAI_DIR))
    spec = importlib.util.spec_from_file_location("damai_main", DAMAI_DIR / "damai.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "check_config_file", Mock())
    monkeypatch.setattr(module, "load_config", Mock())
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module


def make_concert(damai_main, monkeypatch, error=None):
    con = Mock()
    con.enter_concert.side_effect = error
    monkeypatch.setattr(damai_main, "Concert", Mock(return_value=con))
    return con


@pytest.mark.parametrize("error", [
    lambda m: m.LoginPageError("点击登录失败: 页面加载出错"),
    lambda m: TimeoutError("扫码登录超时"),
])
def test_grab_returns_nonzero_on_login_failure(damai_main, monkeypatch, error):
    con = make_concert(damai_main, monkeypatch, error(damai_main))

    assert damai_main.grab() == 1
    con.finish.assert_called_once()
    con.choose_ticket.assert_not_called()


def test_grab_returns_zero_on_success(damai_main, monkeypatch):
    con = make_concert(damai_main, monkeypatch)

    assert damai_main.grab() == 0
    con.choose_ticket.assert_called_once()
