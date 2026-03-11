# -*- coding: utf-8 -*-
"""
전쟁 능력 지표 분석 웹 앱 - 노트북(데이터로 바라본 외교)의 World Bank 분석을
국가·변수 선택으로 실행합니다.
"""
import io
import base64
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import wbgapi as wb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__, static_folder='static')

INDICATORS = {
    "SP.POP.TOTL": "총 인구 (Population, total)",
    "SP.POP.1564.TO.ZS": "15~64세 인구 비율 (%)",
    "NE.CON.GOVT.KD": "정부 최종소비지출 (2015년 불변 USD)",
    "NY.GDP.MKTP.KD.ZG": "GDP 성장률 (연간 %)",
    "NY.GDP.MKTP.CD": "GDP (현재 USD)",
    "NY.GDP.PCAP.CD": "1인당 GDP (현재 US$)",
    "MS.MIL.XPND.GD.ZS": "군사비 지출 (GDP 대비 %)",
    "MS.MIL.XPND.CD": "군사비 지출 (현재 USD)",
    "MS.MIL.TOTL.P1": "총 병력 수 (현역+예비군)",
    "MS.MIL.TOTL.TF.ZS": "병력 (총 노동력 대비 %)",
    "MS.MIL.MPRT.KD": "무기 수입 규모 (SIPRI TIV, 2023년 불변 USD)",
    "FI.RES.TOTL.CD": "총 외환보유고 (금 포함, 현재 US$)",
}
SCALE_BILLIONS = {"NY.GDP.MKTP.CD", "MS.MIL.XPND.CD", "FI.RES.TOTL.CD", "MS.MIL.MPRT.KD"}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/countries")
def api_countries():
    # World Bank API에서 읽기가 실패하거나 빈 결과를 주는 경우를 대비해
    # 기본 국가 목록을 제공한다.
    fallback_countries = [
        {"id": "IRN", "name": "Iran, Islamic Rep."},
        {"id": "ISR", "name": "Israel"},
        {"id": "SAU", "name": "Saudi Arabia"},
        {"id": "RUS", "name": "Russian Federation"},
        {"id": "UKR", "name": "Ukraine"},
        {"id": "KOR", "name": "Korea, Rep."},
        {"id": "PRK", "name": "Korea, Dem. People's Rep."},
        {"id": "USA", "name": "United States"},
        {"id": "CHN", "name": "China"},
        {"id": "JPN", "name": "Japan"},
        {"id": "DEU", "name": "Germany"},
        {"id": "FRA", "name": "France"},
        {"id": "GBR", "name": "United Kingdom"},
    ]
    try:
        rows = []
        for row in wb.economy.list():
            if getattr(row, 'id', None) and len(getattr(row, 'id', '')) == 3:
                rows.append({"id": row.id, "name": getattr(row, 'value', row.id)})
        # World Bank에서 아무 것도 안 돌아오면 기본 목록 사용
        if not rows:
            return jsonify(fallback_countries)
        return jsonify(rows)
    except Exception as e:
        # 에러가 나더라도 기본 목록은 항상 반환
        return jsonify(fallback_countries)


@app.route("/api/indicators")
def api_indicators():
    return jsonify([{"id": k, "name": v} for k, v in INDICATORS.items()])


