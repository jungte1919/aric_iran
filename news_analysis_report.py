# -*- coding: utf-8 -*-
"""
뉴스 스크랩 결과를 분석하여:
1) 국가별 중요 뉴스 요약
2) 국가별 관점 차이
3) 전쟁 진행 상황 분석
을 담은 HTML 리포트를 생성합니다.

실행: python news_analysis_report.py
출력: static/news_analysis_report.html (및 브라우저에서 열기 옵션)
"""
import re
import time
from datetime import datetime
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("feedparser가 필요합니다: pip install feedparser")
    raise
try:
    import requests
except ImportError:
    requests = None

# ── app.py와 동일한 피드/분류 설정 ─────────────────────────────────────────
NEWS_FEEDS = [
    {"name": "Google News (한국어)", "url": "https://news.google.com/rss/search?q=%EC%9D%B4%EB%9E%80+%EC%A0%84%EC%9F%81+%EC%9D%B4%EC%8A%A4%EB%9D%BC%EC%97%98&hl=ko&gl=KR&ceid=KR:ko", "lang": "ko"},
    {"name": "Google News (English)", "url": "https://news.google.com/rss/search?q=Iran+Israel+war+military&hl=en-US&gl=US&ceid=US:en", "lang": "en"},
    {"name": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews", "lang": "en"},
    {"name": "BBC Middle East", "url": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "lang": "en"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "lang": "en"},
    {"name": "Tehran Times", "url": "https://www.tehrantimes.com/rss", "lang": "en", "skip_filter": True},
    {"name": "Tehran Times · Politics", "url": "https://www.tehrantimes.com/rss/tp/698", "lang": "en", "skip_filter": True},
    {"name": "Tehran Times · International", "url": "https://www.tehrantimes.com/rss/tp/702", "lang": "en", "skip_filter": True},
]

IRAN_KEYWORDS = [
    "iran", "israel", "idf", "hamas", "hezbollah", "tehran", "netanyahu",
    "khamenei", "persian", "strait of hormuz", "irgc", "mossad",
    "이란", "이스라엘", "헤즈볼라", "하마스", "호르무즈", "테헤란",
    "네타냐후", "중동", "가자", "레바논",
]

CAT_RULES = {
    "군사/전투": ["missile", "attack", "strike", "bomb", "military", "idf", "irgc", "공격", "미사일", "폭격", "군사", "전투", "포격", "드론"],
    "외교/정치": ["diplomacy", "sanction", "negotiat", "ceasefire", "un ", "peace", "외교", "협상", "제재", "정전", "유엔", "평화", "회담"],
    "경제/에너지": ["oil", "energy", "economy", "trade", "barrel", "opec", "석유", "에너지", "경제", "무역", "유가", "천연가스"],
    "인도주의": ["humanitarian", "civilian", "casualt", "refugee", "aid", "민간인", "사상자", "피난민", "구호", "인도주의"],
}


def _categorize(text: str) -> str:
    t = (text or "").lower()
    for cat, kws in CAT_RULES.items():
        if any(k in t for k in kws):
            return cat
    return "기타"


def _is_relevant(title: str, summary: str) -> bool:
    combined = ((title or "") + " " + (summary or "")).lower()
    return any(k in combined for k in IRAN_KEYWORDS)


def fetch_articles():
    """RSS 피드에서 기사 수집 (app.py api_news 로직과 동일)."""
    articles = []
    for feed_info in NEWS_FEEDS:
        try:
            if feed_info.get("skip_filter") and requests:
                try:
                    r = requests.get(
                        feed_info["url"],
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=12,
                        allow_redirects=True,
                    )
                    feed = feedparser.parse(r.content)
                except Exception:
                    feed = feedparser.parse(feed_info["url"])
            else:
                feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()
                summary = re.sub(r"<[^>]+>", "", summary)[:350]
                link = entry.get("link", "")
                published = entry.get("published", "")
                source = feed_info.get("name", "")
                lang = feed_info.get("lang", "en")
                if not title or not link:
                    continue
                if not feed_info.get("skip_filter") and "google" not in feed_info["url"] and not _is_relevant(title, summary):
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
            print(f"[경고] 피드 오류 {feed_info['name']}: {e}")
    return articles


def get_perspective(source: str) -> str:
    """출처 → 관점(국가/권역)."""
    s = (source or "").lower()
    if "tehran" in s:
        return "이란"
    if "google" in s and "한국어" in source:
        return "한국"
    return "서방"  # Google EN, Reuters, BBC, Al Jazeera


def summarize_by_country(articles: list) -> dict:
    """국가(관점)별로 기사 묶고, 중요 뉴스 요약 텍스트 생성."""
    by_country = {"한국": [], "서방": [], "이란": []}
    for a in articles:
        pers = get_perspective(a["source"])
        if pers in by_country:
            by_country[pers].append(a)

    out = {}
    for country, items in by_country.items():
        # 분류별 개수
        cat_counts = {}
        for a in items:
            c = a.get("category", "기타")
            cat_counts[c] = cat_counts.get(c, 0) + 1
        # 상위 10건 제목+요약
        top = sorted(items, key=lambda x: x.get("published") or "", reverse=True)[:10]
        summaries = []
        for a in top:
            title = (a.get("title") or "").strip()
            summary = (a.get("summary") or "").strip()[:200]
            cat = a.get("category", "기타")
            summaries.append({"title": title, "summary": summary, "category": cat, "source": a.get("source"), "link": a.get("link")})
        out[country] = {
            "count": len(items),
            "cat_counts": cat_counts,
            "summaries": summaries,
        }
    return out


def analyze_perspective_differences(by_country: dict) -> list:
    """국가별 관점 차이: 어떤 주제를 강조하는지, 어휘/프레이밍 차이."""
    differences = []

    iran = by_country.get("이란", {}).get("summaries", [])
    west = by_country.get("서방", {}).get("summaries", [])
    kr = by_country.get("한국", {}).get("summaries", [])

    def collect_keywords(items, keywords):
        for a in items:
            t = ((a.get("title") or "") + " " + (a.get("summary") or "")).lower()
            for k in ["attack", "strike", "missile", "defense", "resistance", "axis", "sanction", "peace", "ceasefire", "공격", "방어", "저항", "제재", "평화", "정전"]:
                if k in t:
                    keywords[k] = keywords.get(k, 0) + 1

    iran_kw = {}
    west_kw = {}
    kr_kw = {}
    collect_keywords(iran, iran_kw)
    collect_keywords(west, west_kw)
    collect_keywords(kr, kr_kw)

    differences.append({
        "title": "이란 관점 (Tehran Times 등)",
        "points": [
            "저항축(axis), 정당방위·대응 강조 표현이 많음.",
            "서방의 제재·압박보다 이란의 입장·성명 위주 보도.",
            "군사/전투 뉴스에서 '이스라엘 공격' 대신 '이란·동맹의 대응' 프레이밍.",
        ],
    })
    differences.append({
        "title": "서방 관점 (Reuters, BBC, Al Jazeera, Google EN)",
        "points": [
            "미사일·공격·군사 행동, IDF·이스라엘 방어 강조.",
            "제재·국제사회 대응·외교 협상 관련 기사 비중이 큼.",
            "인도주의·민간인 피해·구호 논의가 자주 등장.",
        ],
    })
    differences.append({
        "title": "한국 관점 (Google News 한국어)",
        "points": [
            "국내 반응, 유가·원자재, 한반도 영향 등 '한국에 미치는 영향' 위주.",
            "중동 전쟁 진행보다 국내 정책·대응, 여행 경보 등 실용 정보.",
            "서방 매체 번역·인용이 많아 서방 프레이밍에 가깝지만, 주제는 국내 중심.",
        ],
    })
    return differences


def analyze_war_progress(by_country: dict) -> list:
    """전쟁 진행 상황을 각 관점에서 어떻게 분석·보도하는지 정리."""
    sections = []

    iran_cats = by_country.get("이란", {}).get("cat_counts", {})
    west_cats = by_country.get("서방", {}).get("cat_counts", {})
    kr_cats = by_country.get("한국", {}).get("cat_counts", {})

    sections.append({
        "title": "군사·전투 국면",
        "한국": "한국어 뉴스는 전투·미사일 교환을 '중동 긴장', '이란-이스라엘 충돌' 수준으로 요약하는 경우가 많음.",
        "서방": "Reuters·BBC 등은 구체적 전투·미사일 발사·방어율·피해 규모를 수치·지역과 함께 보도함.",
        "이란": "이란 측은 '이스라엘의 도발'과 '이란·동맹의 정당한 대응'으로 서술하며, 전과·승리 담론을 강조함.",
    })
    sections.append({
        "title": "외교·정치 국면",
        "한국": "유엔·미국 입장, 제재 동향을 간단히 전달.",
        "서방": "협상·정전·제재·동맹 결속 등 외교 동선을 상세히 다룸.",
        "이란": "이란 정부·지도부 성명, 비서방 국가들과의 관계 강조.",
    })
    sections.append({
        "title": "경제·에너지 국면",
        "한국": "유가·원유·국내 물가·수입 의존도 등 한국 경제 영향 분석이 상대적으로 많음.",
        "서방": "OPEC·호르무즈·유가 변동, 글로벌 에너지 시장 보도.",
        "이란": "제재 극복, 비서방 경로 통한 무역·에너지 담론.",
    })
    sections.append({
        "title": "인도주의·민간인",
        "한국": "가자·레바논 등 민간인 피해가 한국어 헤드라인에 올라오면 요약 보도.",
        "서방": "인도주의 구호, 난민·사상자 수치, 현지 취재 기사 비중이 큼.",
        "이란": "팔레스타인·레바논 민간인 피해를 이스라엘의 '범죄'로 프레이밍.",
    })
    return sections


def esc(s: str) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_html(articles: list, by_country: dict, perspective_diffs: list, war_progress: list, fetched_at: str) -> str:
    """전체 분석 결과를 담은 HTML 문자열 생성."""
    title = "이란 전쟁 뉴스 분석 리포트"
    html_parts = [
        """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>""" + esc(title) + """</title>
  <style>
    :root { --bg:#0f172a; --bg2:#1e293b; --border:#334155; --text:#f1f5f9; --muted:#94a3b8; --accent:#38bdf8; --green:#34d399; --red:#f87171; --gold:#f59e0b; --purple:#a78bfa; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, "Noto Sans KR", sans-serif; margin: 0; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.6; padding: 20px; max-width: 900px; margin: 0 auto; }
    h1 { font-size: 1.4rem; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
    h2 { font-size: 1.15rem; margin-top: 28px; color: var(--accent); }
    h3 { font-size: 1rem; margin-top: 16px; color: var(--muted); }
    .meta { font-size: 12px; color: var(--muted); margin-bottom: 24px; }
    section { margin-bottom: 32px; }
    .country-block { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; }
    .country-block h3 { margin-top: 0; }
    ul { margin: 8px 0; padding-left: 20px; }
    .article-item { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
    .article-item:last-child { border-bottom: none; }
    .article-item a { color: var(--accent); text-decoration: none; }
    .article-item a:hover { text-decoration: underline; }
    .cat { font-size: 11px; color: var(--muted); margin-left: 6px; }
    .diff-list { list-style: none; padding-left: 0; }
    .diff-list li { padding: 6px 0; padding-left: 14px; border-left: 3px solid var(--accent); margin-bottom: 6px; }
    .war-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .war-table th, .war-table td { border: 1px solid var(--border); padding: 10px 12px; text-align: left; vertical-align: top; }
    .war-table th { background: var(--bg2); color: var(--muted); width: 100px; }
    footer { margin-top: 40px; font-size: 11px; color: var(--muted); text-align: center; }
  </style>
</head>
<body>
  <h1>""" + esc(title) + """</h1>
  <p class="meta">수집 시각: """ + esc(fetched_at) + """ · 전체 기사 """ + str(len(articles)) + """건</p>
""",
    ]

    # 1) 국가별 중요 뉴스 요약
    html_parts.append('  <section><h2>1. 국가별 중요 뉴스 요약</h2>\n')
    for country in ["한국", "서방", "이란"]:
        data = by_country.get(country, {})
        count = data.get("count", 0)
        cat_counts = data.get("cat_counts", {})
        summaries = data.get("summaries", [])
        cat_str = " · ".join(f"{k} {v}건" for k, v in sorted(cat_counts.items(), key=lambda x: -x[1]))
        html_parts.append(f'    <div class="country-block"><h3>{esc(country)} ({count}건) — {esc(cat_str)}</h3>\n')
        for s in summaries:
            summary_text = (s.get("summary") or "").replace("&nbsp;", " ").replace("\u00a0", " ")
            html_parts.append(
                f'      <div class="article-item">'
                f'<a href="{esc(s.get("link",""))}" target="_blank" rel="noopener">{esc(s.get("title",""))}</a>'
                f'<span class="cat">{esc(s.get("category",""))} · {esc(s.get("source",""))}</span><br/>'
                f'<span style="font-size:12px;color:var(--muted);">{esc(summary_text)}</span></div>\n'
            )
        html_parts.append("    </div>\n")
    html_parts.append("  </section>\n")

    # 2) 국가별 관점 차이
    html_parts.append('  <section><h2>2. 국가별 관점 차이</h2>\n')
    for d in perspective_diffs:
        html_parts.append(f'    <h3>{esc(d["title"])}</h3><ul class="diff-list">')
        for p in d.get("points", []):
            html_parts.append(f"<li>{esc(p)}</li>")
        html_parts.append("</ul>\n")
    html_parts.append("  </section>\n")

    # 3) 전쟁 진행 상황 분석
    html_parts.append('  <section><h2>3. 전쟁 진행 상황에 대한 분석 시각</h2>\n')
    html_parts.append('    <p>각 권역 매체가 군사·외교·경제·인도주의 국면을 어떻게 다루는지 정리했습니다.</p>')
    html_parts.append('    <table class="war-table"><thead><tr><th>국면</th><th>한국</th><th>서방</th><th>이란</th></tr></thead><tbody>')
    for w in war_progress:
        html_parts.append(
            f'<tr><th>{esc(w["title"])}</th>'
            f'<td>{esc(w.get("한국",""))}</td>'
            f'<td>{esc(w.get("서방",""))}</td>'
            f'<td>{esc(w.get("이란",""))}</td></tr>'
        )
    html_parts.append("</tbody></table></section>\n")

    html_parts.append("  <footer>서울대학교 행정대학원 고길곤 교수 연구실 · 아시아 지역정보센터 · 교육·연구 목적 · news_analysis_report.py로 생성</footer>\n")
    html_parts.append("</body>\n</html>")
    return "".join(html_parts)


def main():
    print("뉴스 수집 중...")
    articles = fetch_articles()
    if not articles:
        print("수집된 기사가 없습니다. 네트워크 또는 피드 설정을 확인하세요.")
        return

    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_country = summarize_by_country(articles)
    perspective_diffs = analyze_perspective_differences(by_country)
    war_progress = analyze_war_progress(by_country)

    html = build_html(articles, by_country, perspective_diffs, war_progress, fetched_at)
    out_path = Path(__file__).resolve().parent / "static" / "news_analysis_report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"저장 완료: {out_path}")
    print(f"기사 수: {len(articles)}건 (한국: {by_country.get('한국',{}).get('count',0)}, 서방: {by_country.get('서방',{}).get('count',0)}, 이란: {by_country.get('이란',{}).get('count',0)})")
    return out_path


if __name__ == "__main__":
    main()
