# -*- coding: utf-8 -*-
"""
init_db.py — places_clean.csv 를 SQLite(data/place.db)에 적재한다

★ 안전 규칙 (v2.4에서 계승)
    인자 없이 실행    → 테이블이 이미 있으면 **아무것도 하지 않는다**
    --reset 을 주면   → 장소를 다시 적재한다 (찜·클릭 기록은 지워진다)

  Step 7~8에서 학생은 반드시 한 번은 init_db.py를 다시 실행한다.
  그때 찜과 클릭 로그가 전멸하면 그날 수업이 끝난다. 그래서 기본은 no-op다.

여기서 보정 별점(adj_star)을 **한 번만 계산해 컬럼으로 저장**한다.
정규화(§5.2)에 쓰는 adj_min/adj_max가 요청마다 흔들리면 안 되기 때문이다.

실행:  python scripts/init_db.py          (최초 1회)
       python scripts/init_db.py --reset  (처음부터 다시)
"""

import csv
import os
import sqlite3
import sys

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)               # scoring.py 를 불러오기 위해

from scoring import adjusted_star, load_params, CATEGORIES  # noqa: E402

DATA = os.path.join(ROOT, "data")
CLEAN = os.path.join(DATA, "places_clean.csv")
DB = os.path.join(DATA, "place.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  category_raw  TEXT NOT NULL,
  category      TEXT NOT NULL,
  road_address  TEXT,
  lat           REAL NOT NULL,
  lon           REAL NOT NULL,
  star          REAL,
  visitor_rev   INTEGER NOT NULL,
  blog_rev      INTEGER NOT NULL,
  adj_star      REAL NOT NULL,
  adj_star_blog REAL NOT NULL,   -- 확장 2용. 기본 화면은 쓰지 않는다(§13)
  collected_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, nickname TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
  id INTEGER PRIMARY KEY, user_id INTEGER, place_id INTEGER,
  action TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS favorites (
  id INTEGER PRIMARY KEY, user_id INTEGER, place_id INTEGER, created_at TEXT,
  UNIQUE(user_id, place_id)
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY, value TEXT
);

CREATE INDEX IF NOT EXISTS idx_clicks_user ON clicks(user_id);
CREATE INDEX IF NOT EXISTS idx_fav_user    ON favorites(user_id);
"""


def read_clean():
    with open(CLEAN, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    reset = "--reset" in sys.argv

    if not os.path.exists(CLEAN):
        raise SystemExit(f"{CLEAN} 이 없습니다. 먼저 python scripts/preprocess.py 를 실행하세요.")

    conn = sqlite3.connect(DB)

    if reset:
        # 표를 통째로 지우고 다시 만든다. 행만 지우면 컬럼이 바뀐 경우를 못 따라간다.
        print("--reset : 장소·찜·클릭 기록을 모두 지우고 다시 적재합니다.")
        conn.executescript(
            "DROP TABLE IF EXISTS places;    DROP TABLE IF EXISTS users;"
            "DROP TABLE IF EXISTS clicks;    DROP TABLE IF EXISTS favorites;"
            "DROP TABLE IF EXISTS meta;")

    conn.executescript(SCHEMA)

    # 예전에 만든 DB라 컬럼이 모자랄 수 있다. 조용히 실패하지 않게 먼저 알려 준다.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(places)")}
    missing = {"adj_star", "adj_star_blog"} - columns
    if missing:
        print(f"이 DB는 예전 구조입니다 (없는 컬럼: {', '.join(sorted(missing))}).")
        print("  python scripts/init_db.py --reset 으로 다시 만들어 주세요.")
        conn.close()
        sys.exit(1)

    already = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    if already and not reset:
        print(f"이미 장소 {already}곳이 들어 있습니다. 아무것도 바꾸지 않았습니다.")
        print("  (찜·클릭 기록을 지우고 처음부터 다시 만들려면 --reset 을 붙이세요)")
        conn.close()
        return

    params = load_params()
    m = params["m_review"]
    C = params["c_mean"]

    rows = read_clean()

    # ── 실측 평균 별점을 계산해 params.json의 C와 대조한다 (§4.5) ─────
    stars = [float(r["star"]) for r in rows if str(r["star"]).strip()]
    actual = sum(stars) / len(stars)
    gap = abs(actual - C)
    print(f"별점 실측 평균 {actual:.3f}  vs  params.json 의 C = {C}   (차이 {gap:.3f})")
    if gap > 0.05:
        print()
        print("!! 멈춥니다 — 차이가 0.05를 넘습니다.")
        print("   이대로 두면 교재에 인쇄된 손계산 정답과 코드 출력이 어긋납니다.")
        print("   data/params.json 의 c_mean 을 고치고, 손계산 예제도 다시 확정하세요(§4.5).")
        conn.close()
        sys.exit(1)

    # ── 적재 + 보정 별점 계산 ───────────────────────────────────
    records = []
    for i, r in enumerate(rows, start=1):
        star = float(r["star"]) if str(r["star"]).strip() else None
        visitor = int(r["visitor_rev"])
        blog = int(r["blog_rev"])
        adj = adjusted_star(star, visitor, m, C)
        # 확장 2(블로그리뷰 반영)용 값도 같이 계산해 둔다.
        # 화면이 켜질 때만 쓰이고, 기본 화면은 위의 adj만 본다.
        adj_blog = adjusted_star(star, visitor, m, C, blog_rev=blog, use_blog=True)
        records.append((
            i, r["name"], r["category_raw"], r["category"], r["road_address"],
            float(r["lat"]), float(r["lon"]), star, visitor, blog,
            adj, adj_blog, r["collected_at"],
        ))

    conn.executemany(
        "INSERT INTO places (id, name, category_raw, category, road_address,"
        " lat, lon, star, visitor_rev, blog_rev, adj_star, adj_star_blog, collected_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", records)

    # ── meta : 정규화에 쓸 최소·최대를 고정해 둔다 ─────────────────
    adj_values = [rec[10] for rec in records]
    adj_blog_values = [rec[11] for rec in records]
    meta = {
        "m_review": m,
        "c_mean": C,
        "adj_min": min(adj_values),
        "adj_max": max(adj_values),
        "adj_blog_min": min(adj_blog_values),
        "adj_blog_max": max(adj_blog_values),
        "seed_rows": len(records),
        "collected_at": rows[0]["collected_at"],
        "data_source": params.get("data_source", "unknown"),
        "star_mean_actual": round(actual, 4),
    }
    conn.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                     [(k, str(v)) for k, v in meta.items()])
    conn.commit()

    # ── 요약 ────────────────────────────────────────────────────
    print(f"적재 완료 : {len(records)}곳  →  {DB}")
    print(f"보정 별점 : 최저 {meta['adj_min']:.3f} ~ 최고 {meta['adj_max']:.3f}"
          f"  (이 두 값으로 0~1 정규화한다 — §5.2)")

    counts = {}
    for rec in records:
        counts[rec[3]] = counts.get(rec[3], 0) + 1
    print("카테고리 : " + ", ".join(f"{c} {counts.get(c, 0)}" for c in CATEGORIES))

    if meta["data_source"] == "placeholder":
        print()
        print("=" * 62)
        print("★ 주의 : 지금 들어 있는 별점·리뷰수는 임시값입니다.")
        print("   실제인 것은 장소명과 좌표뿐입니다.")
        print("   기획안 §8 A2(네이버플레이스 수집)를 마친 뒤 CSV를 교체하고,")
        print("   data/params.json 의 data_source 를 naver_place 로 바꾸세요.")
        print("=" * 62)

    print()
    print("  다음: python scripts/verify.py")
    conn.close()


if __name__ == "__main__":
    main()
