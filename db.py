# -*- coding: utf-8 -*-
"""
db.py — SQLite 조회·기록 함수 모음

라우트(app.py)는 SQL을 직접 쓰지 않고 전부 여기를 거친다.
그래야 화면 코드가 짧아지고, 학생이 SQL과 화면을 따로따로 볼 수 있다.
"""

import os
import sqlite3
from datetime import datetime, timedelta

from scoring import CATEGORIES

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "place.db")

# ── Vercel 등 읽기 전용 환경 대응 ───────────────────────────
# 배포된 파일은 수정할 수 없다. 그대로 쓰려고 하면
# "attempt to write a readonly database" 오류가 난다.
# 쓸 수 있는 곳은 /tmp 하나뿐이라, 처음 뜰 때 그리로 복사해서 쓴다.
# (주의: /tmp는 서버가 살아 있는 동안만 유지된다 — 기록이 영구 저장되지 않는다)
# 노트북에서 python app.py 로 돌릴 때는 이 블록을 건너뛴다.
if os.environ.get("VERCEL"):
    import shutil
    _writable = os.path.join("/tmp", os.path.basename(DB_PATH))
    if not os.path.exists(_writable):
        shutil.copyfile(DB_PATH, _writable)
    DB_PATH = _writable


# 같은 장소를 다시 열어도 이 시간 안에는 열람 기록을 새로 남기지 않는다(§5.4).
# 새로고침 몇 번으로 한 카테고리 관심도가 치솟는 사고를 막는다.
VIEW_DEDUP_MINUTES = 10


