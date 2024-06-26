"""Файл для глобальных переменных проекта"""

import json
import os
import pathlib


SQLITE_DB_PATH = '/root/sql_chat_demo/database/utils/demo.db'
PROMPT_PATH = '/root/sql_chat_demo/database/utils/ddl.txt'

if os.path.exists('settings_developer.py'):
    from settings_developer import * #noqa

with open(PROMPT_PATH, 'r', encoding='utf-8') as file:
    PROMPT = file.read()