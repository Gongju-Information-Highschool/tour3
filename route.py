# -*- coding: utf-8 -*-
"""
route.py — 찜 목록을 '다니기 좋은 순서'로 정렬한다 (§5.6)

이 서비스는 코스를 **추천하지 않는다.** 학생이 고른 곳을 정렬만 해 준다.
(v2.4와 역할 분담이 다른 지점이다)

    ① 가장 북쪽 장소에서 출발
    ② 남은 곳 중 가장 가까운 곳으로 이동 (최근접 이웃 탐욕법)
    ③ 반복 → 방문 순서 + 구간별 이동시간
    ④ "이 방법은 최적해를 보장하지 않는다"를 화면에 명시 — 한계도 교육 내용
"""

from geo import distance_km

# 도보로 갈 만한 거리의 경계(km). 이보다 멀면 차로 간다고 본다.
WALK_LIMIT_KM = 3.0

WALK_KMH = 4.0      # 사람 걷는 속도
CAR_KMH = 40.0      # 공주 시내·외곽을 섞어 잡은 자동차 평균 속도
DETOUR = 1.3        # 실제 길은 직선이 아니다. 직선거리에 1.3배.


def travel_minutes(km):
    """구간 이동시간(분)과 이동 수단을 함께 돌려준다.

    v1.0은 도보 4km/h 하나로만 계산했다. 그런데 공주 30곳은 반경 30km에
    흩어져 있어서, 공산성 → 마곡사 14.7km가 화면에 **'도보 286분'**으로 찍혔다.
    학생이 결과를 믿지 않는 순간 수업은 끝난다.
    그래서 3km를 경계로 도보와 차량을 나눈다.
      (검산: 공산성 → 마곡사 14.7km → 약 29분. v2.4의 실측 30분과 맞는다)
    """
    road_km = km * DETOUR
    if km <= WALK_LIMIT_KM:
        return round(road_km / WALK_KMH * 60), "도보"
    return round(road_km / CAR_KMH * 60), "차량"


def nearest_neighbor(places):
    """가장 북쪽에서 출발해, 매번 가장 가까운 곳으로 옮겨 가며 순서를 정한다.

    이것이 탐욕(greedy) 알고리즘이다. 매 순간 가장 좋아 보이는 선택을 하지만
    전체로 보면 최선이 아닐 수 있다. 그 한계를 화면에 적어 함께 가르친다.
    """
    remaining = list(places)
    if not remaining:
        return []

    # ① 가장 북쪽(위도가 가장 큰 곳)을 출발점으로
    current = max(remaining, key=lambda p: p["lat"])
    remaining.remove(current)
    order = [current]

    # ② 남은 곳 중 가장 가까운 곳으로
    while remaining:
        nxt = min(remaining, key=lambda p: distance_km(current, p))
        remaining.remove(nxt)
        order.append(nxt)
        current = nxt
    return order


def total_km(ordered):
    """정해진 순서대로 돌 때의 총 이동 거리(km, 직선 기준)."""
    return sum(distance_km(a, b) for a, b in zip(ordered, ordered[1:]))


def route_plan(places):
    """동선 결과 한 벌을 만든다.

    반환 딕셔너리
        order    : 방문 순서대로의 장소 목록
        legs     : 구간별 [출발, 도착, 거리, 분, 수단]
        total_min: 총 이동시간(분)
        total_km : 총 이동거리(km)
        has_car  : 차로 가야 하는 구간이 있는가 (있으면 화면에 경고를 띄운다)
    """
    order = nearest_neighbor(places)

    legs = []
    for a, b in zip(order, order[1:]):
        km = distance_km(a, b)
        minutes, mode = travel_minutes(km)
        legs.append({
            "from": a["name"], "to": b["name"],
            "km": round(km, 1), "minutes": minutes, "mode": mode,
        })

    return {
        "order": order,
        "legs": legs,
        "total_min": sum(leg["minutes"] for leg in legs),
        "total_km": round(sum(leg["km"] for leg in legs), 1),
        "has_car": any(leg["mode"] == "차량" for leg in legs),
    }
