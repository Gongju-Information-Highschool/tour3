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

기획안 §10의 13항목 + 확장 회귀 3항목을 한 번에 확인한다.
결과는 `[ O ] 통과` / `[ X ] 실패` / `[ ? ] 수집 대기` 세 가지다.

교재를 인쇄하기 전에는 대본과 코드가 어긋나지 않았는지도 본다.

```bash
python scripts/check_prompts.py
```

학생이 중간에 막혔을 때 건네줄 Step별 완성본을 만든다 (각 폴더가 실제로 도는지까지 확인한다).

```bash
python scripts/make_snapshots.py
```

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
| `scripts/check_prompts.py` | 대본 ↔ 코드 정합성 10항목 |
| `scripts/make_snapshots.py` | Step별 완성본 생성 + 실행 확인 |
| `scripts/make_dist.py` | 학생 배포본 생성 |
| `프롬프트_대본.md` | 학생이 순서대로 입력할 Claude Code 프롬프트 |

## 지도가 안 뜨면

정상이다. `static/leaflet/` 에 라이브러리가 없거나 타일 서버에 닿지 않으면
**좌표로 그린 위치 관계 그림(SVG)** 으로 자동으로 바뀐다. 점수·필터·찜·동선은 그대로 동작한다.
진짜 지도를 쓰려면 [static/leaflet/README.md](static/leaflet/README.md) 를 보라.

서버를 켤 때 어느 쪽인지 찍힌다.

```
지도 방식 : svg   (leaflet 번들 없음 / 타일서버 연결됨)
```

---

## Vercel로 인터넷에 띄우기

```bash
npm i -g vercel
vercel login
vercel --prod
```

또는 [vercel.com/new](https://vercel.com/new)에서 `Gongju-Information-Highschool/tour3` 저장소를
그대로 Import 하면 된다. 설정은 건드릴 것이 없다 (`vercel.json`이 이미 있다).

### 어떻게 돌아가나

| 파일 | 하는 일 |
|---|---|
| `api/index.py` | Vercel이 부르는 진입점. DB를 `/tmp`로 복사하고 `app`을 내보낸다 |
| `vercel.json` | 모든 주소(`/`, `/stats` …)를 `api/index.py`로 넘긴다 |
| `requirements.txt` | 서버 실행에 필요한 것만 (flask). pandas는 `requirements-dev.txt`로 옮겼다 |

전처리 스크립트를 돌릴 때는 `pip install -r requirements-dev.txt`.

### 알아 둘 것 — 기록이 남지 않는다

Vercel에 올라간 파일은 **읽기 전용**이다. `data/place.db`에 직접 쓸 수 없어서,
서버가 뜰 때마다 DB를 `/tmp`로 복사해서 쓴다.

그래서 사용자가 남긴 기록은 **잠시 뒤 사라지고, 접속자마다 다를 수도 있다.**
관광지 목록·추천 알고리즘 같은 읽기 기능은 전부 정상 동작한다.
발표·시연용으로는 충분하지만, 수업 중 모은 데이터를 계속 쌓으려면 아래 중 하나가 필요하다.

- **노트북에서 `python app.py`로 실행** — 원래 방식. 기록이 그대로 남는다 (권장)
- **외부 DB로 교체** — [Turso](https://turso.tech)(SQLite 호환) 또는 Vercel Postgres.
  `db.py`의 연결 부분만 고치면 된다
