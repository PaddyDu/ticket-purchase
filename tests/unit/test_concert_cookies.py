import builtins
import json
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, call

import pytest


@pytest.fixture
def concert(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "damai"))
    from damai import concert as concert_module

    opened_files = []

    def track_open(*args, **kwargs):
        handle = builtins.open(*args, **kwargs)
        opened_files.append(handle)
        return handle

    monkeypatch.setattr(concert_module, "open", track_open, raising=False)

    monkeypatch.chdir(tmp_path)
    instance = concert_module.Concert.__new__(concert_module.Concert)
    instance.config = SimpleNamespace(index_url="https://www.damai.cn/",
                                      target_url="https://detail.damai.cn/item.htm?id=1")
    instance.driver = Mock()
    type(instance.driver).title = PropertyMock(side_effect=[
        "登录", "大麦网-全球演出赛事官方购票平台-100%正品、先付先抢、在线选座！",
    ])
    instance.login_method = 1
    yield instance
    assert all(handle.closed for handle in opened_files)


@pytest.mark.parametrize("cookies", [[], [{"name": "session", "value": "测试", "secure": True}]])
@pytest.mark.parametrize("existing", [False, True])
def test_save_and_load_cookies(concert, tmp_path, cookies, existing):
    path = tmp_path / "damai_cookies.json"
    if existing:
        path.write_text("old cookies")
        path.chmod(0o644)
    concert.driver.get_cookies.return_value = cookies

    concert.set_cookie()

    assert json.loads(path.read_text(encoding="utf-8")) == cookies
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert concert.driver.get.call_args_list == [call(concert.config.index_url),
                                                 call(concert.config.target_url)]
    concert.get_cookie()
    assert concert.driver.add_cookie.call_args_list == [
        call({"domain": ".damai.cn", "name": cookie["name"], "value": cookie["value"]})
        for cookie in cookies
    ]


@pytest.mark.parametrize("content", [None, "not JSON", "[null]"])
def test_load_cookie_errors_are_reported(concert, tmp_path, capsys, content):
    if content is not None:
        (tmp_path / "damai_cookies.json").write_text(content)

    concert.get_cookie()

    concert.driver.add_cookie.assert_not_called()
    assert capsys.readouterr().out.strip()


def test_save_cookie_error_closes_file(concert, tmp_path):
    concert.driver.get_cookies.return_value = [object()]

    with pytest.raises(TypeError):
        concert.set_cookie()

    assert stat.S_IMODE((tmp_path / "damai_cookies.json").stat().st_mode) == 0o600
    concert.driver.get.assert_called_once_with(concert.config.index_url)


@pytest.mark.parametrize("existing", [False, True])
def test_login_uses_json_cookie_file(concert, tmp_path, existing):
    (tmp_path / "damai_cookies.pkl").write_bytes(b"legacy cookies must not be read")
    if existing:
        (tmp_path / "damai_cookies.json").write_text("[]")
    concert.set_cookie = Mock()
    concert.get_cookie = Mock()

    concert.login()

    assert concert.set_cookie.call_count == (0 if existing else 1)
    assert concert.get_cookie.call_count == (1 if existing else 0)
