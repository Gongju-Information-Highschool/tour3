# 맵으로 공주 (map-gongju)

공주시 30곳을 지도에서 탐색하고, **보정 별점 · 거리 · 내 클릭 패턴**으로 다시 줄 세운 뒤,
찜한 곳을 다니기 좋은 순서로 정렬해 주는 수업용 웹 서비스.

『AI 관광추천 v2.4』의 자매 프로젝트 — 같은 지역, 완전히 다른 UI·데이터·알고리즘.
설계 근거는 [공주지도탐색_최종개발기획안_v2.md](공주지도탐색_최종개발기획안_v2.md) 에 있다.

---

## 실행 (3줄)

```bash
pip install flask pandas
python scripts/init_db.py
python app.py
```

브라우저에서 `http://127.0.0.1:5000`

처음부터 다시 만들려면 (찜·클릭 기록이 사라진다)

```bash
python scripts/init_db.py --reset
```

## 검증

```bash
python scripts/verify.py
```

기획안 §10의 13항목을 한 번에 확인한다. 결과는 `[ O ] 통과` / `[ X ] 실패` /
`[ ? ] 수집 대기` 세 가지다.

---

## ⚠ 지금 데이터는 임시값이다

| 실제 | 임시 |
|---|---|
| 장소명 30곳, 좌표 | 별점, 방문자리뷰 수, 블로그리뷰 수 |

별점과 리뷰 수를 실제 네이버플레이스에서 옮겨 적는 작업(기획안 §8 **A2**, 약 3시간)이
남아 있다. 절차는 [scripts/collect_guide.md](scripts/collect_guide.md) 에 있다.

임시 상태는 화면 상단 배너 · `init_db.py` 출력 · `verify.py` 결과에 모두 표시되므로
학생에게 실제 값으로 오해될 일은 없다. A2를 마치면 CSV를 교체하고
`data/params.json` 의 `data_source` 를 `"naver_place"` 로 바꾸면 배너가 출처 표기로 바뀐다.

---

## 파일 지도

| 파일 | 역할 |
|---|---|
| `app.py` | 서버 + 라우팅 7개 |
| **`scoring.py`** | **보정 별점 · 정규화 · 거리 · 취향 부스트 — 수업의 핵심** |
| `route.py` | 최근접 이웃 동선 + 도보/차량 이동시간 |
| `geo.py` | 하버사인 거리 + 좌표 → SVG 변환 (v2.4에서 이식) |
| `db.py` | SQLite 조회·기록 함수 |
| `data/params.json` | m · C · 손계산 예제의 **단일 출처** |
| `scripts/preprocess.py` | 33행 → 30행 정제 |
| `scripts/init_db.py` | 적재 (인자 없이 재실행하면 아무것도 지우지 않는다) |
| `scripts/verify.py` | 수업 전날 자동 점검 13항목 |
| `scripts/collect_guide.md` | **A2 수집 절차 (남은 사람 손 작업)** |
| `프롬프트_대본.md` | 학생이 순서대로 입력할 Claude Code 프롬프트 |

## 지도가 안 뜨면

정상이다. `static/leaflet/` 에 라이브러리가 없거나 타일 서버에 닿지 않으면
**좌표로 그린 위치 관계 그림(SVG)** 으로 자동으로 바뀐다. 점수·필터·찜·동선은 그대로 동작한다.
진짜 지도를 쓰려면 [static/leaflet/README.md](static/leaflet/README.md) 를 보라.

서버를 켤 때 어느 쪽인지 찍힌다.

```
지도 방식 : svg   (leaflet 번들 없음 / 타일서버 연결됨)
```
