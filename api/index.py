# -*- coding: utf-8 -*-
"""
api/index.py — Vercel 진입점 (Framework Preset을 "Other"로 둔 경우)

Preset이 "Flask"면 Vercel이 루트 app.py를 직접 불러서 이 파일은 쓰이지 않는다.
어느 쪽이든 동작하도록, 읽기 전용 파일시스템 대응은 db.py 안에 넣어 두었다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
