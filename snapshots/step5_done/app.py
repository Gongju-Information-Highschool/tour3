# -*- coding: utf-8 -*-
"""
app.py — "맵으로 공주" 웹 서버

라우팅 7개 (§6.1)
    GET  /              지도 홈
    GET  /panel/<id>    장소 상세
    POST /fav/<id>      찜 토글
    GET  /favorites     찜 목록
    POST /route         동선 결과
    GET  /stats         보정 전/후 랭킹 비교
    GET  /offline       타일 없이 보는 위치 관계 그림

JavaScript는 templates/map.html 의 지도 초기화 블록 하나가 전부다(§6.3).
필터·찜·동선·가중치·기준점은 전부 폼 제출로 처리한다.

실행:  python app.py  →  http://127.0.0.1:5000
"""

import os
import urllib.request

from flask import Flask, redirect, render_template, request, session, url_for

import db
import geo
import scoring

app = Flask(__name__)

# 실제 서비스라면 이 값은 비밀로 관리한다. 수업용이라 그냥 적어 둔다.
app.secret_key = "map-gongju-2026"

ROOT = os.path.dirname(os.path.abspath(__file__))

# 거리 기준점의 기본값 (원도심 한가운데)
DEFAULT_ORIGIN_NAME = "공산성"


# ═══════════════════════════════════════════════════════════════
# 서버가 켜질 때 딱 한 번 — 지도를 띄울 수 있는 상태인지 확인한다 (§6.4)
# ═══════════════════════════════════════════════════════════════