def _normalize_time_column(df):
    if "Time" not in df.columns and "time" in df.columns:
        df = df.rename(columns={"time": "Time"})
    if "Time" in df.columns:
        t = df["Time"].astype(str)
        if t.str.startswith("YR").any():
            df["Time"] = t.str[2:].astype(int)
        else:
            df["Time"] = pd.to_numeric(t, errors="coerce")
    return df


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        body = request.get_json() or {}
        countries = body.get("countries") or []
        series_id = (body.get("series_id") or "").strip()
        year_start = int(body.get("year_start", 2010))
        year_end = int(body.get("year_end", 2025))

        if not countries:
            return jsonify({"error": "국가를 하나 이상 선택하세요."}), 400
        if not series_id or series_id not in INDICATORS:
            return jsonify({"error": "유효한 지표를 선택하세요."}), 400
        if year_start >= year_end:
            return jsonify({"error": "연도 범위가 올바르지 않습니다."}), 400

        country_set = set(c.upper() for c in countries)
        year_range = range(year_start, year_end + 1)

        df = wb.data.DataFrame(
            series=series_id,
            economy=country_set,
            time=year_range,
            index="time",
            labels=True,
        ).reset_index()

        if df.empty:
            return jsonify({"error": "선택한 국가·연도에 해당 데이터가 없습니다."}), 404

        df = _normalize_time_column(df)
        time_col = "Time" if "Time" in df.columns else "time"
        if time_col not in df.columns:
            return jsonify({"error": "연도 컬럼을 찾을 수 없습니다."}), 500

        if series_id in SCALE_BILLIONS:
            for c in country_set:
                if c in df.columns:
                    df[c] = df[c] / 1e9

        data = df[[time_col] + [c for c in country_set if c in df.columns]].to_dict(orient="records")
        for row in data:
            if time_col in row:
                row[time_col] = int(row[time_col]) if pd.notna(row[time_col]) else None
            for k in list(row):
                if k != time_col and isinstance(row[k], (float,)):
                    row[k] = round(row[k], 4) if pd.notna(row[k]) else None

        return jsonify(
            {
                "data": data,
                "time_key": time_col,
                "series_id": series_id,
                "series_name": INDICATORS.get(series_id, series_id),
                "countries": sorted(list(country_set)),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- 위기 분석 (원자재, 공포지수, 외환, 주식) ----------
import sys, os
try:
    import yfinance as yf
    # yfinance 타임존 캐시를 프로젝트 폴더 아래 .yf_cache에 저장 (DB 열기 실패 방지)
    _yf_cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".yf_cache")
    os.makedirs(_yf_cache_dir, exist_ok=True)
    yf.set_tz_cache_location(_yf_cache_dir)
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# 국가 코드 → 한국어 이름
COUNTRY_KO = {
    "USA": "미국", "KOR": "한국", "JPN": "일본", "CHN": "중국",
    "RUS": "러시아", "UKR": "우크라이나", "ISR": "이스라엘",
    "IRN": "이란", "SAU": "사우디아라비아", "GBR": "영국",
    "DEU": "독일", "FRA": "프랑스", "PRK": "북한",
}

def _ko(code):
    return COUNTRY_KO.get(code, code)

# 국가별 주식·외환 심볼 (선택 시 해당 국가만 표시)
# 라벨 형식: "지표명 (국가명)"
CRISIS_STOCKS_BY_COUNTRY = {
    "USA": {"^GSPC":      "S&P 500 (미국)"},
    "ISR": {"^TA125.TA":  "TA-125 (이스라엘)"},
    "SAU": {"^TASI.SR":   "Tadawul (사우디)"},
    "CHN": {"000001.SS":  "SSE Composite (중국)"},
    "RUS": {"IMOEX.ME":   "MOEX (러시아)"},
    "GBR": {"^FTSE":      "FTSE 100 (영국)"},
    "KOR": {"^KS11":      "KOSPI (한국)"},
    "JPN": {"^N225":      "Nikkei 225 (일본)"},
}
# 노트북(데이터로 바라본 외교) Cell 130 외환변동과 동일한 표기
# 라벨 형식: "환율쌍 (국가명)"
CRISIS_FX_BY_COUNTRY = {
    "KOR": {"KRW=X":    "USD/KRW (한국)"},
    "JPN": {"JPY=X":    "USD/JPY (일본)"},
    "CHN": {"CNY=X":    "USD/CNY (중국)"},
    "DEU": {"EURUSD=X": "USD/EUR (독일·유로존)"},
    "FRA": {"EURUSD=X": "USD/EUR (프랑스·유로존)"},
    "GBR": {"GBPUSD=X": "USD/GBP (영국)"},
}
# 국가 미선택 시 노트북과 동일한 4개 환율 표시
CRISIS_FX_DEFAULT = {
    "KRW=X":    "USD/KRW (한국)",
    "CNY=X":    "USD/CNY (중국)",
    "EURUSD=X": "USD/EUR (유로존)",
    "GBPUSD=X": "USD/GBP (영국)",
}


def _sample_series(symbols, period="1y"):
    """yfinance 미설치 시 샘플 데이터 반환 (시각화 테스트용)."""
    import datetime
    n = 252 if period == "1y" else (126 if period == "6mo" else 63)
    today = datetime.date.today()
    labels = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n, 0, -1)]
    symbols_dict = symbols if isinstance(symbols, dict) else {t: t for t in symbols}
    series = {}
    for i, (ticker, name) in enumerate(symbols_dict.items()):
        base = 100 + (i * 10)
        series[name] = [round(base + (j % 30) - 15 + (j * 0.02), 2) for j in range(n)]
    return {"labels": labels, "series": series, "sample_data": True}


