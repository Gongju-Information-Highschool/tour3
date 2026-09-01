# -*- coding: utf-8 -*-
"""
api/index.py — Vercel 서버리스 진입점

Vercel은 배포된 파일을 읽기 전용으로 올린다. data/place.db에 그대로 쓰면
"attempt to write a readonly database" 오류가 난다.
쓸 수 있는 곳은 /tmp 하나뿐이라, 서버가 처음 뜰 때 DB를 그리로 복사해서 쓴다.

주의: /tmp는 서버 인스턴스가 살아 있는 동안만 유지된다.
      찜·열람 기록은 잠시 뒤 사라지고, 접속자마다 다를 수도 있다.
      영구 저장이 필요하면 README의 "영구 DB" 항목을 참고한다.
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db  # noqa: E402

WRITABLE_DB = "/tmp/place.db"
if not os.path.exists(WRITABLE_DB):
    shutil.copyfile(os.path.join(ROOT, "data", "place.db"), WRITABLE_DB)

# db.connect 는 기본 인자로 DB_PATH를 물고 있다(정의될 때 값이 굳는다).
# 그래서 db.DB_PATH만 바꿔서는 안 되고, 함수 자체를 감싸 준다.
_original_connect = db.connect


def _connect(path=WRITABLE_DB):
    return _original_connect(path)


db.connect = _connect
db.DB_PATH = WRITABLE_DB

from app import app  # noqa: E402,F401
