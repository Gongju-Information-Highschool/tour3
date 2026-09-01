# -*- coding: utf-8 -*-
"""
scoring.py — 이 수업의 심장

장소 하나에 점수를 매기는 세 가지 방법과, 그 셋을 합치는 방법이 들어 있다.
    §5.1 보정 별점   : 리뷰 수가 다른 별점을 공정하게 비교한다 (베이지안 평균)
    §5.2 별점 정규화 : 4.1~4.7에 뭉친 보정 별점을 0~1로 펴 준다
    §5.3 거리 점수   : 기준점에서 가까울수록 높다
    §5.4 취향 부스트 : 내 클릭·찜 기록에서 취향을 읽는다 (암묵 피드백)
    §5.5 최종 점수   : 셋을 가중치로 합치고, 동점이면 정해진 순서로 줄 세운다

넘파이를 쓰지 않는다. 전부 순수 파이썬이라 학생이 한 줄씩 따라갈 수 있다.
"""

import json
import os

from geo import haversine_km

# 표준 6분류. **순서를 바꾸지 않는다** (화면 필터·통계가 이 순서를 따른다)
CATEGORIES = ["역사문화", "자연", "체험", "먹거리", "카페감성", "휴식"]

# 취향 부스트의 기준점. 6분류가 완전히 균등하면 관심도가 1/6이 된다.
EVEN = 1.0 / len(CATEGORIES)

# 취향을 반영하기 시작하는 최소 로그 건수 (이보다 적으면 콜드 스타트)
MIN_LOG = 5

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PARAMS_PATH = os.path.join(_ROOT, "data", "params.json")
_params_cache = None


def load_params(path=_PARAMS_PATH):
    """data/params.json 을 읽는다.

    m·C·손계산 예제값의 **단일 출처**다(§4.5).
    scoring.py·verify.py·교재가 전부 이 파일 하나를 본다.
    코드에 4.30을 직접 적어 넣지 않는 이유: 수집 데이터가 바뀌었을 때
    교재의 손계산 정답과 코드 출력이 조용히 어긋나는 사고를 막기 위함이다.
    """
    global _params_cache
    if _params_cache is None:
        with open(path, encoding="utf-8") as f:
            _params_cache = json.load(f)
    return _params_cache


# ═══════════════════════════════════════════════════════════════
# §5.1 보정 별점 — 베이지안 평균
# ═══════════════════════════════════════════════════════════════

def adjusted_star(star, visitor_rev, m, C, verbose=False,
                  blog_rev=0, use_blog=False):
    """리뷰 수를 감안해 별점을 보정한다.

        보정별점 = (v × R + m × C) / (v + m)

        v = 그 장소의 방문자리뷰 수
        R = 그 장소의 별점 (없으면 R = C)
        m = 기준 리뷰 수 (params.json)
        C = 전체 평균 별점 (params.json)

    별점이 없으면(R = C) 식이 (v×C + m×C)/(v+m) = C 로 **정확히 C가 된다.**
    리뷰가 2개든 500개든 결과가 같다 — 별점이 없으면 리뷰 수는 아무것도 알려 주지
    못하기 때문이다. 그래서 별점 없는 장소들은 보정 별점이 전부 동점이 되고,
    §5.5의 동점 규칙이 필요해진다.

    use_blog=True 는 **확장 과제 2**다(§13). 블로그리뷰도 신호로 치되,
    직접 방문해서 쓴 리뷰보다는 약하다고 보아 0.3만 인정한다.
    기본값은 False라 아무것도 주지 않으면 기본 과제와 완전히 같게 동작한다.
    """
    v = int(visitor_rev or 0)
    if use_blog:                       # 확장 2 — 기본은 꺼져 있다
        v = v + 0.3 * int(blog_rev or 0)
    R = C if star is None or star == "" else float(star)

    numerator = v * R + m * C          # 분자
    denominator = v + m                # 분모
    result = numerator / denominator

    if verbose:                        # 손계산 차시에서 중간 계산을 눈으로 본다
        print(f"    ({v} × {R} + {m} × {C}) / ({v} + {m})"
              f" = {numerator:.1f} / {denominator} = {result:.4f}")
    return result


