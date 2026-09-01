# -*- coding: utf-8 -*-
"""
make_dist.py — 학생 배포본을 만든다

교사용 정답과 DB를 빼고 dist/ 폴더에 복사한다.
학생은 dist/ 를 받아 init_db.py 부터 시작한다.

빼는 것
    data/_expected_places.csv   교사용 정답 (정제 결과)
    data/places_clean.csv       정제 결과 — 학생이 직접 만들어야 한다
    data/place.db               DB — 학생이 직접 만들어야 한다
    scripts/make_placeholder_seed.py  임시 시드 생성기 (A2 후에는 쓰지 않는다)
    __pycache__, .git 등

실행:  python scripts/make_dist.py
"""

import os
import shutil

import console_utf8  # noqa: F401  (윈도우 콘솔 한글 출력 보호)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")

EXCLUDE_FILES = {
    os.path.join("data", "_expected_places.csv"),
    os.path.join("data", "places_clean.csv"),
    os.path.join("data", "place.db"),
    os.path.join("scripts", "make_placeholder_seed.py"),
    os.path.join("scripts", "make_dist.py"),
}
EXCLUDE_DIRS = {"__pycache__", ".git", ".claude", "dist", "snapshots"}


def main():
    if os.path.exists(DIST):
        shutil.rmtree(DIST)

    copied, skipped = 0, []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel_folder = os.path.relpath(folder, ROOT)

        for name in files:
            if name.endswith(".pyc"):
                continue
            rel = os.path.normpath(os.path.join(rel_folder, name))
            if rel in EXCLUDE_FILES:
                skipped.append(rel)
                continue

            dst = os.path.join(DIST, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(folder, name), dst)
            copied += 1

    print(f"배포본을 만들었습니다 : {DIST}")
    print(f"  복사 {copied}개 / 제외 {len(skipped)}개")
    for rel in sorted(skipped):
        print(f"    - {rel}")
    print()
    print("  학생에게는 dist/ 폴더를 통째로 주면 됩니다.")
    print("  학생 첫 명령 : python scripts/preprocess.py")


if __name__ == "__main__":
    main()