def connect(path=DB_PATH):
    """DB에 연결한다. 결과를 딕셔너리처럼 쓸 수 있게 row_factory를 설정한다."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════════════
# meta — 알고리즘이 쓰는 상수들 (init_db.py가 채운다)
# ═══════════════════════════════════════════════════════════════

def get_meta(conn):
    """meta 테이블을 딕셔너리로 읽는다. 숫자로 보이는 값은 숫자로 바꿔 준다."""
    meta = {}
    for row in conn.execute("SELECT key, value FROM meta"):
        value = row["value"]
        try:
            meta[row["key"]] = float(value)
        except (TypeError, ValueError):
            meta[row["key"]] = value
    return meta


# ═══════════════════════════════════════════════════════════════
# places
# ═══════════════════════════════════════════════════════════════

def all_places(conn, category=None):
    """장소 목록. category를 주면 그 분류만 걸러서 준다."""
    sql = "SELECT * FROM places"
    args = []
    if category in CATEGORIES:
        sql += " WHERE category = ?"
        args.append(category)
    return [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]


def get_place(conn, place_id):
    row = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    return dict(row) if row else None


def category_counts(conn):
    """카테고리별 장소 수 (필터 칩에 표시한다)."""
    rows = conn.execute(
        "SELECT category, COUNT(*) AS n FROM places GROUP BY category")
    counts = {r["category"]: r["n"] for r in rows}
    return {cat: counts.get(cat, 0) for cat in CATEGORIES}


# ═══════════════════════════════════════════════════════════════
# users — 회원가입 없이 session으로만 구분한다 (§6.2)
# ═══════════════════════════════════════════════════════════════

def create_user(conn, nickname):
    cur = conn.execute(
        "INSERT INTO users (nickname, created_at) VALUES (?, ?)", (nickname, now()))
    conn.commit()
    return cur.lastrowid


def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def rename_user(conn, user_id, nickname):
    conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, user_id))
    conn.commit()


# ═══════════════════════════════════════════════════════════════
# clicks — 암묵 피드백 로그
# ═══════════════════════════════════════════════════════════════

def log_click(conn, user_id, place_id, action):
    """행동을 기록한다. 'view'는 10분 안에 같은 장소를 또 봐도 다시 남기지 않는다."""
    if action == "view":
        cutoff = (datetime.now() - timedelta(minutes=VIEW_DEDUP_MINUTES)) \
            .strftime("%Y-%m-%d %H:%M:%S")
        recent = conn.execute(
            "SELECT 1 FROM clicks "
            " WHERE user_id = ? AND place_id = ? AND action = 'view' AND created_at >= ?"
            " LIMIT 1", (user_id, place_id, cutoff)).fetchone()
        if recent:
            return False

    conn.execute(
        "INSERT INTO clicks (user_id, place_id, action, created_at) VALUES (?, ?, ?, ?)",
        (user_id, place_id, action, now()))
    conn.commit()
    return True


def interest_counts(conn, user_id):
    """취향 부스트의 재료. (카테고리별 열람 수, 카테고리별 현재 찜 수)

    찜은 clicks가 아니라 favorites에서 센다 — 찜 취소가 저절로 상쇄되도록(§5.4).
    """
    views = {}
    for r in conn.execute(
            "SELECT p.category AS category, COUNT(*) AS n"
            "  FROM clicks c JOIN places p ON p.id = c.place_id"
            " WHERE c.user_id = ? AND c.action = 'view'"
            " GROUP BY p.category", (user_id,)):
        views[r["category"]] = r["n"]

    favs = {}
    for r in conn.execute(
            "SELECT p.category AS category, COUNT(*) AS n"
            "  FROM favorites f JOIN places p ON p.id = f.place_id"
            " WHERE f.user_id = ?"
            " GROUP BY p.category", (user_id,)):
        favs[r["category"]] = r["n"]

    return views, favs


def click_summary(conn, user_id):
    """/stats 화면에 보여 줄 내 행동 요약."""
    rows = conn.execute(
        "SELECT action, COUNT(*) AS n FROM clicks WHERE user_id = ? GROUP BY action",
        (user_id,))
    return {r["action"]: r["n"] for r in rows}


# ═══════════════════════════════════════════════════════════════
# favorites
# ═══════════════════════════════════════════════════════════════

def is_favorite(conn, user_id, place_id):
    row = conn.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND place_id = ?",
        (user_id, place_id)).fetchone()
    return row is not None


def toggle_favorite(conn, user_id, place_id):
    """찜을 켜고 끈다. 켜졌으면 True를 돌려준다."""
    if is_favorite(conn, user_id, place_id):
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND place_id = ?",
                     (user_id, place_id))
        conn.commit()
        log_click(conn, user_id, place_id, "unfav")
        return False

    conn.execute(
        "INSERT INTO favorites (user_id, place_id, created_at) VALUES (?, ?, ?)",
        (user_id, place_id, now()))
    conn.commit()
    log_click(conn, user_id, place_id, "fav")
    return True


def favorite_ids(conn, user_id):
    return {r["place_id"] for r in
            conn.execute("SELECT place_id FROM favorites WHERE user_id = ?", (user_id,))}


def favorite_places(conn, user_id):
    rows = conn.execute(
        "SELECT p.* FROM favorites f JOIN places p ON p.id = f.place_id"
        " WHERE f.user_id = ? ORDER BY f.created_at", (user_id,))
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# 확장 과제용 (§13) — 기본 화면은 아래 함수들을 쓰지 않는다
# ═══════════════════════════════════════════════════════════════

def click_counts(conn):
    """장소별 누적 열람·찜 횟수. 확장 4(히트맵)에서 원 크기로 쓴다.

    한 사람이 아니라 **이 서비스를 써 본 모든 사람**의 기록을 합친다.
    수업이 진행될수록 그림이 진해지는 것이 이 확장의 재미다.
    """
    rows = conn.execute(
        "SELECT place_id, COUNT(*) AS n FROM clicks"
        " WHERE action IN ('view', 'fav') GROUP BY place_id")
    return {r["place_id"]: r["n"] for r in rows}


def merged_favorite_places(conn, user_ids):
    """여러 사람의 찜을 합집합으로 모은다. 확장 3(둘이 함께 동선 짜기)."""
    if not user_ids:
        return []
    marks = ",".join("?" for _ in user_ids)
    rows = conn.execute(
        f"SELECT DISTINCT p.* FROM favorites f JOIN places p ON p.id = f.place_id"
        f" WHERE f.user_id IN ({marks}) ORDER BY p.id", list(user_ids))
    return [dict(r) for r in rows]


def user_exists(conn, user_id):
    return conn.execute("SELECT 1 FROM users WHERE id = ?",
                        (user_id,)).fetchone() is not None
