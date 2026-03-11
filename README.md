# 데이터로 이해하는 이란 전쟁

서울대학교 행정대학원 고길곤 교수 연구실 · 아시아 지역정보센터

이란·이스라엘 갈등을 국가 역량, 금융시장 신호, 거버넌스 데이터로 분석하는 웹 대시보드입니다.

---

## 실행 방법 (Windows)

### Step 1 — 최초 설치 (한 번만)

`setup.bat` 파일을 **더블클릭**합니다.

- **Python이 없어도 자동으로 설치**합니다 (인터넷 연결 필요).
- 가상환경(`.venv`)을 자동으로 만들고 필요한 패키지를 설치합니다.
- 처음 실행 시 수 분이 걸릴 수 있습니다.
- `"설치가 모두 완료되었습니다"` 메시지가 뜨면 완료입니다.

> Python 설치 단계에서 **관리자 권한 창**이 뜨면 "예"를 클릭하세요.

---

### Step 2 — 서버 실행 (매번)

`run.bat` 파일을 **더블클릭**합니다.

- 서버가 시작되면 브라우저가 자동으로 열립니다.
- 브라우저가 열리지 않으면 직접 주소창에 입력하세요:

```
http://127.0.0.1:5000
```

- 서버를 종료하려면 실행 창(검정 화면)에서 `Ctrl + C`를 누르세요.

---

## 페이지 구성

| 페이지 | 주소 | 내용 |
|--------|------|------|
| 왜 데이터인가 | /why | 이 플랫폼의 목적과 데이터 소개 |
| 국가자원/국방력 | / | World Bank — GDP·군사비·무기수입 등 국가 역량 비교 |
| 위기 진단 | /crisis | Yahoo Finance — 유가·VIX·환율·주가 실시간 추세 |
| 거버넌스/민주주의 | /governance | WGI · Freedom House · V-Dem 지수 |
| 뉴스 스크랩 | /news | Google News·Reuters·BBC·Al Jazeera 이란 관련 뉴스 |
| 미사일 공격상황 | /map | 중동 미사일 공격 현황 지도 |

---

## 데이터 출처

- **World Bank Open Data** — 국가 역량 지표
- **Yahoo Finance (yfinance)** — 원자재·공포지수·환율·주가
- **World Bank WGI** — 세계 거버넌스 지표
- **Freedom House** — 자유 지수
- **V-Dem / Our World in Data** — 민주주의 지수
- **Google News RSS / Reuters / BBC / Al Jazeera** — 뉴스

> 일부 데이터(유가·주가 등)는 인터넷 연결 상태에서만 실시간으로 조회됩니다.  
> 인터넷이 없는 경우 샘플 데이터로 대체 표시됩니다.

---

## GCP App Engine 배포

Google Cloud Platform에 배포하려면:

1. [Google Cloud](https://console.cloud.google.com)에서 프로젝트 생성
2. [Cloud SDK](https://cloud.google.com/sdk/docs/install) 설치 후 `gcloud auth login` 및 `gcloud app create` 실행
3. 프로젝트 폴더에서 배포:

```bash
gcloud app deploy
```

배포 후 `https://프로젝트ID.appspot.com` 으로 접속합니다.

---

## 문제 해결

| 증상 | 해결 방법 |
|------|-----------|
| `setup.bat` 실행 시 "Python이 없습니다" | Python을 설치하고 PATH에 추가했는지 확인 |
| 브라우저에서 페이지가 열리지 않음 | `run.bat`이 실행 중인지 확인 후 `http://127.0.0.1:5000` 직접 입력 |
| 유가·주가 데이터가 안 나옴 | 인터넷 연결 확인. 샘플 데이터로 대체 표시됩니다 |
| 뉴스가 안 나옴 | 인터넷 연결 확인. 수집에 30초 이상 소요될 수 있습니다 |

---

*본 자료는 교육·연구 목적으로 제작되었으며 특정 정치적 입장을 지지하지 않습니다.*
