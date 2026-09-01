# -*- coding: utf-8 -*-
"""
make_placeholder_seed.py — data/places_raw.csv(33행)를 만든다

┌──────────────────────────────────────────────────────────────────┐
│ ★ 중요 ★                                                          │
│ 이 스크립트가 만드는 별점·리뷰수는 전부 **임시값(placeholder)** 이다. │
│ 네이버플레이스에서 수집한 실제 값이 아니다.                          │
│                                                                  │
│ 실제인 것   : 장소명 30곳, 좌표(mapx/mapy)  ← v2.4에서 이식        │
│ 임시인 것   : 별점, 방문자리뷰 수, 블로그리뷰 수                    │
│                                                                  │
│ 기획안 §8 A2(네이버플레이스 수집, 약 3h)를 마치면                   │
│ 이 스크립트를 버리고 수집한 CSV로 교체한다.                         │
│ 교체 후 data/params.json 의 data_source 를 "naver_place" 로 바꾼다. │
└──────────────────────────────────────────────────────────────────┘

임시값이라도 아무 숫자나 넣지 않았다. 기획안 §10 검증이 요구하는
성질(별점 결측 5건, 콤마 6건, 보정 전/후 순위 뒤집힘 3곳 이상,
평균 별점이 C=4.30과 0.05 이내)을 만족하도록 설계했다.
그래야 A2 이전에도 파이프라인 전체를 끝까지 돌려 볼 수 있다.

실행:  python scripts/make_placeholder_seed.py
"""

import csv
import os

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# ═══════════════════════════════════════════════════════════════
# 장소별 값
#   (장소명, 네이버 카테고리 원문, 별점, 방문자리뷰, 블로그리뷰)
#   별점 None = 결측 (별점이 아직 없는 플레이스. 실데이터에서 흔하다)
# ═══════════════════════════════════════════════════════════════
#
# 값을 고를 때 지킨 두 가지
#   ① 별점 평균이 params.json 의 C = 4.30 과 맞을 것 (init_db가 0.05 넘으면 멈춘다)
#   ② '리뷰 적고 별점 높은 곳'과 '리뷰 많고 별점 보통인 곳'이 충분히 섞일 것
#      ← 이게 없으면 보정 전/후 랭킹이 거의 그대로라 검증 5번(순위 뒤집힘 3곳)이
#        실패하고, 12차시 발표에서 학생이 설명할 것이 없어진다.
#      실데이터에서도 리뷰 10개 미만에 별점 4.8~5.0인 작은 가게는 아주 흔하다.
#
PLACES = [
    # ── 역사문화 계열 ────────────────────────────────────────
    ("공산성",                        "문화유적",       4.3, 1204, 890),
    ("공주무령왕릉과왕릉원",           "문화유적",       4.2,  512, 430),
    ("국립공주박물관",                 "박물관",         4.4,  843, 651),
    ("석장리박물관",                   "박물관",         3.8,  121,  96),
    ("충청남도역사박물관",             "박물관",         3.7,   63,  41),
    ("마곡사",                        "사찰",           4.6, 1532, 1120),  # 리뷰 최다 → 크게 상승
    ("갑사",                          "사찰",           4.4,  707, 512),
    ("동학사",                        "사찰",           4.3, 1018, 604),
    ("신원사",                        "사찰",           3.9,  168, 122),
    ("천주교황새바위순교성지",          "성지",           3.8,   92,  58),
    ("공주한옥마을",                   "한옥",           3.6,  246, 315),
    # ── 자연 ────────────────────────────────────────────────
    ("유구색동수국정원",               "정원",           4.8,  431, 705),
    ("계룡저수지",                     "저수지",         None,   17,  12),   # 별점 결측 1
    ("고마나루솔밭",                   "숲",             4.0,  138,  87),
    ("공주산림휴양마을",               "자연휴양림",     None,   54,  33),   # 별점 결측 2
    # ── 휴식 ────────────────────────────────────────────────
    ("공주산성시장문화공원",           "공원",           None,    9,   6),   # 별점 결측 3
    ("임립미술관",                     "미술관",         4.7,   14,  61),   # 저리뷰·고별점
    ("이미정갤러리",                   "갤러리",         None,   12,   9),   # 별점 결측 4
    ("대통길작은미술관",               "미술관",         4.8,    8,  18),   # 저리뷰·고별점
    ("자연미술관Ko",                   "미술관",         4.8,   11,  39),   # 저리뷰·고별점
    # ── 체험 ────────────────────────────────────────────────
    ("공주목재문화체험장",             "체험마을",       4.3,   71,  44),
    ("대장이랜드중장농촌체험휴양마을",  "농촌체험마을",   None,    4,   3),   # 별점 결측 5
    ("계룡산상신농촌체험휴양마을",      "농촌체험마을",   4.9,    4,   5),   # 리뷰 4개 별점 4.9 → 크게 하락
    ("아트센터고마",                   "문화예술회관",   3.8,  112,  79),
    # ── 먹거리 ──────────────────────────────────────────────
    ("공주산성시장",                   "재래시장",       3.9, 1043, 812),
    ("개성집공주점",                   "한정식",         4.5, 1287, 640),   # 리뷰 많고 별점 높음 → 상승
    ("고마나루1999",                   "한식",           4.4,  396, 288),
    ("공산성본가",                     "한식",           4.2, 1128, 507),
    # ── 카페감성 ────────────────────────────────────────────
    ("베이커리밤마을",                 "베이커리",       4.4,  312, 401),   # ★ 손계산 예제 B
    ("곡물집",                         "카페",           5.0,    2,   1),   # ★ 손계산 예제 A
]

