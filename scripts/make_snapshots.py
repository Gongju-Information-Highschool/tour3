# -*- coding: utf-8 -*-
"""
make_snapshots.py — Step별 완성본을 만든다 (기획안 §14 '학생별 진도 편차' 대비)

수업에서 가장 자주 일어나는 사고는 **한 학생이 Step 4에서 막혀 나머지를 통째로 놓치는 것**이다.
그때 `snapshots/step4_done/` 을 복사해 주면 그 지점부터 다시 따라올 수 있다.

각 스냅샷은 **그 단계까지 끝낸 상태**이며, 그대로 `python app.py` 가 돌아간다.
(돌아가지 않는 스냅샷은 아무 쓸모가 없다 — 이 스크립트가 그것까지 확인한다)

    step3_done  지도에 마커 30개까지          (정제·적재·지도)
    step4_done  + 보정 별점                   (손계산 차시 완료 지점)
    step5_done  + 정규화·거리·취향·랭킹
    step6_done  + 상세 패널·찜·클릭 로그
    step7_done  + 동선·통계  (= 완성본)

데이터가 바뀌면(A2 이후) **이 스크립트를 다시 돌려야 한다.**

실행:  python scripts/make_snapshots.py
"""

import os
import shutil
import subprocess
import sys

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "snapshots")

# 어느 스냅샷에도 들어가지 않는 것들
NEVER = {"snapshots", "dist", "__pycache__", ".git", ".claude"}
NEVER_FILES = {
    os.path.join("data", "_expected_places.csv"),   # 교사용 정답
    os.path.join("data", "place.db"),               # 학생이 직접 만든다
    os.path.join("scripts", "make_snapshots.py"),
    os.path.join("scripts", "make_dist.py"),
}

# 단계마다 **빼는** 파일 (그 단계에서는 아직 없어야 하는 것)
STEPS = {
    "step3_done": [
        os.path.join("templates", "panel.html"),
        os.path.join("templates", "favorites.html"),
        os.path.join("templates", "route.html"),
        os.path.join("templates", "stats.html"),
        "route.py",
    ],
    "step4_done": [
        os.path.join("templates", "panel.html"),
        os.path.join("templates", "favorites.html"),
        os.path.join("templates", "route.html"),
        os.path.join("templates", "stats.html"),
        "route.py",
    ],
    "step5_done": [
        os.path.join("templates", "favorites.html"),
        os.path.join("templates", "route.html"),
        os.path.join("templates", "stats.html"),
        "route.py",
    ],
    "step6_done": [
        os.path.join("templates", "route.html"),
        os.path.join("templates", "stats.html"),
        "route.py",
    ],
    "step7_done": [],          # 완성본
}

# 단계마다 app.py 에서 **잘라 내는** 라우트
#   (파일을 지우면 라우트가 템플릿을 못 찾아 500이 난다. 라우트도 같이 뺀다)
CUT_ROUTES = {
    "step3_done": ["panel", "toggle_fav", "favorites", "make_route", "stats"],
    "step4_done": ["panel", "toggle_fav", "favorites", "make_route", "stats"],
    "step5_done": ["toggle_fav", "favorites", "make_route", "stats"],
    "step6_done": ["make_route", "stats"],
    "step7_done": [],
}

STEP_NOTE = {
    "step3_done": "3차시까지: 정제 → DB 적재 → 지도에 마커 30개",
    "step4_done": "4차시(5-6차시)까지: 보정 별점 + 손계산 검증",
    "step5_done": "7차시까지: 정규화·거리·취향 부스트·최종 점수 랭킹",
    "step6_done": "8차시까지: 상세 패널 · 찜 · 클릭 로그",
    "step7_done": "9차시까지: 동선 · 보정 전/후 통계 (완성본)",
}


def copy_tree(dst):
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in NEVER]
        rel_folder = os.path.relpath(folder, ROOT)
        for name in files:
            if name.endswith(".pyc"):
                continue
            rel = os.path.normpath(os.path.join(rel_folder, name))
            if rel in NEVER_FILES:
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(os.path.join(folder, name), target)


def cut_routes(app_path, names):
    """app.py에서 지정한 뷰 함수 블록을 통째로 들어낸다.

    라우트는 `@app.route(...)` 로 시작해 다음 `@app.route` 나
    `if __name__` 전까지가 한 덩어리다.
    """
    if not names:
        return
    src = open(app_path, encoding="utf-8").read()
    lines = src.split("\n")

    out, skip = [], False
    for i, line in enumerate(lines):
        if line.startswith("@app.route("):
            # 이 데코레이터가 붙은 함수 이름을 앞에서 찾아 둔다
            func = ""
            for nxt in lines[i:i + 4]:
                if nxt.startswith("def "):
                    func = nxt[4:].split("(")[0]
                    break
            skip = func in names
        elif line.startswith("if __name__"):
            skip = False
        if not skip:
            out.append(line)

    open(app_path, "w", encoding="utf-8").write("\n".join(out))


def main():
    if os.path.exists(OUT):
        # 윈도우에서는 방금 실행한 파이썬이 __pycache__를 붙잡고 있어 지워지지 않을 때가 있다.
        shutil.rmtree(OUT, ignore_errors=True)

    results = []
    for step, drop in STEPS.items():
        dst = os.path.join(OUT, step)
        copy_tree(dst)

        for rel in drop:
            path = os.path.join(dst, rel)
            if os.path.exists(path):
                os.remove(path)

        # route.py를 뺐으면 app.py의 import도 같이 빼야 한다.
        # (파일만 지우면 서버가 뜨자마자 ModuleNotFoundError로 죽는다)
        app_path = os.path.join(dst, "app.py")
        if not os.path.exists(os.path.join(dst, "route.py")):
            text = open(app_path, encoding="utf-8").read()
            text = text.replace("import route as route_lib\n", "")
            open(app_path, "w", encoding="utf-8").write(text)

        cut_routes(app_path, CUT_ROUTES[step])

        with open(os.path.join(dst, "여기까지.txt"), "w", encoding="utf-8") as f:
            f.write(f"{step}\n{STEP_NOTE[step]}\n\n"
                    "막힌 지점부터 이어가려면 이 폴더를 통째로 복사해서 쓰세요.\n"
                    "  python scripts/init_db.py\n"
                    "  python app.py\n")

        # ── 정말로 도는지 확인한다 ──────────────────────────────
        subprocess.run([sys.executable, "-B", os.path.join(dst, "scripts", "init_db.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=dst)
        check = subprocess.run(
            [sys.executable, "-B", "-c",
             "import app; c = app.app.test_client();"
             " print(c.get('/').status_code)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dst)
        ok = check.stdout.strip().endswith("200")
        results.append((step, ok, check.stderr.strip().split("\n")[-1] if not ok else ""))

    print("=" * 70)
    print("Step별 완성본을 만들었습니다 :", OUT)
    print("=" * 70)
    for step, ok, err in results:
        print(f"  [{'O' if ok else 'X'}] {step:<12} {STEP_NOTE[step]}")
        if err:
            print(f"        {err}")
    print()
    print("  데이터를 바꾸면(A2 이후) 이 스크립트를 다시 돌리세요.")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
