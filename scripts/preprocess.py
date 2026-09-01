# -*- coding: utf-8 -*-
"""
preprocess.py — places_raw.csv(33행)를 places_clean.csv(30행)로 정제한다

기획안 §4.4의 정제 정답:
    33행 → 중복 2건 제거 · 좌표 결측 1건 제외 → 30행
    콤마 6건 숫자화, 카테고리 매핑

정제 순서가 중요하다:
    ① 콤마 제거 → ② 좌표 결측 제외 → ③ 중복 제거 → ④ 카테고리 매핑
  ②를 ④보다 먼저 하는 이유: 좌표가 없어 어차피 버릴 행('공주역' 같은
  관광지가 아닌 검색 결과)의 카테고리까지 매핑표에 넣을 필요가 없다.

실행:  python scripts/preprocess.py
"""

import csv
import os
import sys

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

RAW = os.path.join(DATA, "places_raw.csv")
CLEAN = os.path.join(DATA, "places_clean.csv")
CATMAP = os.path.join(DATA, "category_map.csv")

# 지점 표기 접미사. 중복인지 비교할 때만 떼어 낸다.
#   '점' 한 글자는 떼지 않는다 — '~점'으로 끝나는 멀쩡한 상호를 망가뜨린다.
SUFFIXES = ["공주점", "본점"]


def read_rows(path):
    """CSV를 딕셔너리 목록으로 읽는다.

    pandas가 있으면 pandas로, 없으면 표준 csv 모듈로 읽는다.
    (학교 컴퓨터에서 pandas 설치가 실패해도 수업이 멈추지 않게)
    한글이 깨지지 않도록 encoding='utf-8-sig' 고정.
    """
    try:
        import pandas as pd
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        return df.to_dict("records"), "pandas"
    except ImportError:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f)), "csv 모듈"


def to_int(text):
    """리뷰 수 문자열을 정수로. "1,204" → 1204, 빈칸 → 0"""
    text = (text or "").strip().replace(",", "")
    return int(text) if text else 0


def norm_name(name):
    """중복 비교용으로 이름을 표준화한다. 공백과 지점 접미사를 뗀다."""
    key = "".join((name or "").split())          # 모든 공백 제거
    for suf in SUFFIXES:
        if key.endswith(suf) and len(key) > len(suf):
            key = key[: -len(suf)]
    return key


def load_category_map():
    """네이버 카테고리 원문 → 표준 6분류 매핑표를 읽는다."""
    mapping = {}
    with open(CATMAP, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            mapping[row["category_raw"].strip()] = row["category"].strip()
    return mapping


def main():
    rows, reader = read_rows(RAW)
    print(f"[0] 원본 읽기 ({reader}) : {len(rows)}행")

    # ── ① 리뷰 수의 콤마를 없애고 정수로 바꾼다 ────────────────────
    comma_count = 0
    for r in rows:
        if "," in (r.get("visitor_rev") or "") or "," in (r.get("blog_rev") or ""):
            comma_count += 1
        r["visitor_rev"] = to_int(r.get("visitor_rev"))
        r["blog_rev"] = to_int(r.get("blog_rev"))
    print(f"[1] 콤마 표기 숫자화     : {comma_count}행 처리")

    # ── ② 좌표가 없는 행은 지도에 찍을 수 없으므로 제외한다 ─────────
    kept, dropped = [], []
    for r in rows:
        mapx, mapy = (r.get("mapx") or "").strip(), (r.get("mapy") or "").strip()
        if not mapx or not mapy:
            dropped.append(r["name"])
            continue
        # 네이버 mapx/mapy는 10^7을 곱한 정수다. 되돌려서 경도·위도로 만든다.
        r["lon"] = round(int(mapx) / 10 ** 7, 7)
        r["lat"] = round(int(mapy) / 10 ** 7, 7)
        kept.append(r)
    print(f"[2] 좌표 결측 제외       : {len(dropped)}행 제외 {dropped}")

    # ── ③ 중복 제거 — 방문자리뷰가 많은 행을 남긴다 ────────────────
    best = {}
    dup_log = []
    for r in kept:
        key = norm_name(r["name"])
        if key in best:
            loser, winner = sorted([best[key], r], key=lambda x: x["visitor_rev"])
            dup_log.append(f"{loser['name']}(리뷰 {loser['visitor_rev']}) "
                           f"→ {winner['name']}(리뷰 {winner['visitor_rev']}) 로 통합")
            best[key] = winner
        else:
            best[key] = r
    kept = list(best.values())
    print(f"[3] 중복 제거            : {len(dup_log)}건")
    for line in dup_log:
        print(f"      - {line}")

    # ── ④ 카테고리 원문을 표준 6분류로 바꾼다 ──────────────────────
    mapping = load_category_map()
    unmapped = sorted({r["category_raw"] for r in kept if r["category_raw"] not in mapping})
    if unmapped:
        # 오류로 멈추지 않는다. 매핑표에 무엇을 더 넣어야 하는지 알려 준다.
        print(f"[4] ! 매핑표에 없는 카테고리 원문 {len(unmapped)}건 — "
              f"data/category_map.csv 에 추가하세요")
        for raw in unmapped:
            print(f"      - {raw}")
        sys.exit(1)
    for r in kept:
        r["category"] = mapping[r["category_raw"]]
    print(f"[4] 카테고리 매핑        : {len(kept)}행 전부 표준 6분류로 변환")

    # ── 저장 ────────────────────────────────────────────────────
    kept.sort(key=lambda r: r["name"])
    cols = ["name", "category_raw", "category", "road_address",
            "lat", "lon", "star", "visitor_rev", "blog_rev", "collected_at"]
    with open(CLEAN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)

    # ── 요약 ────────────────────────────────────────────────────
    from collections import Counter
    dist = Counter(r["category"] for r in kept)
    no_star = sum(1 for r in kept if not str(r.get("star") or "").strip())

    print()
    print(f"정제 결과 : {len(rows)}행 → {len(kept)}행   ({CLEAN})")
    print(f"별점 결측 : {no_star}건  (보정 별점이 알아서 처리한다 — §5.1)")
    print("카테고리 분포 :")
    for cat in ["역사문화", "자연", "체험", "먹거리", "카페감성", "휴식"]:
        n = dist.get(cat, 0)
        flag = "" if n >= 4 else "   ← 4곳 미만! A2에서 보강 필요 (§4.3)"
        print(f"    {cat:<6} {n:2d}곳{flag}")
    print()
    print("  다음: python scripts/init_db.py")


if __name__ == "__main__":
    main()