def _fetch_ticker_close(ticker, period):
    """단일 티커의 종가 시계열 (날짜 리스트, 값 리스트) 반환. 실패 시 (None, None)."""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            print(f"[yf] {ticker}: empty DataFrame", flush=True)
            return None, None
        if "Close" not in hist.columns:
            print(f"[yf] {ticker}: no Close column, columns={list(hist.columns)}", flush=True)
            return None, None
        s = hist["Close"].copy().sort_index(ascending=True).dropna()
        if s.empty:
            return None, None
        dates = [x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x)[:10] for x in s.index]
        values = [round(float(x), 4) for x in s.tolist()]
        print(f"[yf] {ticker}: {len(values)} rows, first={values[0] if values else None}, last={values[-1] if values else None}", flush=True)
        return dates, values
    except Exception as e:
        print(f"[yf] {ticker}: exception {e}", flush=True)
        return None, None


def _yf_series(symbols, period="1y"):
    """노트북(데이터로 바라본 외교) Cell 123처럼 티커별로 Ticker().history() 호출해 항목마다 서로 다른 데이터 보장."""
    if not HAS_YFINANCE:
        print("[yf] yfinance not installed, using sample data", flush=True)
        return _sample_series(symbols, period)
    symbols_dict = symbols if isinstance(symbols, dict) else {t: t for t in symbols}
    out = {"labels": [], "series": {}}
    all_dates = None
    for ticker, label in symbols_dict.items():
        dates, values = _fetch_ticker_close(ticker, period)
        if dates is None:
            continue
        if all_dates is None:
            all_dates = list(dates)
            out["labels"] = all_dates
            out["series"][label] = list(values)
        elif dates == all_dates:
            out["series"][label] = list(values)
        else:
            date_to_val = dict(zip(dates, values))
            out["series"][label] = [date_to_val.get(d) for d in all_dates]
    if not out["series"]:
        print("[yf] all tickers failed, using sample data", flush=True)
        return _sample_series(symbols, period)
    return out


def _crisis_countries():
    """요청에서 국가 목록 파싱 (선택 없으면 전체)"""
    raw = request.args.get("countries", "")
    if not raw or not raw.strip():
        return None
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


@app.route("/api/crisis/status")
def api_crisis_status():
    """yfinance 설치 여부 및 사용 중인 Python 경로 (설치 안내용)"""
    return jsonify({
        "yfinance_available": HAS_YFINANCE,
        "python": sys.executable,
        "install_hint": "프로젝트 폴더에서 다음을 실행하세요: .\\.venv\\Scripts\\python.exe -m pip install yfinance",
    })


@app.route("/api/crisis/debug")
def api_crisis_debug():
    """티커 2개를 직접 조회해 실제 데이터가 다른지 확인 (진단용)"""
    tickers = ["CL=F", "GC=F"]  # WTI, Gold
    result = {"yfinance_available": HAS_YFINANCE}
    if not HAS_YFINANCE:
        return jsonify(result)
    for t in tickers:
        dates, values = _fetch_ticker_close(t, "1mo")
        if dates:
            result[t] = {"rows": len(values), "first": values[0], "last": values[-1],
                         "sample": values[:3]}
        else:
            result[t] = {"error": "no data"}
    return jsonify(result)


# 원자재: 티커 → 표시명 (유형별 패널용)
CRISIS_COMMODITIES = {
    "CL=F": "WTI",
    "BZ=F": "Brent Crude",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
    "GC=F": "Gold",
    "SI=F": "Silver",
}


