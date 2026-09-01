# -*- coding: utf-8 -*-
"""
console_utf8.py — 윈도우 명령 프롬프트에서 한글 print가 죽지 않게 한다

윈도우의 기본 콘솔 인코딩은 cp949다. 한글은 대개 나오지만
'—'(em dash) 같은 문자가 섞이면 UnicodeEncodeError로 **스크립트가 멈춘다.**
CSV 인코딩(utf-8-sig)과는 다른 문제이고, 실제로 수업 첫날 바로 만난다.

모든 스크립트 맨 위에서 `import console_utf8` 한 줄만 하면 된다.
"""

import sys


def _fix(stream):
    try:
        # 파이썬 3.7+ : 출력 스트림의 인코딩을 UTF-8로 바꾼다.
        # 콘솔이 표현하지 못하는 글자는 물음표로 대체하고 넘어간다(멈추지 않는다).
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass          # 아주 오래된 파이썬이면 그냥 둔다


_fix(sys.stdout)
_fix(sys.stderr)
