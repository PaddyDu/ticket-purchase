# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "1.0.0"
__Description__ = "配置类"
__Created__ = 2023/10/27 09:54
"""
import json
import re
from pathlib import Path


class Config:
    def __init__(self, server_url, keyword, users, city, date, price, price_index=0,
                 if_commit_order=False, udid=None, platform_version=None):
        self.server_url = server_url
        self.keyword = keyword
        self.users = users
        self.city = city
        self.date = date
        self.price = price
        self.price_index = price_index
        self.if_commit_order = if_commit_order
        self.udid = udid
        self.platform_version = platform_version

    @staticmethod
    def load_config():
        config_path = Path(__file__).resolve().parent / 'config.jsonc'
        with config_path.open('r', encoding='utf-8') as config_file:
            content = config_file.read()
        pattern = r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/'
        content = re.sub(pattern, lambda match: match.group() if match.group().startswith('"') else ' ', content)
        config = json.loads(content)
        return Config(config['server_url'],
                      config['keyword'],
                      config['users'],
                      config['city'],
                      config['date'],
                      config['price'],
                      config.get('price_index', 0),
                      config.get('if_commit_order', False),
                      config.get('udid'),
                      config.get('platform_version'))