# ═══════════════════════════════════════════════════════════════
# 오염(§4.4) — 정제 실습의 재료
# ═══════════════════════════════════════════════════════════════

# 오염 ①·② 중복 2건: 같은 장소가 표기 차이로 두 번 수집된다.
#   정제 규칙(§4.4): 접미사·공백을 뗀 뒤 이름이 같으면 중복,
#                    방문자리뷰 수가 큰 행을 남긴다.
DUPLICATES = [
    # (원본 장소명, 중복 행에 쓸 표기, 그 행의 방문자리뷰, 블로그리뷰)
    ("개성집공주점", "개성집",       903, 455),   # 지점명 표기 차이
    ("공주산성시장", "공주 산성시장", 664, 502),   # 공백 표기 차이
]

# 오염 ③ 좌표 결측 1건: 관광지가 아닌 것이 검색 결과에 섞여 들어왔고,
#   좌표도 빠져 있다. 정제 단계에서 제외된다.
NO_COORD_ROW = ("공주역", "기차역", 4.0, 88, 30)

# 오염 ④ 리뷰수 콤마 표기: 화면에서 복사하면 1000 이상은 "1,204"로 들어온다.
COMMA_THRESHOLD = 1000

COLLECTED_AT = "2026-08"


def load_coords():
    """v2.4에서 이식한 실제 좌표를 읽는다 (경도·위도 → mapx·mapy 로 되돌린다)."""
    coords = {}
    path = os.path.join(DATA, "spots_geo.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            # 네이버 지역검색 원본 형식으로 되돌린다 (정수 mapx/mapy)
            coords[row["name"]] = (
                str(int(round(float(row["lon"]) * 10 ** 7))),
                str(int(round(float(row["lat"]) * 10 ** 7))),
            )
    return coords


def fmt_review(n):
    """리뷰 수를 화면에서 복사한 것처럼 만든다. 1000 이상이면 콤마가 붙는다."""
    return "{:,}".format(n) if n >= COMMA_THRESHOLD else str(n)


def main():
    coords = load_coords()

    missing = [name for name, *_ in PLACES if name not in coords]
    if missing:
        raise SystemExit("좌표를 찾을 수 없는 장소가 있다: " + ", ".join(missing))

    rows = []

    # 1) 정상 30행
    for name, cat_raw, star, visitor, blog in PLACES:
        mapx, mapy = coords[name]
        rows.append({
            "name": name,
            "category_raw": cat_raw,
            "road_address": "충청남도 공주시",      # 실주소는 A2에서 채운다
            "mapx": mapx,
            "mapy": mapy,
            "star": "" if star is None else str(star),
            "visitor_rev": fmt_review(visitor),
            "blog_rev": fmt_review(blog),
            "collected_at": COLLECTED_AT,
        })

    # 2) 중복 2행
    for origin, alias, visitor, blog in DUPLICATES:
        base = next(r for r in rows if r["name"] == origin)
        dup = dict(base)
        dup["name"] = alias
        dup["visitor_rev"] = fmt_review(visitor)   # 원본보다 적게 → 원본이 살아남는다
        dup["blog_rev"] = fmt_review(blog)
        rows.append(dup)

    # 3) 좌표 결측 1행
    name, cat_raw, star, visitor, blog = NO_COORD_ROW
    rows.append({
        "name": name,
        "category_raw": cat_raw,
        "road_address": "충청남도 공주시",
        "mapx": "",                                  # ← 결측
        "mapy": "",
        "star": str(star),
        "visitor_rev": fmt_review(visitor),
        "blog_rev": fmt_review(blog),
        "collected_at": COLLECTED_AT,
    })

    out = os.path.join(DATA, "places_raw.csv")
    cols = ["name", "category_raw", "road_address", "mapx", "mapy",
            "star", "visitor_rev", "blog_rev", "collected_at"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ── 만들어진 결과를 눈으로 확인할 수 있게 요약을 찍는다 ──────────
    stars = [s for _, _, s, _, _ in PLACES if s is not None]
    comma_rows = sum(1 for r in rows if "," in r["visitor_rev"] or "," in r["blog_rev"])

    print("=" * 62)
    print("★ 임시(placeholder) 시드를 만들었습니다 — 실제 네이버 별점이 아닙니다")
    print("=" * 62)
    print(f"  파일           : {out}")
    print(f"  전체 행        : {len(rows)}행  (정상 30 + 중복 2 + 좌표결측 1)")
    print(f"  별점 결측      : {sum(1 for _, _, s, _, _ in PLACES if s is None)}건")
    print(f"  콤마 표기 행   : {comma_rows}건")
    print(f"  별점 평균(실측): {sum(stars) / len(stars):.3f}   ← params.json 의 c_mean 과 비교")
    print()
    print("  다음: python scripts/preprocess.py")


if __name__ == "__main__":
    main()
