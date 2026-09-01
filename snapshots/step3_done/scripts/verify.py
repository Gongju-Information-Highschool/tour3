# -*- coding: utf-8 -*-
"""
verify.py — 수업 전날 이것 하나로 전부 확인한다 (기획안 §10, 13항목)

결과는 세 가지다.
    PASS     통과
    FAIL     고쳐야 한다
    PENDING  코드는 맞는데 **데이터 수집(A2)이 아직**이라 판단할 수 없다
             ← 임시 시드로 돌리는 동안만 나온다

실행:  python scripts/verify.py
"""

import itertools
import os
import sys

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import db            # noqa: E402
import geo           # noqa: E402
import route as route_lib  # noqa: E402
import scoring       # noqa: E402

RESULTS = []


def check(no, title, fn):
    """항목 하나를 확인한다. fn은 (상태, 설명)을 돌려준다."""
    try:
        state, detail = fn()
    except Exception as e:                      # 실패해도 나머지 항목은 계속 본다
        state, detail = "FAIL", f"예외: {type(e).__name__}: {e}"
    RESULTS.append((no, title, state, detail))


def main():
    params = scoring.load_params()
    m, C = params["m_review"], params["c_mean"]

    conn = db.connect()
    meta = db.get_meta(conn)
    places = db.all_places(conn)

    # ── 0. 행 수 ────────────────────────────────────────────────
    def c0():
        import csv
        with open(os.path.join(ROOT, "data", "places_raw.csv"),
                  encoding="utf-8-sig", newline="") as f:
            raw = len(list(csv.DictReader(f)))
        ok = raw == 33 and len(places) == 30
        return ("PASS" if ok else "FAIL",
                f"원본 {raw}행 → 적재 {len(places)}행 (기대: 33 → 30)")

    # ── 1. 리뷰 수가 전부 정수인가 ──────────────────────────────
    def c1():
        bad = [p["name"] for p in places
               if not isinstance(p["visitor_rev"], int)
               or not isinstance(p["blog_rev"], int)]
        return ("PASS" if not bad else "FAIL",
                f"정수 아님 {len(bad)}건 {bad[:3]}")

    # ── 2. 카테고리 6분류 + 각 4곳 이상 ────────────────────────
    def c2():
        counts = db.category_counts(conn)
        outside = [p["name"] for p in places if p["category"] not in scoring.CATEGORIES]
        if outside:
            return "FAIL", f"표준 6분류 밖 {len(outside)}건 {outside[:3]}"
        thin = {c: n for c, n in counts.items() if n < 4}
        if thin:
            return ("PENDING",
                    f"4곳 미만: {thin} — A2에서 해당 분류 장소를 보강해야 한다(§4.3)")
        return "PASS", f"{counts}"

    # ── 3. 별점 결측이 보정 별점에서는 사라지고, 전부 정확히 C ──
    def c3():
        missing = [p for p in places if p["star"] is None]
        if len(missing) != 5:
            return "FAIL", f"별점 결측이 {len(missing)}건 (기대 5건)"
        off = [p["name"] for p in missing if abs(p["adj_star"] - C) > 1e-9]
        return ("PASS" if not off else "FAIL",
                f"결측 5곳의 보정 별점이 전부 정확히 {C}" if not off
                else f"C와 다른 곳 {off}")

    # ── 4. 손계산 예제와 코드가 소수 2자리까지 같은가 ───────────
    def c4():
        bad = []
        for key, ex in params["hand_calc"].items():
            got = scoring.adjusted_star(ex["R"], ex["v"], m, C)
            if round(got, 2) != round(ex["expect"], 2):
                bad.append(f"{ex['name']} 기대 {ex['expect']} / 계산 {got:.4f}")
        return ("PASS" if not bad else "FAIL",
                "params.json 의 두 예제 모두 일치" if not bad else "; ".join(bad))

    # ── 5. 보정 전/후 순위가 3계단 이상 움직인 곳 3곳 이상 ──────
    def c5():
        flips = scoring.big_flips(places, threshold=3)
        top = sorted(flips, key=lambda r: -abs(r["delta"]))[:3]
        detail = ", ".join(f"{r['name']}({r['rank_before']}→{r['rank_after']})" for r in top)
        return ("PASS" if len(flips) >= 3 else "FAIL",
                f"{len(flips)}곳 (기대 3곳 이상) · {detail}")

    # ── 6. 정규화하면 최소 0, 최대 1 ───────────────────────────
    def c6():
        vals = [scoring.star_score(p["adj_star"], meta["adj_min"], meta["adj_max"])
                for p in places]
        ok = abs(min(vals)) < 1e-9 and abs(max(vals) - 1) < 1e-9
        return ("PASS" if ok else "FAIL", f"min {min(vals):.3f} / max {max(vals):.3f}")

    # ── 7. 거리 점수 ───────────────────────────────────────────
    def c7():
        same = scoring.distance_score(0.0)
        one = scoring.distance_score(1.0)
        ok = round(same, 3) == 1.0 and round(one, 3) == 0.5
        return ("PASS" if ok else "FAIL", f"0km → {same:.3f}, 1km → {one:.3f}")

    # ── 8. 콜드 스타트와 균등 분포 모두 0.5 ────────────────────
    def c8():
        even, n = scoring.interest_map({}, {})
        cold = scoring.pref_boost("역사문화", even, n)          # 로그 0건
        many = {c: 10 for c in scoring.CATEGORIES}
        flat, total = scoring.interest_map(many, {})            # 균등하지만 로그는 많음
        neutral = scoring.pref_boost("역사문화", flat, total)
        ok = abs(cold - 0.5) < 1e-9 and abs(neutral - 0.5) < 1e-9
        return ("PASS" if ok else "FAIL",
                f"콜드스타트 {cold:.3f} / 균등 {neutral:.3f} (둘 다 0.5여야 한다)")

    # ── 9. 동선이 무작위보다 짧은가 (4곳 전수 24순열과 비교) ────
    def c9():
        four = [p for p in places if p["name"] in
                ("공산성", "국립공주박물관", "곡물집", "공주한옥마을")]
        if len(four) != 4:
            return "FAIL", "검증용 4곳을 찾지 못했다"
        nn_km = route_lib.total_km(route_lib.nearest_neighbor(four))
        alls = [route_lib.total_km(list(perm)) for perm in itertools.permutations(four)]
        avg, best = sum(alls) / len(alls), min(alls)
        ok = nn_km <= avg + 1e-9
        return ("PASS" if ok else "FAIL",
                f"최근접이웃 {nn_km:.2f}km · 24순열 평균 {avg:.2f}km · 최적 {best:.2f}km "
                f"(최적 대비 +{(nn_km - best) / best * 100:.1f}%)")

    # ── 10. 3km 초과는 차량으로, 공산성→마곡사 30±3분 ──────────
    def c10():
        by_name = {p["name"]: p for p in places}
        km = geo.distance_km(by_name["공산성"], by_name["마곡사"])
        minutes, mode = route_lib.travel_minutes(km)
        near = route_lib.travel_minutes(1.0)
        ok = mode == "차량" and 27 <= minutes <= 33 and near[1] == "도보"
        return ("PASS" if ok else "FAIL",
                f"공산성→마곡사 {km:.1f}km → {mode} {minutes}분 (기대 차량 30±3분), "
                f"1km → {near[1]} {near[0]}분")

    # ── 11. 인터넷 없이도 전 라우트가 200 ──────────────────────
    def c11():
        os.environ["MAPGONGJU_FORCE_OFFLINE"] = "1"   # 타일 확인을 건너뛴다
        import app as app_module
        app_module.MAP_MODE = "svg"                  # 오프라인 상태를 흉내 낸다
        client = app_module.app.test_client()

        paths = ["/", "/panel/1", "/favorites", "/stats", "/offline",
                 "/?cat=역사문화&w_star=0.9&w_dist=0.9&w_pref=0.9"]
        bad = []
        for path in paths:
            res = client.get(path)
            if res.status_code != 200:
                bad.append(f"{path}={res.status_code}")

        res = client.post("/fav/1", data={"back": "/favorites"})
        if res.status_code not in (302, 303):
            bad.append(f"POST /fav/1={res.status_code}")
        client.post("/fav/2", data={"back": "/favorites"})
        res = client.post("/route")
        if res.status_code != 200:
            bad.append(f"POST /route={res.status_code}")

        return ("PASS" if not bad else "FAIL",
                f"라우트 {len(paths) + 2}개 확인" if not bad else ", ".join(bad))

    # ── 12. init_db 재실행 안전 ────────────────────────────────
    def c12():
        import subprocess
        before = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        # 윈도우에서는 encoding을 지정하지 않으면 cp949로 읽다가 한글에서 깨진다
        r = subprocess.run([sys.executable, os.path.join(HERE, "init_db.py")],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        after = db.connect().execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        ok = before == after and "바꾸지 않았습니다" in r.stdout
        return ("PASS" if ok else "FAIL",
                f"재실행 전후 찜 {before} → {after} (보존되어야 한다)")

    checks = [
        (0, "원본 33행 → 정제 30행", c0),
        (1, "리뷰 수 전부 정수 (콤마 잔존 0건)", c1),
        (2, "표준 6분류 안 + 분류별 4곳 이상", c2),
        (3, "별점 결측 5건 → 보정 별점은 전부 C", c3),
        (4, "손계산 예제와 코드가 소수 2자리 일치", c4),
        (5, "보정 전/후 순위 3계단 이상 변동 3곳", c5),
        (6, "정규화 후 최소 0.0 / 최대 1.0", c6),
        (7, "거리 점수 0km→1.0, 1km→0.5", c7),
        (8, "콜드스타트·균등 모두 취향 부스트 0.5", c8),
        (9, "동선이 24순열 평균보다 짧다", c9),
        (10, "3km 초과는 차량 / 공산성→마곡사 30분", c10),
        (11, "오프라인에서 전 라우트 200", c11),
        (12, "init_db 재실행해도 찜·로그 보존", c12),
    ]
    for no, title, fn in checks:
        check(no, title, fn)

    # ── 결과 출력 ──────────────────────────────────────────────
    print("=" * 78)
    print("검증 결과 (기획안 §10)")
    print("=" * 78)
    mark = {"PASS": "[ O ]", "FAIL": "[ X ]", "PENDING": "[ ? ]"}
    for no, title, state, detail in RESULTS:
        print(f"{mark[state]} {no:>2}. {title}")
        print(f"          {detail}")

    n_pass = sum(1 for *_, s, _ in RESULTS if s == "PASS")
    n_fail = sum(1 for *_, s, _ in RESULTS if s == "FAIL")
    n_pend = sum(1 for *_, s, _ in RESULTS if s == "PENDING")
    print("-" * 78)
    print(f"통과 {n_pass} · 실패 {n_fail} · 수집대기 {n_pend}  / 전체 {len(RESULTS)}")

    if meta.get("data_source") == "placeholder":
        print()
        print("★ 지금은 임시 데이터로 검증했습니다. 별점·리뷰수는 실제 값이 아닙니다.")
        print("  A2(네이버플레이스 수집)를 마친 뒤 이 스크립트를 다시 돌려야")
        print("  5번(순위 뒤집힘)이 진짜로 통과했는지 알 수 있습니다.")

    conn.close()
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
