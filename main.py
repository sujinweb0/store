import streamlit as st
import pandas as pd
import plotly.express as px
import math
import os

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 제목
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="편의점 & 카페 지도 검색",
    page_icon="🏪",
    layout="wide"
)

st.title("🏪 편의점 & ☕ 카페 위치 지도 앱")
st.caption("지역별, 업종별 매장 위치를 지도에서 확인하고 특정 매장 기준 반경 검색을 수행합니다.")


# -----------------------------------------------------------------------------
# 2. 하버사인(Haversine) 공식 함수
# 두 위도/경도 좌표 간의 대원 거리(km)를 계산합니다.
# -----------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    # 지구 반지름 (단위: km)
    R = 6371.0
    
    # 각도를 라디안으로 변환
    rad_lat1 = math.radians(lat1)
    rad_lon1 = math.radians(lon1)
    rad_lat2 = math.radians(lat2)
    rad_lon2 = math.radians(lon2)
    
    # 위도 및 경도 차이
    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1
    
    # 하버사인 공식 계산
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance


# -----------------------------------------------------------------------------
# 3. 데이터 불러오기 및 전처리 (캐싱 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 파일명 호환성 체크 (store.csv 우선, 없으면 store_filtered.csv)
    file_path = "store.csv"
    if not os.path.exists(file_path):
        if os.path.exists("store_filtered.csv"):
            file_path = "store_filtered.csv"
        else:
            st.error("데이터 파일(store.csv 또는 store_filtered.csv)을 찾을 수 없습니다.")
            return pd.DataFrame()

    df = pd.read_csv(file_path)

    # 1) 위도, 경도 숫자형 변환 및 결측치 제거
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    # 2) 업종이 '편의점' 또는 '카페'인 데이터만 필터링
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    return df

df_raw = load_data()

# 데이터가 비어 있는 경우 앱 중단
if df_raw.empty:
    st.warning("표시할 매장 데이터가 없습니다. CSV 파일을 확인해 주세요.")
    st.stop()


# -----------------------------------------------------------------------------
# 4. 사이드바 - 지역(시/도) 선택 및 필터링
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 검색 및 필터 옵션")

# 시/도 목록 추출 (결측치 제외 후 정렬)
sido_list = sorted([str(s) for s in df_raw["시도명"].dropna().unique()])
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

# 선택한 시/도의 데이터만 1차 필터링
filtered_df = df_raw[df_raw["시도명"] == selected_sido].copy()


# -----------------------------------------------------------------------------
# 5. 사이드바 - 반경 검색 옵션 (심화 기능)
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")

search_subtitle = "" # 카드 위 표시할 부제목 문자열
center_lat, center_lon = None, None # 지도 중심 좌표 변수

if use_radius_search:
    if not filtered_df.empty:
        # 매장명을 기준 매장 드롭다운 목록으로 구성
        # 중복 상호명이 있을 수 있으므로 인덱스와 상호명을 조합하여 유일하게 구분
        store_options = filtered_df.index.tolist()
        
        selected_idx = st.sidebar.selectbox(
            "기준 매장 선택",
            options=store_options,
            format_func=lambda idx: f"{filtered_df.loc[idx, '상호명']} ({filtered_df.loc[idx, '상권업종소분류명']})"
        )
        
        radius_km = st.sidebar.slider("검색 반경 (km)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
        
        # 기준 매장의 좌표 추출
        target_store = filtered_df.loc[selected_idx]
        center_lat = target_store["위도"]
        center_lon = target_store["경도"]
        
        # 하버사인 공식을 적용하여 각 매장과의 거리 계산
        filtered_df["거리"] = filtered_df.apply(
            lambda row: haversine_distance(center_lat, center_lon, row["위도"], row["경도"]),
            axis=1
        )
        
        # 설정한 반경 이내의 매장만 2차 필터링
        filtered_df = filtered_df[filtered_df["거리"] <= radius_km]
        
        # 부제목 문자열 작성
        search_subtitle = f"📍 **{target_store['상호명']}** 기준 반경 **{radius_km} km** 이내"
    else:
        st.sidebar.warning("선택한 지역에 매장이 없습니다.")


# -----------------------------------------------------------------------------
# 6. 메인 화면 - 지표 카드 (st.metric) 출력
# -----------------------------------------------------------------------------
if search_subtitle:
    st.markdown(f"#### {search_subtitle}")

# 카운트 계산
convenience_count = len(filtered_df[filtered_df["상권업종소분류명"] == "편의점"])
cafe_count = len(filtered_df[filtered_df["상권업종소분류명"] == "카페"])
total_count = len(filtered_df)

col1, col2, col3 = st.columns(3)
col1.metric("🏪 편의점 수", f"{convenience_count:,} 개")
col2.metric("☕ 카페 수", f"{cafe_count:,} 개")
col3.metric("🏢 전체 매장 수", f"{total_count:,} 개")

st.markdown("---")


# -----------------------------------------------------------------------------
# 7. 메인 화면 - Plotly 지도 시각화
# -----------------------------------------------------------------------------
if filtered_df.empty:
    st.info("💡 조건에 일치하는 매장이 없습니다. 검색 반경이나 지역을 변경해 보세요.")
else:
    # plotly scatter_map (최신버전) vs scatter_mapbox (구버전) 분기 처리
    map_kwargs = {
        "data_frame": filtered_df,
        "lat": "위도",
        "lon": "경도",
        "color": "상권업종소분류명",
        "color_discrete_map": {"편의점": "blue", "카페": "orange"}, # 편의점: 파란색, 카페: 주황색
        "hover_name": "상호명",
        "hover_data": {"상권업종소분류명": True, "위도": False, "경도": False},
        "zoom": 13 if use_radius_search else 10,
        "height": 600
    }

    # 반경 검색 중일 경우 지도 중심점을 기준 매장 위치로 설정
    if use_radius_search and center_lat is not None and center_lon is not None:
        map_kwargs["center"] = {"lat": center_lat, "lon": center_lon}

    # px.scatter_map 존재 여부에 따른 호환성 처리
    if hasattr(px, "scatter_map"):
        fig = px.scatter_map(
            **map_kwargs,
            map_style="open-street-map"
        )
    else:
        fig = px.scatter_mapbox(
            **map_kwargs,
            mapbox_style="open-street-map"
        )

    # 여백 조절 및 지도 출력
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig, use_container_width=True)