def tile_server_reachable(timeout=2.0):
    """OpenStreetMap 타일 서버에 닿는지 본다.

    타일이 화면에 안 뜨는 것은 브라우저에서 일어나는 일이라 서버는 알 수 없다.
    그래서 감지하려면 JS가 필요한데, 그건 §6.3의 경계를 넘는다.
    대신 서버가 켜질 때 한 번 확인하고 그 결과로 화면을 나눈다.
    (매 요청마다 확인하면 화면이 느려진다)
    """
    try:
        req = urllib.request.Request(
            "https://tile.openstreetmap.org/0/0/0.png",
            headers={"User-Agent": "map-gongju-class/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status == 200
    except Exception:
        return False


LEAFLET_BUNDLE = os.path.join(ROOT, "static", "leaflet", "leaflet.js")
HAS_LEAFLET = os.path.exists(LEAFLET_BUNDLE)
ONLINE = tile_server_reachable()

# 지도를 그리는 두 가지 방법
#   leaflet : 진짜 지도 타일 위에 마커      (인터넷 + leaflet 번들이 둘 다 있을 때)
#   svg     : 좌표만 찍은 위치 관계 그림     (그 외 전부)
MAP_MODE = "leaflet" if (HAS_LEAFLET and ONLINE) else "svg"


# ═══════════════════════════════════════════════════════════════
# 요청마다 준비되는 것들
# ═══════════════════════════════════════════════════════════════

@app.before_request
def ensure_user():
    """회원가입 없이 session으로만 사람을 구분한다 (§6.2).

    이 서비스는 첫 화면이 입력 폼이 아니라 지도라서, '제출하는 순간'이 없다.
    그래서 누구든 처음 들어오면 조용히 사용자 한 명을 만들어 둔다.
    """
    if "user_id" in session:
        return
    conn = db.connect()
    nickname = "guest"
    user_id = db.create_user(conn, nickname)
    db.rename_user(conn, user_id, f"guest-{user_id:04d}")
    conn.close()
    session["user_id"] = user_id


# 상단 메뉴. Step별 완성본(snapshots/)에서는 아직 없는 화면이 있으므로
# **실제로 살아 있는 라우트만** 골라서 보여 준다. 없는 화면을 url_for 하면 서버가 죽는다.
NAV = [("home", "지도"), ("favorites", "찜 목록"),
       ("stats", "보정 전/후"), ("offline", "위치 관계 그림")]


@app.context_processor
def inject_globals():
    """모든 화면이 공통으로 쓰는 값들 (상단 배너 등)."""
    conn = db.connect()
    meta = db.get_meta(conn)
    conn.close()
    endpoints = set(app.view_functions)
    return {
        "endpoints": endpoints,
        "nav": [(name, label) for name, label in NAV if name in endpoints],
        "MAP_MODE": MAP_MODE,
        "ONLINE": ONLINE,
        "HAS_LEAFLET": HAS_LEAFLET,
        "meta": meta,
        "CATEGORIES": scoring.CATEGORIES,
        "is_placeholder": meta.get("data_source") == "placeholder",
    }


def read_weights():
    """가중치 3개를 쿼리에서 읽는다. 없으면 params.json 기본값."""
    base = scoring.load_params()["weights"]

    def get(name, default):
        try:
            return max(0.0, float(request.args.get(name, default)))
        except (TypeError, ValueError):
            return default

    return (get("w_star", base["star"]),
            get("w_dist", base["dist"]),
            get("w_pref", base["pref"]))


def read_extensions():
    """확장 과제 스위치(§13). **전부 기본값이 꺼짐이다.**

    아무 것도 주지 않으면 기본 과제와 완전히 똑같이 동작한다.
    이 원칙은 verify.py의 회귀 항목이 지켜 준다.
    """
    return {
        "use_blog": request.args.get("use_blog") == "1",   # 확장 2
        "heat": request.args.get("heat") == "1",           # 확장 4
    }


def pick_origin(conn, places):
    """거리를 재는 기준점을 정한다 (§5.3).

    우선순위: 주소창의 ?origin= → 방금 열어 본 장소(세션) → 공산성 → 첫 번째 장소
    지도 중심을 읽지 않는 이유는 그게 JS를 부르기 때문이다.
    """
    raw = request.args.get("origin")
    if raw:
        try:
            session["origin_id"] = int(raw)
        except ValueError:
            pass

    by_id = {p["id"]: p for p in places}
    origin_id = session.get("origin_id")
    if origin_id in by_id:
        return by_id[origin_id]

    for p in places:
        if p["name"] == DEFAULT_ORIGIN_NAME:
            return p
    return places[0] if places else None


def user_taste(conn):
    """지금 사용자의 취향(관심도)과 신호 총량."""
    views, favs = db.interest_counts(conn, session["user_id"])
    return scoring.interest_map(views, favs)


# ═══════════════════════════════════════════════════════════════
# 1. 지도 홈
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def home():
    conn = db.connect()
    meta = db.get_meta(conn)

    category = request.args.get("cat") or ""
    weights = read_weights()

    all_places = db.all_places(conn)
    origin = pick_origin(conn, all_places)

    shown = db.all_places(conn, category) if category else all_places
    interests, log_count = user_taste(conn)

    ext = read_extensions()

    # 확장 2 — 블로그리뷰까지 신호로 치는 보정 별점으로 갈아 끼운다.
    # 값은 init_db.py가 adj_star_blog 컬럼에 미리 계산해 두었다.
    if ext["use_blog"]:
        for p in shown:
            p["adj_star"] = p["adj_star_blog"]
        adj_min, adj_max = meta.get("adj_blog_min"), meta.get("adj_blog_max")
    else:
        adj_min, adj_max = meta.get("adj_min"), meta.get("adj_max")

    ranked = scoring.rank_places(
        shown, origin, interests, log_count, weights,
        adj_min=adj_min, adj_max=adj_max)

    # 확장 4 — 히트맵. 마커 크기를 점수 대신 '눌린 횟수'로 바꾼다.
    heat = db.click_counts(conn) if ext["heat"] else {}
    if ext["heat"]:
        hottest = max(heat.values(), default=0)
        for p in ranked:
            n = heat.get(p["id"], 0)
            p["heat"] = n
            p["size"] = ("big" if n >= hottest * 0.66 and n > 0 else
                         "mid" if n >= hottest * 0.33 and n > 0 else "small")

    favs = db.favorite_ids(conn, session["user_id"])
    counts = db.category_counts(conn)
    conn.close()

    # 지도를 못 쓸 때를 대비해 SVG 좌표도 함께 넘긴다.
    # 정적 이미지가 아니라 지금 점수·필터가 그대로 반영된 그림이다(§6.4).
    svg_points = geo.project_points(ranked, width=520, height=440, min_dist=16, zoom_out=1.05)

    # Leaflet에 넘길 최소한의 값만 추린다 (템플릿이 tojson으로 심는다)
    places_json = [
        {"id": p["id"], "name": p["name"], "lat": p["lat"], "lon": p["lon"],
         "category": p["category"], "size": p["size"]}
        for p in ranked
    ]

    return render_template(
        "map.html",
        places=ranked, places_json=places_json,
        svg_points=svg_points, origin=origin,
        category=category, counts=counts, favorites=favs,
        all_places=all_places, weights=weights,
        log_count=log_count, interests=interests,
        ext=ext, heat=heat,
    )


# ═══════════════════════════════════════════════════════════════
# 2. 장소 상세
# ═══════════════════════════════════════════════════════════════

@app.route("/panel/<int:place_id>")
def panel(place_id):
    conn = db.connect()
    place = db.get_place(conn, place_id)
    if not place:
        conn.close()
        return "그런 장소가 없습니다", 404

    meta = db.get_meta(conn)

    # 열람 기록을 남긴다. 10분 안에 또 봐도 다시 남기지는 않는다(§5.4).
    db.log_click(conn, session["user_id"], place_id, "view")

    # 이 장소를 다음 기준점으로 삼는다 — "방금 본 곳에서 가까운 순서로"
    session["origin_id"] = place_id

    is_fav = db.is_favorite(conn, session["user_id"], place_id)
    conn.close()

    place["s_star"] = scoring.star_score(
        place["adj_star"], meta["adj_min"], meta["adj_max"])

    return render_template("panel.html", place=place, is_fav=is_fav)


# ═══════════════════════════════════════════════════════════════
# 3. 찜 토글
# ═══════════════════════════════════════════════════════════════

@app.route("/offline")
def offline():
    conn = db.connect()
    meta = db.get_meta(conn)
    places = db.all_places(conn)
    origin = pick_origin(conn, places)
    interests, log_count = user_taste(conn)
    ranked = scoring.rank_places(
        places, origin, interests, log_count, read_weights(),
        adj_min=meta.get("adj_min"), adj_max=meta.get("adj_max"))
    conn.close()

    svg_points = geo.project_points(ranked, width=520, height=440, min_dist=16, zoom_out=1.05)
    return render_template("offline.html", svg_points=svg_points,
                           places=ranked, origin=origin)


if __name__ == "__main__":
    print(f"지도 방식 : {MAP_MODE}   (leaflet 번들 {'있음' if HAS_LEAFLET else '없음'}"
          f" / 타일서버 {'연결됨' if ONLINE else '연결 안 됨'})")
    print("http://127.0.0.1:5000 을 브라우저에서 여세요")
    app.run(debug=True, port=5000)
