# -*- coding: utf-8 -*-
"""
geo.py — 좌표를 다룬다 (거리 계산 + 지도 API 없이 그리는 위치 관계 그림)

v2.4(AI 관광추천)의 geo.py를 이식했다. 두 가지를 쓴다.
  · haversine_km()   : 거리 점수(§5.3)와 동선 이동시간(§5.6)의 바탕
  · project_points() : 인터넷이 없을 때 지도를 대신하는 SVG 산점도(§6.4)

거리 검산값 (상식과 맞는지 확인용, v2.4에서 실측)
    공산성 → 국립공주박물관   1.3km
    공산성 → 마곡사          14.7km
    마곡사 → 동학사          29.4km
"""

import math


def haversine_km(lat1, lon1, lat2, lon2):
    """지구가 둥근 것을 감안해 두 지점 사이 직선거리를 km로 구한다.

    (하버사인 공식. 고등학교 수준을 넘으므로 '이런 공식이 있다' 정도로 넘어가고,
     결과가 상식에 맞는지만 위 검산값으로 확인하면 된다.)
    """
    R = 6371.0                      # 지구 반지름 km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def distance_km(a, b):
    """장소 딕셔너리 두 개 사이의 거리(km)."""
    return haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])


# ═══════════════════════════════════════════════════════════
# 지도 API 없이 위치 관계를 그린다 — 오프라인 폴백(§6.4)
# ═══════════════════════════════════════════════════════════

def project_points(places, focus=None, width=480, height=420, pad=34, min_dist=0,
                   zoom_out=1.6):
    """장소들의 경도·위도를 그림 위의 좌표(x, y)로 바꾼다.

    진짜 지도가 아니라 '어디가 서로 가까운지'를 보여 주는 그림이다.
    타일 서버에 접속할 수 없을 때 Leaflet 지도를 대신한다.

    focus : 축척을 맞출 기준이 되는 장소들. 비우면 전체에 맞춘다.
            (동선 화면에서는 동선에 담긴 곳들에 맞춰 확대한다)
    min_dist : 이 값보다 가까운 점끼리는 살짝 밀어내 겹침을 푼다. 0이면 안 민다.
    zoom_out : 범위에 주는 여유. 번호와 이름이 붙는 동선 그림은 1.6배가 필요하지만,
               점만 찍는 전체 보기에서 1.6배를 주면 여백만 넓어지고
               원도심이 한 덩어리로 뭉친다. 전체 보기는 1.05를 쓴다.
    """
    pts = [p for p in places if p.get("lat") and p.get("lon")]
    if not pts:
        return []

    base = [p for p in (focus or pts) if p.get("lat") and p.get("lon")] or pts

    lat_mid = sum(p["lat"] for p in base) / len(base)
    lon_scale = math.cos(math.radians(lat_mid))    # 경도 1도는 위도 1도보다 짧다

    lons = [p["lon"] for p in base]
    lats = [p["lat"] for p in base]
    cx = (min(lons) + max(lons)) / 2
    cy = (min(lats) + max(lats)) / 2

    # 점들이 가장자리에 붙지 않도록 범위에 여유를 준다
    span_x = (max(lons) - min(lons)) * lon_scale * zoom_out
    span_y = (max(lats) - min(lats)) * zoom_out

    # 너무 좁게 확대하면 점이 화면 밖으로 나가므로 최소 범위를 둔다
    # (위도 0.02도 ≈ 2.2km)
    MIN_SPAN = 0.02
    span_x = max(span_x, MIN_SPAN * lon_scale)
    span_y = max(span_y, MIN_SPAN)

    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)

    out = []
    for p in pts:
        x = width / 2 + (p["lon"] - cx) * lon_scale * scale
        # 위도는 위로 갈수록 커지는데 화면은 아래로 갈수록 커지므로 뒤집는다
        y = height / 2 - (p["lat"] - cy) * scale
        if not (-pad <= x <= width + pad and -pad <= y <= height + pad):
            continue                     # 확대 범위를 크게 벗어난 곳은 그리지 않는다
        item = dict(p)
        item["x"], item["y"] = round(x, 1), round(y, 1)
        out.append(item)

    if min_dist:
        separate(out, min_dist, width, height, pad)
    return out


def separate(points, min_dist, width, height, pad, rounds=60):
    """너무 가까이 붙은 점을 조금씩 밀어서 떨어뜨린다.

    원도심 장소들은 서로 1km 안쪽이라 그대로 그리면 동그라미가 겹쳐
    무엇이 무엇인지 읽을 수 없다. 위치를 살짝 옮기더라도 보이는 편이 낫다.
    (그래서 이 그림은 '정확한 지도'가 아니라 '위치 관계 그림'이다 —
     화면에도 그렇게 적어 둔다)
    """
    for _ in range(rounds):
        moved = False
        for i, a in enumerate(points):
            for b in points[i + 1:]:
                dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                dist = math.hypot(dx, dy)
                if dist >= min_dist:
                    continue
                if dist < 1e-6:              # 완전히 같은 자리면 옆으로 뗀다
                    dx, dy, dist = 1.0, 0.0, 1.0
                push = (min_dist - dist) / 2
                ux, uy = dx / dist, dy / dist
                a["x"] -= ux * push
                a["y"] -= uy * push
                b["x"] += ux * push
                b["y"] += uy * push
                moved = True
        for p in points:                     # 그림 밖으로 밀려나지 않게 가둔다
            p["x"] = min(max(p["x"], pad), width - pad)
            p["y"] = min(max(p["y"], pad), height - pad)
        if not moved:
            break

    for p in points:
        p["x"] = round(p["x"], 1)
        p["y"] = round(p["y"], 1)
