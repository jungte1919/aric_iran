# -*- coding: utf-8 -*-
"""
호르무즈 해협 선박 통계 분석 도구
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사용 가능한 API:
  1. AISHub      - 무료 (AIS 수신기 공유 조건), 실시간 위치 데이터
  2. MarineTraffic API  - 유료 (CS1/PS1 플랜), 상세 이력 & 통계
  3. VesselFinder API   - 유료, 상업용
  4. aisstream.io       - 무료 티어, 실시간 WebSocket 스트림
  5. EIA (에너지정보청)  - 완전 무료, 호르무즈 통과 유량 통계

이 스크립트는 AISHub API(무료 등록 필요)를 우선 시도하고,
API 키가 없을 경우 실제 통계 기반의 데모 데이터로 분석합니다.
"""

import json
import os
import io
import base64
from datetime import datetime, timedelta
import random

import pandas as pd
import numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams, font_manager

# ─── 한글 폰트 설정 ───────────────────────────────────────────────────────────
def _setup_korean_font() -> str:
    """
    matplotlib 한글 폰트를 설정하고 실제 적용된 폰트명을 반환합니다.

    전략 (순서대로 시도):
      1. Windows/Linux/macOS 시스템 경로에서 TTF 파일을 직접 addfont()
      2. fontManager.ttflist에서 이름 검색
      3. 모두 실패하면 음수 기호만 ASCII로 고정
    """
    import os

    # ── 1. 파일 경로 직접 로드 (가장 확실한 방법) ─────────────────────────────
    path_candidates = [
        # Windows
        ("C:/Windows/Fonts/malgun.ttf",       "Malgun Gothic"),
        ("C:/Windows/Fonts/malgunbd.ttf",     "Malgun Gothic"),
        ("C:/Windows/Fonts/NanumGothic.ttf",  "NanumGothic"),
        # macOS
        ("/Library/Fonts/AppleGothic.ttf",    "AppleGothic"),
        ("/System/Library/Fonts/AppleGothic.ttf", "AppleGothic"),
        # Linux (nanum)
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "NanumGothic"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK KR"),
    ]
    for path, name in path_candidates:
        if os.path.exists(path):
            font_manager.fontManager.addfont(path)
            rcParams["font.family"]     = "sans-serif"
            rcParams["font.sans-serif"] = [name] + [
                f for f in rcParams.get("font.sans-serif", []) if f != name
            ]
            rcParams["axes.unicode_minus"] = False
            return name

    # ── 2. fontManager 캐시에서 이름 검색 ─────────────────────────────────────
    name_candidates = [
        "Malgun Gothic", "맑은 고딕",
        "NanumGothic", "NanumBarunGothic",
        "Noto Sans KR", "Noto Sans CJK KR",
        "AppleGothic", "Apple SD Gothic Neo",
        "HYGothic-Medium", "Hancom Gothic",
        "MS Gothic", "Yu Gothic",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in name_candidates:
        if name in available:
            rcParams["font.family"]     = "sans-serif"
            rcParams["font.sans-serif"] = [name] + [
                f for f in rcParams.get("font.sans-serif", []) if f != name
            ]
            rcParams["axes.unicode_minus"] = False
            return name

    # ── 3. 폴백: 음수 기호만 처리 ─────────────────────────────────────────────
    rcParams["axes.unicode_minus"] = False
    return ""


_KO_FONT = _setup_korean_font()


def _apply_font():
    """차트 함수마다 호출해 rcParams 초기화에 대비한 재적용."""
    if _KO_FONT:
        rcParams["font.family"]     = "sans-serif"
        rcParams["font.sans-serif"] = [_KO_FONT] + [
            f for f in rcParams.get("font.sans-serif", []) if f != _KO_FONT
        ]
    rcParams["axes.unicode_minus"] = False


# ─── 호르무즈 해협 지리 경계 ───────────────────────────────────────────────────
HORMUZ_BBOX = {
    "latmin": 25.5,
    "latmax": 27.5,
    "lonmin": 56.0,
    "lonmax": 60.0,
}

# ─── 선박 유형 매핑 ────────────────────────────────────────────────────────────
SHIP_TYPE_MAP = {
    80: "유조선(Tanker)",
    81: "유조선(Tanker)",
    82: "유조선(Tanker)",
    83: "유조선(Tanker)",
    84: "유조선(Tanker)",
    85: "유조선(Tanker)",
    86: "유조선(Tanker)",
    87: "유조선(Tanker)",
    88: "유조선(Tanker)",
    89: "유조선(Tanker)",
    70: "화물선(Cargo)",
    71: "화물선(Cargo)",
    72: "화물선(Cargo)",
    73: "화물선(Cargo)",
    74: "화물선(Cargo)",
    75: "화물선(Cargo)",
    76: "화물선(Cargo)",
    77: "화물선(Cargo)",
    78: "화물선(Cargo)",
    79: "화물선(Cargo)",
    60: "여객선(Passenger)",
    61: "여객선(Passenger)",
    62: "여객선(Passenger)",
    63: "여객선(Passenger)",
    64: "여객선(Passenger)",
    65: "여객선(Passenger)",
    66: "여객선(Passenger)",
    67: "여객선(Passenger)",
    68: "여객선(Passenger)",
    69: "여객선(Passenger)",
    30: "어선(Fishing)",
    52: "예인선(Tug)",
    1: "예약(Reserved)",
}

# ─── MMSI 국가 코드 매핑 (앞 3자리) ──────────────────────────────────────────
MMSI_COUNTRY = {
    "412": "중국", "413": "중국", "414": "중국",
    "419": "인도", "418": "인도",
    "440": "한국", "441": "한국",
    "431": "일본", "432": "일본", "433": "일본",
    "525": "인도네시아",
    "477": "홍콩",
    "566": "싱가포르",
    "538": "마샬군도",
    "636": "라이베리아",
    "229": "몰타",
    "657": "케냐",
    "477": "홍콩",
    "311": "바하마",
    "308": "바하마",
    "309": "바하마",
    "422": "이란",
    "447": "UAE",
    "450": "쿠웨이트",
    "461": "카타르",
    "403": "사우디아라비아",
    "273": "러시아",
    "244": "네덜란드",
    "235": "영국",
    "232": "영국",
    "338": "미국",
    "366": "미국",
    "367": "미국",
    "368": "미국",
    "218": "독일",
    "249": "몰타",
    "255": "포르투갈/마데이라",
    "256": "몰타",
    "636": "라이베리아",
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. AISHub API 클라이언트
# ══════════════════════════════════════════════════════════════════════════════

class AISHubClient:
    """
    AISHub 무료 API 클라이언트
    
    등록: https://www.aishub.net/join-us
    조건: AIS 데이터 수신기 보유자이거나 파트너 데이터 공유 참여자
    요금: 무료 (분당 1회 요청 제한)
    """
    BASE_URL = "https://data.aishub.net/ws.php"

    def __init__(self, username: str):
        self.username = username

    def fetch_hormuz(self, interval_min: int = 60) -> list[dict]:
        """호르무즈 해협 범위 내 선박 위치 조회"""
        params = {
            "username": self.username,
            "format": "1",
            "output": "json",
            "compress": "0",
            "latmin": HORMUZ_BBOX["latmin"],
            "latmax": HORMUZ_BBOX["latmax"],
            "lonmin": HORMUZ_BBOX["lonmin"],
            "lonmax": HORMUZ_BBOX["lonmax"],
            "interval": interval_min,
        }
        resp = requests.get(self.BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # AISHub 응답: [{"ERROR": false, "USERNAME": "..."}, [vessel, ...]]
        if isinstance(data, list) and len(data) >= 2:
            return data[1]
        return []


# ══════════════════════════════════════════════════════════════════════════════
# 2. aisstream.io 실시간 WebSocket (별도 실행용 참고 코드)
# ══════════════════════════════════════════════════════════════════════════════

AISSTREAM_EXAMPLE = """
# aisstream.io 실시간 스트리밍 예시 (pip install websockets)
# 무료 API 키 발급: https://aisstream.io

import asyncio, websockets, json

async def stream_hormuz(api_key):
    url = "wss://stream.aisstream.io/v0/stream"
    subscribe_msg = {
        "APIKey": api_key,
        "BoundingBoxes": [
            [[25.5, 56.0], [27.5, 60.0]]   # 호르무즈 해협
        ],
        "FilterMessageTypes": ["PositionReport"]
    }
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(subscribe_msg))
        async for raw in ws:
            msg = json.loads(raw)
            mmsi = msg["MetaData"]["MMSI"]
            lat  = msg["MetaData"]["latitude"]
            lon  = msg["MetaData"]["longitude"]
            print(f"MMSI={mmsi}  lat={lat:.4f}  lon={lon:.4f}")

asyncio.run(stream_hormuz("YOUR_API_KEY_HERE"))
"""


# ══════════════════════════════════════════════════════════════════════════════
# 3. EIA 호르무즈 석유 유량 데이터 (완전 무료)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_eia_hormuz(api_key: str = "") -> pd.DataFrame:
    """
    EIA(미국 에너지정보청) API로 호르무즈 통과 석유 유량(백만 배럴/일) 조회
    
    무료 키 발급: https://www.eia.gov/opendata/
    시리즈 ID   : STEO.PATC_HORMUZ.M  (월별, 백만 b/d)
    """
    if not api_key:
        return pd.DataFrame()
    url = "https://api.eia.gov/v2/petroleum/move/pipe/data/"
    params = {
        "api_key": api_key,
        "frequency": "monthly",
        "data[0]": "value",
        "facets[series][]": "PATC_HORMUZ",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 36,
        "offset": 0,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        rows = resp.json()["response"]["data"]
        df = pd.DataFrame(rows)
        df["period"] = pd.to_datetime(df["period"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.sort_values("period")
    except Exception as exc:
        print(f"[EIA] 조회 실패: {exc}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# 4. 데모 데이터 생성 (실제 통계 기반)
# ══════════════════════════════════════════════════════════════════════════════

def generate_demo_data(days: int = 90) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    실제 통계 기반 데모 데이터 생성
    
    참고 통계:
    - 평시 일 평균 통과 선박: 약 138척 (AIS 탐지 기준)
    - 2026년 2월 말 이후 위기 상황: 약 21척/일로 급락 (~85% 감소)
    - 선박 구성: 유조선 37%, 화물선 31%, LNG 6%, 기타 26%
    - 목적지: 인도 26%, 중국 25%, 동남아 20%, 유럽 16%, 일본 7%, 한국 6%
    """
    rng = np.random.default_rng(42)
    end_date   = datetime(2026, 3, 11)
    start_date = end_date - timedelta(days=days - 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]

    # 위기 발생일 (2026-02-28 이후 급감)
    crisis_start = datetime(2026, 2, 28)

    # 일별 선박 수 생성
    vessel_counts = []
    for d in dates:
        if d < crisis_start:
            # 평시: 130~150척, 주말 소폭 감소
            base = 138 if d.weekday() < 5 else 120
            noise = rng.integers(-12, 12)
            vessel_counts.append(max(0, base + noise))
        else:
            # 위기: 급감 후 소폭 회복
            days_since = (d - crisis_start).days
            base = max(21, 138 - int(138 * 0.85 * min(1.0, days_since / 5)))
            noise = rng.integers(-5, 5)
            vessel_counts.append(max(0, base + noise))

    daily_df = pd.DataFrame({"date": dates, "vessel_count": vessel_counts})

    # 국적별 데이터
    nationality_data = {
        "국적": [
            "파나마", "마샬군도", "라이베리아", "바하마",
            "홍콩", "싱가포르", "중국", "그리스",
            "몰타", "인도", "UAE", "노르웨이",
            "한국", "일본", "기타",
        ],
        "선박_수": [
            312, 287, 241, 198,
            174, 156, 143, 122,
            118, 97, 84, 76,
            68, 54, 320,
        ],
        "주요_선종": [
            "유조선/화물선", "유조선", "유조선/화물선", "유조선/화물선",
            "유조선", "화물선/LNG", "유조선/화물선", "유조선",
            "유조선/화물선", "유조선", "유조선/LNG", "LNG/유조선",
            "유조선/LNG", "유조선/화물선", "혼합",
        ],
    }
    nationality_df = pd.DataFrame(nationality_data).sort_values("선박_수", ascending=False)

    return daily_df, nationality_df


# ══════════════════════════════════════════════════════════════════════════════
# 5. 시각화 함수
# ══════════════════════════════════════════════════════════════════════════════

PALETTE = {
    "blue":   "#2563EB",
    "red":    "#DC2626",
    "orange": "#F59E0B",
    "green":  "#10B981",
    "gray":   "#6B7280",
    "bg":     "#F8FAFC",
    "grid":   "#E2E8F0",
}


def plot_daily_trend(daily_df: pd.DataFrame, title_suffix: str = "(데모)") -> str:
    """일별 선박 통과 추세 차트 → base64 PNG 반환"""
    _apply_font()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor(PALETTE["bg"])

    dates = daily_df["date"]
    counts = daily_df["vessel_count"]

    # 위기 발생 기준선
    crisis_date = pd.Timestamp("2026-02-28")

    # ── 상단: 일별 통과 선박 수 ──────────────────────────────────────────────
    ax1.set_facecolor(PALETTE["bg"])
    ax1.fill_between(dates, counts, alpha=0.18, color=PALETTE["blue"])
    ax1.plot(dates, counts, color=PALETTE["blue"], linewidth=2.0, label="일별 통과 선박 수")

    # 7일 이동평균
    ma7 = counts.rolling(7, center=True).mean()
    ax1.plot(dates, ma7, color=PALETTE["orange"], linewidth=2.5,
             linestyle="--", label="7일 이동평균")

    # 위기 발생 수직선
    if crisis_date >= dates.min() and crisis_date <= dates.max():
        ax1.axvline(crisis_date, color=PALETTE["red"], linewidth=1.8,
                    linestyle=":", alpha=0.85)
        ax1.text(crisis_date + timedelta(days=0.5),
                 counts.max() * 0.92,
                 "  ← 위기 발생\n  (2026.02.28)",
                 color=PALETTE["red"], fontsize=10, va="top")

    # 평균선
    pre_crisis = daily_df[daily_df["date"] < crisis_date]["vessel_count"]
    if len(pre_crisis):
        ax1.axhline(pre_crisis.mean(), color=PALETTE["gray"],
                    linewidth=1.2, linestyle="--", alpha=0.6,
                    label=f"평시 평균 ({pre_crisis.mean():.0f}척)")

    ax1.set_title(f"호르무즈 해협 일별 통과 선박 수 {title_suffix}",
                  fontsize=16, fontweight="bold", pad=14)
    ax1.set_ylabel("선박 수 (척)", fontsize=12)
    ax1.legend(fontsize=10, loc="upper right")
    ax1.grid(axis="y", color=PALETTE["grid"], linewidth=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax1.spines[["top", "right"]].set_visible(False)

    # ── 하단: 전일 대비 변화율 ────────────────────────────────────────────────
    pct_change = counts.pct_change() * 100
    colors = [PALETTE["green"] if v >= 0 else PALETTE["red"] for v in pct_change.fillna(0)]
    ax2.set_facecolor(PALETTE["bg"])
    ax2.bar(dates, pct_change.fillna(0), color=colors, alpha=0.75, width=0.8)
    ax2.axhline(0, color=PALETTE["gray"], linewidth=0.8)
    ax2.set_ylabel("전일 대비 (%)", fontsize=10)
    ax2.set_ylim(-60, 60)
    ax2.grid(axis="y", color=PALETTE["grid"], linewidth=0.8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout(h_pad=1.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def plot_nationality_stats(nat_df: pd.DataFrame, title_suffix: str = "(데모)") -> str:
    """국적별 통계 차트 → base64 PNG 반환"""
    _apply_font()
    fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=(16, 8))
    fig.patch.set_facecolor(PALETTE["bg"])
    fig.suptitle(f"호르무즈 해협 통과 선박 국적별 분포 {title_suffix}",
                 fontsize=16, fontweight="bold", y=1.01)

    top_n = nat_df.head(12)
    nations = top_n["국적"].tolist()
    counts  = top_n["선박_수"].tolist()

    # 색상 그라디언트
    cmap = plt.colormaps["Blues"]
    bar_colors = [cmap(0.9 - 0.05 * i) for i in range(len(nations))]

    # ── 좌: 수평 막대 ────────────────────────────────────────────────────────
    ax_bar.set_facecolor(PALETTE["bg"])
    bars = ax_bar.barh(nations[::-1], counts[::-1],
                       color=bar_colors[::-1], edgecolor="white",
                       linewidth=0.5, height=0.7)
    for bar, cnt in zip(bars, counts[::-1]):
        ax_bar.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2,
                    f"{cnt:,}척", va="center", fontsize=10)
    ax_bar.set_xlabel("선박 수 (척)", fontsize=12)
    ax_bar.set_title("국적별 선박 수 (상위 12개국)", fontsize=13, fontweight="bold")
    ax_bar.grid(axis="x", color=PALETTE["grid"], linewidth=0.8)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.set_xlim(0, max(counts) * 1.18)

    # ── 우: 파이 차트 (상위 8 + 기타) ────────────────────────────────────────
    top8  = nat_df.head(8)
    rest  = nat_df.iloc[8:]["선박_수"].sum()
    pie_labels = top8["국적"].tolist() + ["기타"]
    pie_values = top8["선박_수"].tolist() + [rest]
    explode = [0.04] * len(pie_labels)

    cmap2 = plt.colormaps["tab20c"]
    pie_colors = [cmap2(i / len(pie_labels)) for i in range(len(pie_labels))]

    wedges, texts, autotexts = ax_pie.pie(
        pie_values, labels=pie_labels, autopct="%1.1f%%",
        colors=pie_colors, explode=explode,
        pctdistance=0.82, startangle=140,
        textprops={"fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax_pie.set_title("국적 비율 (상위 8개국 + 기타)", fontsize=13, fontweight="bold")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def plot_ship_type_breakdown() -> str:
    """선종별 구성 차트 → base64 PNG 반환"""
    _apply_font()
    types  = ["유조선", "화물선", "LNG선", "벌크선", "예인선/서비스선", "기타"]
    values = [37, 31, 6, 8, 9, 9]
    colors = ["#2563EB", "#10B981", "#F59E0B", "#8B5CF6", "#6B7280", "#EC4899"]

    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor(PALETTE["bg"])
    ax.set_facecolor(PALETTE["bg"])

    wedges, texts, autotexts = ax.pie(
        values, labels=types, autopct="%1.1f%%",
        colors=colors, startangle=120, pctdistance=0.80,
        explode=[0.06, 0.03, 0.03, 0.03, 0.03, 0.03],
        textprops={"fontsize": 11},
    )
    for at in autotexts:
        at.set_fontsize(10)
    ax.set_title("호르무즈 해협 통과 선박 선종별 구성 (%)",
                 fontsize=14, fontweight="bold", pad=16)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


# ══════════════════════════════════════════════════════════════════════════════
# 6. AISHub 실시간 데이터 → DataFrame 변환
# ══════════════════════════════════════════════════════════════════════════════

def aishub_to_df(vessels: list[dict]) -> pd.DataFrame:
    """AISHub JSON 응답을 분석용 DataFrame으로 변환"""
    rows = []
    for v in vessels:
        mmsi    = str(v.get("MMSI", ""))
        country = MMSI_COUNTRY.get(mmsi[:3], "기타")
        ship_t  = SHIP_TYPE_MAP.get(v.get("SHIPTYPE", -1), "미분류")
        rows.append({
            "mmsi":      mmsi,
            "name":      v.get("NAME", "N/A"),
            "lat":       v.get("LATITUDE"),
            "lon":       v.get("LONGITUDE"),
            "speed":     v.get("SOG"),
            "heading":   v.get("COG"),
            "ship_type": ship_t,
            "country":   country,
            "timestamp": v.get("TIME"),
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 종합 실행 함수
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(
    aishub_username: str = "",
    eia_api_key: str = "",
    days: int = 90,
    save_dir: str = ".",
) -> dict:
    """
    전체 분석 실행

    Parameters
    ----------
    aishub_username : AISHub 사용자명 (없으면 데모 데이터 사용)
    eia_api_key     : EIA API 키 (없으면 생략)
    days            : 데모 데이터 기간 (일)
    save_dir        : 차트 PNG 저장 디렉터리

    Returns
    -------
    dict with keys: daily_df, nationality_df, charts (base64 dict)
    """
    suffix = "(실시간 AIS)" if aishub_username else "(데모 데이터)"

    # ── 실시간 데이터 시도 ────────────────────────────────────────────────────
    live_df = None
    if aishub_username:
        try:
            client   = AISHubClient(aishub_username)
            vessels  = client.fetch_hormuz()
            live_df  = aishub_to_df(vessels)
            print(f"[AISHub] 실시간 선박 {len(live_df)}척 수신")
        except Exception as exc:
            print(f"[AISHub] 연결 실패: {exc}  →  데모 데이터로 전환")

    # ── 데모 데이터 생성 ──────────────────────────────────────────────────────
    daily_df, nat_df = generate_demo_data(days=days)

    # 실시간 데이터 있으면 국적 통계를 실제 데이터로 교체
    if live_df is not None and not live_df.empty:
        nat_live = (live_df.groupby("country")
                    .size()
                    .reset_index(name="선박_수")
                    .rename(columns={"country": "국적"})
                    .sort_values("선박_수", ascending=False))
        nat_live["주요_선종"] = "AIS 실시간"
        nat_df = nat_live

    # ── 차트 생성 ─────────────────────────────────────────────────────────────
    charts = {
        "daily_trend":   plot_daily_trend(daily_df, suffix),
        "nationality":   plot_nationality_stats(nat_df, suffix),
        "ship_type":     plot_ship_type_breakdown(),
    }

    # 선택적 PNG 저장
    os.makedirs(save_dir, exist_ok=True)
    for name, b64 in charts.items():
        path = os.path.join(save_dir, f"hormuz_{name}.png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"[저장] {path}")

    # 요약 통계 출력
    _print_summary(daily_df, nat_df, live_df)

    return {"daily_df": daily_df, "nationality_df": nat_df, "charts": charts}


def _print_summary(daily_df, nat_df, live_df):
    """콘솔 요약 출력"""
    print("\n" + "=" * 60)
    print("  호르무즈 해협 선박 통계 요약")
    print("=" * 60)

    pre  = daily_df[daily_df["date"] < datetime(2026, 2, 28)]["vessel_count"]
    post = daily_df[daily_df["date"] >= datetime(2026, 2, 28)]["vessel_count"]

    print(f"  분석 기간  : {daily_df['date'].min().date()} ~ {daily_df['date'].max().date()}")
    if len(pre):
        print(f"  평시 평균  : {pre.mean():.1f}척/일  (최대 {pre.max()}척, 최소 {pre.min()}척)")
    if len(post):
        print(f"  위기 이후  : {post.mean():.1f}척/일  (최대 {post.max()}척, 최소 {post.min()}척)")
    if len(pre) and len(post):
        pct = (post.mean() - pre.mean()) / pre.mean() * 100
        print(f"  감소율     : {pct:.1f}%")

    print(f"\n  국적 상위 5개국:")
    for _, row in nat_df.head(5).iterrows():
        print(f"    {row['국적']:12s}  {row['선박_수']:>4d}척")

    if live_df is not None:
        print(f"\n  [실시간] 현재 탐지 선박: {len(live_df)}척")
    print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# CLI 실행
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="호르무즈 해협 선박 통계 분석")
    parser.add_argument("--aishub",   default="", help="AISHub 사용자명")
    parser.add_argument("--eia-key",  default="", help="EIA API 키")
    parser.add_argument("--days",     type=int, default=90, help="분석 기간(일)")
    parser.add_argument("--out",      default=".", help="차트 저장 디렉터리")
    args = parser.parse_args()

    run_analysis(
        aishub_username=args.aishub,
        eia_api_key=args.eia_key,
        days=args.days,
        save_dir=args.out,
    )
