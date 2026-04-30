import os
import sys
import json
sys.path.append(os.path.abspath("."))
from core.romm_api import romm_api

try:
    data = romm_api._make_request("/platforms")
    for p in data:
        if p['id'] in (1, 9):
            print(f"ID: {p['id']}, Name: {p['name']}, fs_slug: {p['fs_slug']}")
except Exception as e:
    print(e)