@app.route("/api/crisis/commodities")
def api_crisis_commodities():
    """원자재 가격 (전역, 유형별 패널용)"""
    period = request.args.get("period", "1y")
    return jsonify(_yf_series(CRISIS_COMMODITIES, period=period))


# 금융 공포지수: yfinance 티커 → 표시명, 위험 기준값(점선으로 표시)
CRISIS_FEAR_INDICES = {
    "^VIX": {"name": "VIX(미국 주식)", "danger": [20, 30]},   # 20 주의, 30 위험
    "^MOVE": {"name": "MOVE(채권)", "danger": [120]},         # 120 이상 긴장
    "^SKEW": {"name": "SKEW(꼬리위험)", "danger": [140]},    # 140 이상 꼬리 위험
    "^VVIX": {"name": "VVIX(VIX 변동성)", "danger": [90]},   # 90 이상 변동성 불안
}
CRISIS_FEAR_SYMBOLS = {t: d["name"] for t, d in CRISIS_FEAR_INDICES.items()}
CRISIS_FEAR_DANGER = {d["name"]: d["danger"] for d in CRISIS_FEAR_INDICES.values()}


@app.route("/api/crisis/fear")
def api_crisis_fear():
    """금융 공포지수 (VIX, MOVE, SKEW, VVIX) + 위험 기준값"""
    period = request.args.get("period", "1y")
    out = _yf_series(CRISIS_FEAR_SYMBOLS, period=period)
    if "danger_thresholds" not in out:
        out["danger_thresholds"] = CRISIS_FEAR_DANGER
    return jsonify(out)


@app.route("/api/crisis/fx")
def api_crisis_fx():
    """외환 변동 — 노트북 Cell 130과 동일한 환율 쌍·표기"""
    countries = _crisis_countries()
    if countries:
        symbols = {}
        seen = set()
        for c in countries:
            for ticker, label in CRISIS_FX_BY_COUNTRY.get(c, {}).items():
                if ticker not in seen:
                    seen.add(ticker)
                    symbols[ticker] = label  # 이미 국가명 포함된 형식
        if not symbols:
            symbols = dict(CRISIS_FX_DEFAULT)
    else:
        symbols = dict(CRISIS_FX_DEFAULT)
    period = request.args.get("period", "1y")
    return jsonify(_yf_series(symbols, period=period))


@app.route("/api/crisis/stocks")
def api_crisis_stocks():
    """주식시장 — countries 파라미터로 선택 국가만 표시, 국가별 라벨"""
    countries = _crisis_countries()
    if countries:
        symbols = {}
        for c in countries:
            for ticker, label in CRISIS_STOCKS_BY_COUNTRY.get(c, {}).items():
                symbols[ticker] = label  # 이미 국가명 포함된 형식
        if not symbols:
            symbols = {t: L for c in CRISIS_STOCKS_BY_COUNTRY for t, L in CRISIS_STOCKS_BY_COUNTRY[c].items()}
    else:
        symbols = {t: L for c in CRISIS_STOCKS_BY_COUNTRY for t, L in CRISIS_STOCKS_BY_COUNTRY[c].items()}
    period = request.args.get("period", "1y")
    return jsonify(_yf_series(symbols, period=period))


@app.route("/why")
def why_page():
    return send_from_directory("static", "why.html")


@app.route("/governance")
def governance_page():
    return send_from_directory("static", "governance.html")


# Worldwide Governance Indicators (WGI) — 값 범위 약 -2.5 ~ +2.5, 높을수록 좋음
WGI_INDICATORS = {
    "VA.EST": "발언권과 책임성 (Voice & Accountability)",
    "PV.EST": "정치 안정성 (Political Stability)",
    "GE.EST": "정부 효과성 (Government Effectiveness)",
    "RQ.EST": "규제 품질 (Regulatory Quality)",
    "RL.EST": "법치주의 (Rule of Law)",
    "CC.EST": "부패 통제 (Control of Corruption)",
}


