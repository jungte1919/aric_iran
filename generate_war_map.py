# -*- coding: utf-8 -*-
"""
2026년 미국-이란 전쟁 미사일 공격 지도 생성.
실행: python generate_war_map.py
생성 파일: static/missile_map.html
"""
import os
import sys

def main():
    try:
        import geopandas as gpd
        import folium
        import pandas as pd
    except ImportError as e:
        print("필요 패키지 설치: pip install geopandas folium pandas")
        raise e

    WORLD_URL = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"

    attack_data = {
        '도시명': [
            '테헤란', '이스파한', '곰', '카라지', '케르만샤', '타브리즈', '카즈빈',
            '텔아비브', '예루살렘', '하이파', '베르셰바', '아슈돗', '네타냐', '골란고원', '에일랏',
            '마나마(바레인)', '도하(카타르)', '아부다비(UAE)', '두바이(UAE)', '쿠웨이트시',
            '바그다드(이라크)', '암만(요르단)', '리야드(사우디)', '제다(사우디)', '무스카트(오만)', '살랄라(오만)',
            '니코시아(키프로스)'
        ],
        '영문명': [
            'Tehran', 'Isfahan', 'Gom', 'Karaj', 'Kermanshah', 'Tabriz', 'Qazvin',
            'Tel Aviv', 'Jerusalem', 'Haifa', 'Beer Sheva', 'Ashdod', 'Netanya', 'Golan Heights', 'Eilat',
            'Manama', 'Doha', 'Abu Dhabi', 'Dubai', 'Kuwait City',
            'Baghdad', 'Amman', 'Riyadh', 'Jeddah', 'Muscat', 'Salalah',
            'Nicosia'
        ],
        '위도': [
            35.6892, 32.6546, 34.2996, 35.8172, 34.3141, 38.0808, 36.2765,
            32.0853, 31.7683, 32.8193, 31.2461, 31.8041, 32.3384, 33.1835, 29.5581,
            26.1551, 25.2854, 24.4539, 25.2048, 29.3759,
            33.3128, 31.9454, 24.7136, 21.5433, 23.6100, 17.0832,
            35.1264
        ],
        '경도': [
            51.3890, 51.6243, 50.9676, 50.9808, 46.0981, 46.2919, 50.0068,
            34.7818, 35.2137, 34.9526, 34.7913, 34.6479, 34.8683, 35.7924, 34.9521,
            50.4367, 51.5310, 54.3773, 55.2708, 47.9774,
            44.3615, 35.9284, 46.6753, 39.1721, 58.5400, 54.0924,
            33.3823
        ],
        '공격유형': [
            '정부 청사, 지도부 암살', '군사 시설', '군사 기지', '군사 시설', '미사일 기지', '미사일 발사대', '공군 기지',
            '민간 지역, 공항', '구도심 지역', '항구도시', '남부 도시', '항구도시', '해안 도시', '전략적 고지', '공항, 전략 시설',
            '미 해군 5함대 사령부', '미군 공군기지', 'UAE 전략 시설', 'UAE 에너지 시설, 공항', '미군 기지',
            '미군 공군기지', '미군 기지', '미군 기지, 왕궁', '미군 함대 기지', '협상 장소, 미군 기지', '전략 석유 시설',
            '영국 군사 기지'
        ],
        '피해규모': [
            '매우 심각', '중대', '중대', '중대', '중대', '중대', '중대',
            '심각', '심각', '중대', '중대', '중대', '중대', '중대', '중대',
            '중대', '중대', '심각', '심각', '중대', '중대', '중대', '심각', '중대', '중대', '중대',
            '중대'
        ],
        '공격국': [
            '미국/이스라엘', '미국/이스라엘', '미국/이스라엘', '미국/이스라엘', '미국/이스라엘', '미국/이스라엘', '미국/이스라엘',
            '이란', '이란', '이란', '이란', '이란', '이란', '이란', '이란',
            '이란', '이란', '이란', '이란', '이란', '이란', '이란', '이란', '이란', '이란', '이란',
            '이란'
        ],
        '지역분류': [
            '이란', '이란', '이란', '이란', '이란', '이란', '이란',
            '이스라엘', '이스라엘', '이스라엘', '이스라엘', '이스라엘', '이스라엘', '이스라엘', '이스라엘',
            '중동', '중동', '중동', '중동', '중동', '중동', '중동', '중동', '중동', '중동', '중동',
            '키프로스'
        ]
    }

    # 위도/경도 개수 맞춤 (도시명 27개)
    df_attacks = pd.DataFrame(attack_data)
    if len(df_attacks['위도']) != len(df_attacks['도시명']):
        raise ValueError("위도/경도 개수가 도시명과 맞지 않습니다.")

    country_name_kr = {
        "Iran": "이란", "Israel": "이스라엘", "Saudi Arabia": "사우디아라비아",
        "Iraq": "이라크", "United Arab Emirates": "아랍에미리트", "Kuwait": "쿠웨이트",
        "Qatar": "카타르", "Bahrain": "바레인", "Oman": "오만", "Yemen": "예멘",
        "Syria": "시리아", "Lebanon": "레바논", "Jordan": "요르단", "Cyprus": "키프로스"
    }

    m = folium.Map(location=[30, 40], zoom_start=5, tiles="OpenStreetMap")

    try:
        world = gpd.read_file(WORLD_URL)
        gdf = world[world["NAME"].isin(list(country_name_kr.keys()))].copy()
        if gdf.crs and str(gdf.crs) != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)

        for idx, row in gdf.iterrows():
            country_name = row["NAME"]
            country_name_korean = country_name_kr.get(country_name, country_name)
            if country_name == "Iran":
                fill_color, color, weight, opacity = "#FFE5E5", "#FF0000", 2.5, 0.7
                label = "이란 (공격 대상)"
            elif country_name == "Israel":
                fill_color, color, weight, opacity = "#E5F3FF", "#0066CC", 2.5, 0.7
                label = "이스라엘"
            else:
                fill_color, color, weight, opacity = "#E8E8E8", "#808080", 1, 0.4
                label = country_name_korean

            def style_fn(x, c=color, fc=fill_color, w=weight, o=opacity):
                return {'fillColor': fc, 'color': c, 'weight': w, 'fillOpacity': o}

            folium.GeoJson(
                gpd.GeoSeries(row.geometry).__geo_interface__,
                style_function=style_fn,
                tooltip=folium.Tooltip(label)
            ).add_to(m)
    except Exception as e:
        print("국가 경계 로드 생략:", e)

    for idx, row in df_attacks.iterrows():
        city_kr = row['도시명']
        city_en = row['영문명']
        lat, lon = row['위도'], row['경도']
        attack_type = row['공격유형']
        attacker = row['공격국']
        damage = row['피해규모']
        region = row['지역분류']

        if attacker == '미국/이스라엘':
            popup_color, icon_color = '#FF6B6B', 'red'
        elif region == '이스라엘':
            popup_color, icon_color = '#FF5C5C', 'darkred'
        else:
            popup_color, icon_color = '#4ECDC4', 'blue'

        radius = 35000 if damage == '매우 심각' else 25000 if damage == '심각' else 15000

        popup_html = f"""
        <div style="font-family: 'Malgun Gothic', 'Noto Sans KR', sans-serif; font-size: 12px; width: 250px;">
            <h4 style="margin: 5px 0; color: {popup_color}; border-bottom: 3px solid {popup_color}; padding-bottom: 5px;">{city_kr}</h4>
            <table style="width: 100%; margin-top: 8px; border-collapse: collapse;">
                <tr style="background: #f5f5f5;"><td style="width: 45%; font-weight: bold; padding: 4px;">영문명:</td><td style="padding: 4px;">{city_en}</td></tr>
                <tr><td style="font-weight: bold; padding: 4px;">공격 유형:</td><td style="padding: 4px;">{attack_type}</td></tr>
                <tr style="background: #f5f5f5;"><td style="font-weight: bold; padding: 4px;">공격국:</td><td><span style="background: {popup_color}; color: white; padding: 2px 6px; border-radius: 3px;">{attacker}</span></td></tr>
                <tr><td style="font-weight: bold; padding: 4px;">피해규모:</td><td style="padding: 4px;">● {damage}</td></tr>
                <tr style="background: #f5f5f5;"><td style="font-weight: bold; padding: 4px;">지역:</td><td style="padding: 4px;">{region}</td></tr>
                <tr style="border-top: 2px dashed #ddd;"><td colspan="2" style="font-size: 10px; color: #666; padding: 4px;">📅 2026년 2월 28일 ~ 3월 중순</td></tr>
            </table>
        </div>
        """

        folium.Circle(
            location=[lat, lon],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=300),
            color=icon_color,
            fill=True,
            fillColor=popup_color,
            fillOpacity=0.6,
            weight=2,
            tooltip=f"{city_kr} - {damage}"
        ).add_to(m)

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=city_kr,
            icon=folium.Icon(color=icon_color, icon='info-sign', prefix='fa')
        ).add_to(m)

    legend_html = '''
    <div style="position: fixed; bottom: 50px; right: 50px; width: 330px; background: white; border: 3px solid #333; z-index: 9999;
         font-size: 12px; padding: 15px; font-family: 'Malgun Gothic', 'Noto Sans KR', sans-serif;">
    <h3 style="margin: 0 0 12px; color: #333; border-bottom: 3px solid #FF6B6B; padding-bottom: 8px;">🔴 2026년 미국-이란 전쟁</h3>
    <h4 style="margin: 8px 0 4px; color: #555;">미사일 공격 현황</h4>
    <div style="margin-bottom: 12px; padding: 8px; background: #fff5f5; border-left: 4px solid #FF6B6B;">
        <b style="color: #FF6B6B;">🟥 미국/이스라엘 공격</b><br>
        <span style="font-size: 11px;">이란 내 군사시설, 정부청사 등</span>
    </div>
    <div style="margin-bottom: 12px; padding: 8px; background: #fff0f0; border-left: 4px solid #FF5C5C;">
        <b style="color: #FF5C5C;">🟥 이란의 이스라엘 보복</b><br>
        <span style="font-size: 11px;">이스라엘 도시, 공항 등</span>
    </div>
    <div style="margin-bottom: 12px; padding: 8px; background: #e5f7f5; border-left: 4px solid #4ECDC4;">
        <b style="color: #4ECDC4;">🟦 이란의 중동 미군기지 공격</b><br>
        <span style="font-size: 11px;">걸프 지역 미군 기지 등</span>
    </div>
    <hr style="margin: 10px 0;">
    <b>● 원의 크기 = 피해규모</b><br>
    <span style="font-size: 11px;">매우 심각(큼) / 심각(중간) / 중대(작음)</span>
    <hr style="margin: 10px 0;">
    <div style="font-size: 10px; color: #555;">⏰ 2026년 2월 28일 ~ 진행 중</div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    out_path = os.path.join(os.path.dirname(__file__), 'static', 'missile_map.html')
    m.save(out_path)
    print("✓ 미사일 공격 지도 생성 완료:", out_path)
    return m

if __name__ == "__main__":
    main()