# ═══════════════════════════════════════════════════════════════
# §5.2 별점 정규화 — v1.0의 가장 큰 결함을 고치는 곳
# ═══════════════════════════════════════════════════════════════

def star_score(adj, adj_min, adj_max):
    """보정 별점을 0~1로 편다.

    왜 필요한가: 실데이터의 보정 별점은 4.1~4.7처럼 좁은 구간에 뭉친다.
    그냥 5로 나누면 0.82~0.94, 변별폭이 0.12뿐이라 가중치를 0.5로 줘도
    거리 점수(0~1)에 완전히 눌린다. **배운 것이 화면에 나타나지 않는다.**

    대신 최하위를 0, 최상위를 1로 펴면 가중치 0.5가 액면 그대로 작동한다.
    대가도 분명하다 — 절대 평가가 상대 평가로 바뀐다. 4.10점이 0점이 된다.
    /stats 화면에서 원값과 정규화값을 나란히 보여 주고 이 점을 이야기한다.
    """
    if adj_max - adj_min < 1e-9:       # 30곳이 전부 같은 점수인 극단적 경우
        return 0.5
    return (adj - adj_min) / (adj_max - adj_min)


# ═══════════════════════════════════════════════════════════════
# §5.3 거리 점수
# ═══════════════════════════════════════════════════════════════

def distance_score(km):
    """기준점에서 가까울수록 1에 가깝다.  0km→1.0, 1km→0.5, 4km→0.2"""
    return 1.0 / (1.0 + km)


def distance_km_between(origin, place):
    """기준점과 장소 사이 거리(km). 기준점이 없으면 None."""
    if not origin:
        return None
    return haversine_km(origin["lat"], origin["lon"], place["lat"], place["lon"])


# ═══════════════════════════════════════════════════════════════
# §5.4 취향 부스트 — 행동이 곧 취향이다
# ═══════════════════════════════════════════════════════════════

def interest_map(view_counts, fav_counts):
    """카테고리별 관심도를 구한다. 합이 1인 비율이다.

        관심도 = (그 카테고리 열람 수 × 1 + 현재 찜 수 × 3) / (전체 열람×1 + 전체 찜×3)

    '찜은 열람보다 3배 강한 신호'라는 가중치 하나로 암묵 피드백의 핵심을 가르친다.

    찜 수는 clicks 로그가 아니라 **현재 favorites 테이블**에서 센다.
    로그로 세면 찜했다 취소한 기록이 그대로 남아 취향이 왜곡되기 때문이다.

    반환: (관심도 딕셔너리, 신호 총량)  ← 총량으로 콜드 스타트를 판단한다
    """
    scores = {}
    for cat in CATEGORIES:
        scores[cat] = view_counts.get(cat, 0) * 1 + fav_counts.get(cat, 0) * 3
    total = sum(scores.values())
    if total == 0:
        return {cat: EVEN for cat in CATEGORIES}, 0
    return {cat: scores[cat] / total for cat in CATEGORIES}, total


def pref_boost(category, interests, log_count):
    """관심도를 0~1 점수로 바꾼다.

        부스트 = 관심도 / (관심도 + 1/6)

    왜 나눗셈을 한 번 더 하나: 6분류가 균등하면 관심도는 1/6 = 0.167이다.
    그 값을 그대로 쓰면 아무 행동도 안 한 사용자의 부스트가 늘 0.167 —
    다른 두 점수가 0.5 근처에서 노는 동안 혼자 바닥에 깔린다.
    이 식으로 바꾸면 균등에서 정확히 0.5(중립), 한 곳에 몰리면 0.86이 된다.

    ★ 이 식은 §5.1의 보정 별점과 같은 꼴이다 — x / (x + 기준값).
      "관심도를 균등이라는 기준 쪽으로 끌어당긴다". 같은 아이디어를 두 번 만난다.
    """
    if log_count < MIN_LOG:            # 콜드 스타트 — 아직 판단할 근거가 없다
        return 0.5
    x = interests.get(category, 0.0)
    return x / (x + EVEN)


# ═══════════════════════════════════════════════════════════════
# §5.5 최종 점수
# ═══════════════════════════════════════════════════════════════

