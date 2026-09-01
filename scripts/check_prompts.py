# -*- coding: utf-8 -*-
"""
check_prompts.py — 프롬프트 대본과 실제 코드가 어긋나지 않았는지 본다

교재는 종이로 인쇄된다. 코드를 고치고 대본을 안 고치면
**학생이 인쇄물대로 입력했는데 결과가 다른 상황**이 벌어지고,
그때 학생은 자기가 틀린 줄 안다. 그게 가장 나쁜 실패다.

이 스크립트는 대본(프롬프트_대본.md)에 적힌 약속들이
코드·데이터에 그대로 남아 있는지 확인한다.

실행:  python scripts/check_prompts.py
"""

import json
import os
import re
import sys

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "프롬프트_대본.md")

RESULTS = []


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def check(title, ok, detail):
    RESULTS.append((title, ok, detail))


def main():
    if not os.path.exists(SCRIPT):
        raise SystemExit("프롬프트_대본.md 이 없습니다.")

    doc = read("프롬프트_대본.md")
    scoring_src = read("scoring.py")
    route_src = read("route.py")
    db_src = read("db.py")
    params = json.loads(read("data", "params.json"))

    # ── 1. 대본이 부르는 함수가 코드에 실제로 있는가 ────────────────
    #     대본에 `함수이름(` 형태로 등장하는 것을 모아 확인한다
    promised = {
        "adjusted_star": scoring_src,
        "star_score": scoring_src,
        "distance_score": scoring_src,
        "pref_boost": scoring_src,
        "final_score": scoring_src,
    }
    missing = [name for name, src in promised.items()
               if name in doc and f"def {name}(" not in src]
    check("대본이 부르는 함수가 코드에 있다",
          not missing,
          "없는 함수: " + ", ".join(missing) if missing else
          f"{len(promised)}개 확인")

    # ── 2. 대본에 인쇄된 손계산 정답 = params.json 값 ──────────────
    #     "= 4.34" 같은 꼴을 찾아 params.json의 expect와 맞춰 본다
    printed = set(re.findall(r"=\s*(\d\.\d{2})\b", doc))
    expected = {f"{ex['expect']:.2f}" for ex in params["hand_calc"].values()}
    ok = expected <= printed
    check("대본의 손계산 정답 = params.json",
          ok,
          f"대본 {sorted(expected & printed)} / params {sorted(expected)}"
          if ok else f"대본에 없는 정답: {sorted(expected - printed)}")

    # ── 3. 대본에 적힌 상수가 params.json과 같은가 ────────────────
    m, C = params["m_review"], params["c_mean"]
    ok = f"m = {m}" in doc and f"C = {C:.2f}" in doc
    check("대본의 m·C = params.json",
          ok, f"m = {m}, C = {C:.2f}")

    # ── 4. 대본이 약속한 규칙이 코드에 남아 있는가 ─────────────────
    rules = [
        ("10분 안에 다시 열면 기록하지 않는다",
         "VIEW_DEDUP_MINUTES = 10" in db_src),
        ("3km 경계로 도보·차량을 나눈다",
         "WALK_LIMIT_KM = 3.0" in route_src),
        ("도보 4km/h · 차량 40km/h",
         "WALK_KMH = 4.0" in route_src and "CAR_KMH = 40.0" in route_src),
        ("취향 부스트는 로그 5건 미만이면 0.5",
         "MIN_LOG = 5" in scoring_src),
        ("가중치 합이 1이 아니면 합으로 나눈다",
         "def normalize_weights(" in scoring_src),
        ("동점이면 리뷰 많은 쪽 → id 작은 쪽",
         '-x["visitor_rev"], x["id"]' in scoring_src),
    ]
    for title, ok in rules:
        check(title, ok, "코드에 있음" if ok else "코드에서 사라졌다 — 대본을 고치거나 코드를 되돌리세요")

    # ── 5. 대본이 "JS는 지도 1블록" 이라 했는데 정말 그런가 ─────────
    js_blocks = 0
    tpl_dir = os.path.join(ROOT, "templates")
    for name in os.listdir(tpl_dir):
        if not name.endswith(".html"):
            continue
        html = read("templates", name)
        # 외부 라이브러리를 불러오는 <script src=...>는 세지 않는다
        js_blocks += len(re.findall(r"<script>", html))
    check("JavaScript 블록이 1개뿐이다",
          js_blocks == 1,
          f"{js_blocks}개 발견 (map.html의 지도 초기화 1개여야 한다)")

    # ── 결과 ───────────────────────────────────────────────────
    print("=" * 74)
    print("프롬프트 대본 ↔ 코드 정합성")
    print("=" * 74)
    for title, ok, detail in RESULTS:
        print(f"[ {'O' if ok else 'X'} ] {title}")
        print(f"        {detail}")

    bad = sum(1 for _, ok, _ in RESULTS if not ok)
    print("-" * 74)
    print(f"확인 {len(RESULTS)}항목 · 어긋남 {bad}건")
    if bad:
        print()
        print("교재를 인쇄하기 전에 반드시 맞춰 두세요(§4.5).")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