@app.route("/api/governance")
def api_governance():
    """WGI 6개 지표를 국가·연도별로 반환 (wbgapi 사용)."""
    try:
        raw_countries = request.args.get("countries", "")
        year_start = int(request.args.get("year_start", 2000))
        year_end   = int(request.args.get("year_end", 2024))

        if not raw_countries.strip():
            return jsonify({"error": "국가를 하나 이상 선택하세요."}), 400

        country_set = [c.strip().upper() for c in raw_countries.split(",") if c.strip()]
        year_range  = range(year_start, year_end + 1)
        result = {}   # { indicator_id: { country: [{year, value}, ...] } }

        for ind_id in WGI_INDICATORS:
            try:
                df = wb.data.DataFrame(
                    series=ind_id,
                    economy=country_set,
                    time=year_range,
                    index="time",
                    labels=False,
                ).reset_index()

                if df.empty:
                    result[ind_id] = {}
                    continue

                df = _normalize_time_column(df)
                time_col = "Time" if "Time" in df.columns else "time"
                df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
                df = df.dropna(subset=[time_col]).sort_values(time_col)

                ind_data = {}
                for c in country_set:
                    if c not in df.columns:
                        continue
                    rows = []
                    for _, row in df[[time_col, c]].iterrows():
                        yr = int(row[time_col]) if pd.notna(row[time_col]) else None
                        val = round(float(row[c]), 4) if pd.notna(row[c]) else None
                        if yr is not None:
                            rows.append({"year": yr, "value": val})
                    if rows:
                        ind_data[c] = rows
                result[ind_id] = ind_data
            except Exception:
                result[ind_id] = {}

        return jsonify({
            "indicators": WGI_INDICATORS,
            "countries": country_set,
            "year_start": year_start,
            "year_end": year_end,
            "data": result,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Freedom House ──────────────────────────────────────────────────────────
# ISO3 → FH 파일 내 국가명 매핑 (공식 FH 표기 기준)
FH_NAME_MAP = {
    "AFG":"Afghanistan","ALB":"Albania","DZA":"Algeria","AGO":"Angola",
    "ARG":"Argentina","ARM":"Armenia","AUS":"Australia","AUT":"Austria",
    "AZE":"Azerbaijan","BHS":"Bahamas","BHR":"Bahrain","BGD":"Bangladesh",
    "BLR":"Belarus","BEL":"Belgium","BLZ":"Belize","BEN":"Benin",
    "BTN":"Bhutan","BOL":"Bolivia","BIH":"Bosnia and Herzegovina",
    "BWA":"Botswana","BRA":"Brazil","BRN":"Brunei","BGR":"Bulgaria",
    "BFA":"Burkina Faso","BDI":"Burundi","CPV":"Cabo Verde","KHM":"Cambodia",
    "CMR":"Cameroon","CAN":"Canada","CAF":"Central African Republic",
    "TCD":"Chad","CHL":"Chile","CHN":"China","COL":"Colombia","COM":"Comoros",
    "COD":"Congo (Kinshasa)","COG":"Congo (Brazzaville)","CRI":"Costa Rica",
    "CIV":"Cote d'Ivoire","HRV":"Croatia","CUB":"Cuba","CYP":"Cyprus",
    "CZE":"Czech Republic","DNK":"Denmark","DJI":"Djibouti","DOM":"Dominican Republic",
    "ECU":"Ecuador","EGY":"Egypt","SLV":"El Salvador","GNQ":"Equatorial Guinea",
    "ERI":"Eritrea","EST":"Estonia","SWZ":"Eswatini","ETH":"Ethiopia",
    "FJI":"Fiji","FIN":"Finland","FRA":"France","GAB":"Gabon","GMB":"The Gambia",
    "GEO":"Georgia","DEU":"Germany","GHA":"Ghana","GRC":"Greece","GTM":"Guatemala",
    "GIN":"Guinea","GNB":"Guinea-Bissau","GUY":"Guyana","HTI":"Haiti",
    "HND":"Honduras","HUN":"Hungary","ISL":"Iceland","IND":"India",
    "IDN":"Indonesia","IRN":"Iran","IRQ":"Iraq","IRL":"Ireland","ISR":"Israel",
    "ITA":"Italy","JAM":"Jamaica","JPN":"Japan","JOR":"Jordan","KAZ":"Kazakhstan",
    "KEN":"Kenya","PRK":"North Korea","KOR":"South Korea","KWT":"Kuwait",
    "KGZ":"Kyrgyzstan","LAO":"Laos","LVA":"Latvia","LBN":"Lebanon","LSO":"Lesotho",
    "LBR":"Liberia","LBY":"Libya","LIE":"Liechtenstein","LTU":"Lithuania",
    "LUX":"Luxembourg","MDG":"Madagascar","MWI":"Malawi","MYS":"Malaysia",
    "MDV":"Maldives","MLI":"Mali","MLT":"Malta","MRT":"Mauritania","MUS":"Mauritius",
    "MEX":"Mexico","MDA":"Moldova","MNG":"Mongolia","MNE":"Montenegro",
    "MAR":"Morocco","MOZ":"Mozambique","MMR":"Myanmar","NAM":"Namibia",
    "NPL":"Nepal","NLD":"Netherlands","NZL":"New Zealand","NIC":"Nicaragua",
    "NER":"Niger","NGA":"Nigeria","MKD":"North Macedonia","NOR":"Norway",
    "OMN":"Oman","PAK":"Pakistan","PAN":"Panama","PNG":"Papua New Guinea",
    "PRY":"Paraguay","PER":"Peru","PHL":"Philippines","POL":"Poland",
    "PRT":"Portugal","QAT":"Qatar","ROU":"Romania","RUS":"Russia","RWA":"Rwanda",
    "SAU":"Saudi Arabia","SEN":"Senegal","SRB":"Serbia","SLE":"Sierra Leone",
    "SGP":"Singapore","SVK":"Slovakia","SVN":"Slovenia","SOM":"Somalia",
    "ZAF":"South Africa","SSD":"South Sudan","ESP":"Spain","LKA":"Sri Lanka",
    "SDN":"Sudan","SUR":"Suriname","SWE":"Sweden","CHE":"Switzerland",
    "SYR":"Syria","TWN":"Taiwan","TJK":"Tajikistan","TZA":"Tanzania",
    "THA":"Thailand","TLS":"Timor-Leste","TGO":"Togo","TTO":"Trinidad and Tobago",
    "TUN":"Tunisia","TUR":"Turkey","TKM":"Turkmenistan","UGA":"Uganda",
    "UKR":"Ukraine","ARE":"United Arab Emirates","GBR":"United Kingdom",
    "USA":"United States","URY":"Uruguay","UZB":"Uzbekistan","VEN":"Venezuela",
    "VNM":"Vietnam","YEM":"Yemen","ZMB":"Zambia","ZWE":"Zimbabwe",
}
FH_NAME_TO_ISO = {v: k for k, v in FH_NAME_MAP.items()}

_fh_cache = None   # 메모리 캐시


def _load_fh_data():
    """Freedom House Excel을 다운로드(또는 캐시)해 DataFrame 반환."""
    global _fh_cache
    if _fh_cache is not None:
        return _fh_cache
    import io, requests as req
    url = "https://freedomhouse.org/sites/default/files/2024-02/All_data_FIW_2013-2024.xlsx"
    r = req.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="FIW13-24", header=1)
    # 실제 컬럼명 정리
    df.columns = [str(c).strip() for c in df.columns]
    # 국가만 (C/T == 'c')
    if "C/T" in df.columns:
        df = df[df["C/T"] == "c"].copy()
    df["iso3"] = df["Country/Territory"].map(FH_NAME_TO_ISO)
    df["Edition"] = pd.to_numeric(df["Edition"], errors="coerce")
    df = df.dropna(subset=["Edition"])
    df["Edition"] = df["Edition"].astype(int)
    _fh_cache = df
    return df


@app.route("/api/freedom_house")
def api_freedom_house():
    """Freedom House FIW 2013-2024 데이터 반환."""
    try:
        raw_countries = request.args.get("countries", "")
        year_start = int(request.args.get("year_start", 2013))
        year_end   = int(request.args.get("year_end", 2024))
        if not raw_countries.strip():
            return jsonify({"error": "국가를 하나 이상 선택하세요."}), 400

        country_set = [c.strip().upper() for c in raw_countries.split(",") if c.strip()]
        df = _load_fh_data()

        result = {}  # { iso3: [{year, total, pr, cl, status}, ...] }
        for iso in country_set:
            sub = df[(df["iso3"] == iso) &
                     (df["Edition"] >= year_start) &
                     (df["Edition"] <= year_end)].sort_values("Edition")
            if sub.empty:
                continue
            rows = []
            for _, row in sub.iterrows():
                rows.append({
                    "year":   int(row["Edition"]),
                    "total":  int(row["Total"])   if pd.notna(row.get("Total"))     else None,
                    "pr":     int(row["PR rating"]) if pd.notna(row.get("PR rating")) else None,
                    "cl":     int(row["CL rating"]) if pd.notna(row.get("CL rating")) else None,
                    "status": str(row["Status"])  if pd.notna(row.get("Status"))    else None,
                })
            result[iso] = rows

        return jsonify({
            "countries": country_set,
            "year_start": year_start,
            "year_end": year_end,
            "data": result,
            "note": "Freedom House Freedom in the World 2013-2024. Total: 0-100(높을수록 자유). PR/CL: 1-7(낮을수록 자유).",
        })
    except Exception as e:
        print(f"[FH] error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


# ── V-Dem (OWID 기반 CSV) ───────────────────────────────────────────────────
VDEM_SOURCES = {
    "electoral":     ("선거 민주주의 지수",       "https://ourworldindata.org/grapher/electoral-democracy.csv?v=1",         "Electoral Democracy Index"),
    "liberal":       ("자유 민주주의 지수",        "https://ourworldindata.org/grapher/liberal-democracy.csv?v=1",            "Liberal Democracy Index"),
    "participatory": ("참여 민주주의 지수",        "https://ourworldindata.org/grapher/participatory-democracy-index.csv?v=1","Participatory Denocracy Index"),
    "human_rights":  ("인권 지수",                "https://ourworldindata.org/grapher/civil-liberties.csv?v=1",              "Human Rights Index"),
}
_vdem_cache = {}  # { key: DataFrame }


def _load_vdem(key):
    if key in _vdem_cache:
        return _vdem_cache[key]
    import io, requests as req
    _, url, col = VDEM_SOURCES[key]
    r = req.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    _vdem_cache[key] = df
    return df


@app.route("/api/vdem")
def api_vdem():
    """V-Dem 4개 지수 (OWID 기반 CSV). 값 0~1, 높을수록 민주적."""
    try:
        raw_countries = request.args.get("countries", "")
        year_start = int(request.args.get("year_start", 1970))
        year_end   = int(request.args.get("year_end", 2024))
        if not raw_countries.strip():
            return jsonify({"error": "국가를 하나 이상 선택하세요."}), 400

        country_set = [c.strip().upper() for c in raw_countries.split(",") if c.strip()]
        result = {}   # { iso3: { key: [{year, value}] } }

        for key, (label, url, col) in VDEM_SOURCES.items():
            try:
                df = _load_vdem(key)
                sub = df[(df["Code"].isin(country_set)) &
                         (df["Year"] >= year_start) &
                         (df["Year"] <= year_end)].copy()
                for iso in country_set:
                    rows = sub[sub["Code"] == iso].sort_values("Year")
                    if rows.empty:
                        continue
                    if iso not in result:
                        result[iso] = {}
                    result[iso][key] = [
                        {"year": int(r["Year"]),
                         "value": round(float(r[col]), 4) if pd.notna(r[col]) else None}
                        for _, r in rows.iterrows()
                    ]
            except Exception as e:
                print(f"[VDEM] {key}: {e}", flush=True)

        indicators = {k: v[0] for k, v in VDEM_SOURCES.items()}
        return jsonify({
            "countries": country_set,
            "year_start": year_start,
            "year_end": year_end,
            "indicators": indicators,
            "data": result,
            "note": "V-Dem (Varieties of Democracy) via Our World in Data. 값 0~1, 높을수록 민주적.",
        })
    except Exception as e:
        print(f"[VDEM] error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route("/crisis")
def crisis_page():
    return send_from_directory("static", "crisis.html")


@app.route("/map")
@app.route("/missile")
def missile_map_page():
    """미사일 공격 상황 지도. missile_map.html(folium 생성)이 있으면 사용, 없으면 map_leaflet.html(Leaflet) 제공."""
    import os
    if os.path.isfile(os.path.join(app.static_folder, "missile_map.html")):
        return send_from_directory("static", "missile_map.html")
    return send_from_directory("static", "map_leaflet.html")


@app.route("/news")
def news_page():
    return send_from_directory("static", "news.html")


# ── News RSS ──────────────────────────────────────────────────────────────
import feedparser, time

NEWS_FEEDS = [
    {
        "name": "Google News (한국어)",
        "url": "https://news.google.com/rss/search?q=%EC%9D%B4%EB%9E%80+%EC%A0%84%EC%9F%81+%EC%9D%B4%EC%8A%A4%EB%9D%BC%EC%97%98&hl=ko&gl=KR&ceid=KR:ko",
        "lang": "ko",
    },
    {
        "name": "Google News (English)",
        "url": "https://news.google.com/rss/search?q=Iran+Israel+war+military&hl=en-US&gl=US&ceid=US:en",
        "lang": "en",
    },
    {
        "name": "Reuters World",
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "lang": "en",
    },
    {
        "name": "BBC Middle East",
        "url": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
        "lang": "en",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "lang": "en",
    },
]

IRAN_KEYWORDS = [
    "iran", "israel", "idf", "hamas", "hezbollah", "tehran", "netanyahu",
    "khamenei", "persian", "strait of hormuz", "irgc", "mossad",
    "이란", "이스라엘", "헤즈볼라", "하마스", "호르무즈", "테헤란",
    "네타냐후", "중동", "가자", "레바논",
]

CAT_RULES = {
    "군사/전투": ["missile", "attack", "strike", "bomb", "military", "idf", "irgc",
                  "공격", "미사일", "폭격", "군사", "전투", "포격", "드론"],
    "외교/정치": ["diplomacy", "sanction", "negotiat", "ceasefire", "un ", "peace",
                  "외교", "협상", "제재", "정전", "유엔", "평화", "회담"],
    "경제/에너지": ["oil", "energy", "economy", "trade", "barrel", "opec",
                    "석유", "에너지", "경제", "무역", "유가", "천연가스"],
    "인도주의": ["humanitarian", "civilian", "casualt", "refugee", "aid",
                 "민간인", "사상자", "피난민", "구호", "인도주의"],
}

_news_cache = {"articles": [], "fetched_at": None}
_news_cache_ts = 0.0


def _categorize(text: str) -> str:
    t = text.lower()
    for cat, kws in CAT_RULES.items():
        if any(k in t for k in kws):
            return cat
    return "기타"


def _is_relevant(title: str, summary: str) -> bool:
    combined = (title + " " + summary).lower()
    return any(k in combined for k in IRAN_KEYWORDS)


@app.route("/api/news")
def api_news():
    global _news_cache, _news_cache_ts
    now = time.time()
    refresh = request.args.get("refresh") == "1"
    if not refresh and now - _news_cache_ts < 1800:
        return jsonify(_news_cache)

    articles = []
    errors = []
    for feed_info in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()
                # strip HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:350]
                link = entry.get("link", "")
                published = entry.get("published", "")
                source = feed_info.get("name", "")
                lang = feed_info.get("lang", "en")
                if not title or not link:
                    continue
                # For non-Google feeds filter by Iran relevance
                if "google" not in feed_info["url"] and not _is_relevant(title, summary):
                    continue
                articles.append({
                    "title": title,
                    "link": link,
                    "published": published,
                    "source": source,
                    "summary": summary,
                    "lang": lang,
                    "category": _categorize(title + " " + summary),
                })
        except Exception as e:
            errors.append({"feed": feed_info["name"], "error": str(e)})
            print(f"[news] feed error {feed_info['name']}: {e}", flush=True)

    _news_cache = {
        "articles": articles,
        "fetched_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "errors": errors,
    }
    _news_cache_ts = now
    return jsonify(_news_cache)


@app.route("/install_yfinance.bat")
def download_install_bat():
    """yfinance 설치용 배치 파일 다운로드 (프로젝트 폴더에 저장 후 더블클릭)"""
    return send_from_directory(
        app.root_path, "install_yfinance.bat",
        as_attachment=True, download_name="install_yfinance.bat"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
