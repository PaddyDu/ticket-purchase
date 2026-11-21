from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock

import pytest

LOGGED_IN = "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！"


@pytest.fixture
def concert_module(monkeypatch):
    import damai  # bind the package before damai/ shadows it with damai.py
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "damai"))
    from damai import concert as module
    monkeypatch.setattr(module, "sleep", Mock())
    return module


@pytest.fixture
def concert(concert_module, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    instance = concert_module.Concert.__new__(concert_module.Concert)
    instance.config = SimpleNamespace(index_url="https://www.damai.cn/",
                                      target_url="https://detail.damai.cn/item.htm?id=1",
                                      login_timeout=300)
    instance.driver = Mock()
    instance.driver.current_url = "https://www.damai.cn/"
    instance.driver.get_cookies.return_value = []
    return instance


def set_titles(driver, titles):
    type(driver).title = PropertyMock(side_effect=titles)


@pytest.mark.parametrize("title, url, expected", [
    ("500 Internal Server Error", "https://www.damai.cn/", True),
    ("502 Bad Gateway", "https://www.damai.cn/", True),
    ("HTTP 403", "https://www.damai.cn/", True),
    ("Service Unavailable", "https://www.damai.cn/", True),
    ("www.damai.cn", "chrome-error://chromewebdata/", True),
    ("大麦网-全球演出赛事官方购票平台", "https://www.damai.cn/", False),
    ("大麦登录", "https://passport.damai.cn/login", False),
    (LOGGED_IN, "https://www.damai.cn/", False),
    ("", None, False),
    (None, "https://www.damai.cn/", False),
])
def test_is_error_page(concert_module, title, url, expected):
    assert concert_module.is_error_page(title, url) is expected


def test_set_cookie_raises_on_error_page(concert, concert_module, tmp_path):
    set_titles(concert.driver, ["500 Internal Server Error"])

    with pytest.raises(concert_module.LoginPageError, match="点击登录失败"):
        concert.set_cookie()

    assert not (tmp_path / "damai_cookies.json").exists()
    concert.driver.get.assert_called_once_with(concert.config.index_url)


def test_set_cookie_raises_on_browser_network_error(concert, concert_module):
    concert.driver.current_url = "chrome-error://chromewebdata/"
    set_titles(concert.driver, ["www.damai.cn"])

    with pytest.raises(concert_module.LoginPageError):
        concert.set_cookie()


def test_set_cookie_raises_when_error_page_appears_during_scan(concert, concert_module, tmp_path):
    set_titles(concert.driver, ["大麦登录", "大麦登录", "504 Gateway Time-out"])

    with pytest.raises(concert_module.LoginPageError, match="扫码登录失败"):
        concert.set_cookie()

    assert not (tmp_path / "damai_cookies.json").exists()


def test_set_cookie_times_out_waiting_for_scan(concert, concert_module, monkeypatch, tmp_path):
    clock = iter([0, 0, 0, 100, 400])
    monkeypatch.setattr(concert_module.time, "monotonic", lambda: next(clock))
    set_titles(concert.driver, ["大麦登录"] * 4)

    with pytest.raises(TimeoutError, match="扫码登录超时: 300 秒"):
        concert.set_cookie()

    assert concert_module.sleep.call_count == 2
    assert not (tmp_path / "damai_cookies.json").exists()


def test_set_cookie_waits_until_logged_in(concert, concert_module, tmp_path):
    set_titles(concert.driver, ["大麦网-全球演出赛事官方购票平台", "大麦登录", "大麦登录", LOGGED_IN])

    concert.set_cookie()

    assert (tmp_path / "damai_cookies.json").exists()
    assert concert_module.sleep.call_count == 2


def test_login_timeout_defaults_when_missing_from_config(concert, concert_module, monkeypatch):
    del concert.config.login_timeout
    clock = iter([0, concert_module.DEFAULT_LOGIN_TIMEOUT])
    monkeypatch.setattr(concert_module.time, "monotonic", lambda: next(clock))
    set_titles(concert.driver, ["大麦网-全球演出赛事官方购票平台"])

    with pytest.raises(TimeoutError, match="点击登录超时: 300 秒"):
        concert.set_cookie()