def normalize_weights(w):
    """가중치 합이 1이 아니면 합으로 나눈다.

    학생은 반드시 0.9/0.9/0.9 같은 값을 넣어 본다. 그래도 서비스가 깨지지 않아야 한다.
    """
    total = sum(w)
    if total <= 0:
        return (0.5, 0.3, 0.2)         # 전부 0을 넣으면 기본값으로 되돌린다
    return tuple(x / total for x in w)


def final_score(s_star, s_dist, s_pref, w=(0.5, 0.3, 0.2)):
    """세 점수를 가중치로 합친다. 셋 다 0~1이므로 결과도 0~1이다."""
    w_star, w_dist, w_pref = normalize_weights(w)
    return w_star * s_star + w_dist * s_dist + w_pref * s_pref


def rank_places(places, origin, interests, log_count, w=(0.5, 0.3, 0.2),
                adj_min=None, adj_max=None):
    """장소 목록에 점수를 매겨 정렬해 돌려준다.

    places : DB에서 읽은 장소 딕셔너리 목록 (adj_star 컬럼이 들어 있어야 한다)
    origin : 거리를 재는 기준점 장소. None이면 거리 점수는 전부 중립(0.5)

    동점 규칙(§5.5): final 내림차순 → 방문자리뷰 내림차순 → id 오름차순.
    별점 없는 장소들은 보정 별점이 정확히 같아서, 이 규칙이 없으면
    새로고침할 때마다 순위가 바뀐다.
    """
    if adj_min is None:
        adj_min = min(p["adj_star"] for p in places)
    if adj_max is None:
        adj_max = max(p["adj_star"] for p in places)

    scored = []
    for p in places:
        item = dict(p)
        item["s_star"] = star_score(p["adj_star"], adj_min, adj_max)

        km = distance_km_between(origin, p)
        item["km"] = km
        item["s_dist"] = 0.5 if km is None else distance_score(km)

        item["s_pref"] = pref_boost(p["category"], interests, log_count)
        item["final"] = final_score(item["s_star"], item["s_dist"], item["s_pref"], w)
        scored.append(item)

    scored.sort(key=lambda x: (-x["final"], -x["visitor_rev"], x["id"]))

    # 마커 크기 3단계(상·중·하)를 붙인다. 순위 기준으로 1/3씩 나눈다.
    n = len(scored)
    for i, item in enumerate(scored):
        item["rank"] = i + 1
        item["size"] = "big" if i < n / 3 else ("mid" if i < n * 2 / 3 else "small")
    return scored


# ═══════════════════════════════════════════════════════════════
# /stats 용 — 보정 전/후 랭킹 비교 (수업 데모의 클라이맥스)
# ═══════════════════════════════════════════════════════════════

def rank_compare(places):
    """보정 전 랭킹과 보정 후 랭킹을 나란히 놓고 순위 변동을 구한다.

    비교 대상은 **별점이 있는 장소만**이다.
    별점이 없는 곳은 '보정 전 랭킹' 자체가 존재하지 않으므로 뺀다.

    보정 전 : star 내림차순 (동점이면 방문자리뷰 많은 쪽이 위)
    보정 후 : adj_star 내림차순 (동점 규칙 동일)
    delta   : 양수면 순위가 올라간 것 (예: 4위 → 1위면 +3)
    """
    rated = [p for p in places if p.get("star") is not None]

    before = sorted(rated, key=lambda p: (-p["star"], -p["visitor_rev"], p["id"]))
    after = sorted(rated, key=lambda p: (-p["adj_star"], -p["visitor_rev"], p["id"]))

    before_rank = {p["id"]: i + 1 for i, p in enumerate(before)}
    after_rank = {p["id"]: i + 1 for i, p in enumerate(after)}

    rows = []
    for p in after:
        b, a = before_rank[p["id"]], after_rank[p["id"]]
        item = dict(p)
        item["rank_before"] = b
        item["rank_after"] = a
        item["delta"] = b - a
        rows.append(item)
    return rows


def big_flips(places, threshold=3):
    """순위가 threshold 계단 이상 움직인 장소만 골라낸다 (검증 5번)."""
    return [r for r in rank_compare(places) if abs(r["delta"]) >= threshold]
