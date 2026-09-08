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

st.title("🏪 편의점 & ☕ 카페 동별 위치 지도 앱")
st.caption("지역별, 동별, 업종별 매장 위치를 지도와 통계표로 확인합니다.")


# -----------------------------------------------------------------------------
# 2. 하버사인(Haversine) 공식 함수
# -----------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    rad_lat1 = math.radians(lat1)
    rad_lon1 = math.radians(lon1)
    rad_lat2 = math.radians(lat2)
    rad_lon2 = math.radians(lon2)
    
    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# -----------------------------------------------------------------------------
# 3. 데이터 불러오기 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
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

    # 3) 동 이름 컬럼 처리 ('행정동명' 우선 사용, 없으면 '법정동명' 사용)
    if "행정동명" in df.columns:
        df["동명"] = df["행정동명"].fillna("미분류")
    elif "법정동명" in df.columns:
        df["동명"] = df["법정동명"].fillna("미분류")
    else:
        df["동명"] = "미분류"

    return df

df_raw = load_data()

if df_raw.empty:
    st.warning("표시할 매장 데이터가 없습니다. CSV 파일을 확인해 주세요.")
    st.stop()


# -----------------------------------------------------------------------------
# 4. 사이드바 - 지역(시/도) 및 동 선택 필터
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 검색 및 필터 옵션")

# 1) 시/도 선택
sido_list = sorted([str(s) for s in df_raw["시도명"].dropna().unique()])
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

# 시/도 데이터 1차 필터링
filtered_df = df_raw[df_raw["시도명"] == selected_sido].copy()

# 2) 동 선택 (전체 선택 옵션 포함)
dong_list = ["전체 (모든 동)"] + sorted([str(d) for d in filtered_df["동명"].unique() if d != "미분류"])
selected_dong = st.sidebar.selectbox("동 선택", dong_list)

# 특정 동을 선택한 경우 2차 필터링
if selected_dong != "전체 (모든 동)":
    filtered_df = filtered_df[filtered_df["동명"] == selected_dong]


# -----------------------------------------------------------------------------
# 5. 사이드바 - 반경 검색 옵션 (심화 기능)
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")

search_subtitle = ""
center_lat, center_lon = None, None

if use_radius_search:
    if not filtered_df.empty:
        store_options = filtered_df.index.tolist()
        
        selected_idx = st.sidebar.selectbox(
            "기준 매장 선택",
            options=store_options,
            format_func=lambda idx: f"[{filtered_df.loc[idx, '동명']}] {filtered_df.loc[idx, '상호명']} ({filtered_df.loc[idx, '상권업종소분류명']})"
        )
        
        radius_km = st.sidebar.slider("검색 반경 (km)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
        
        target_store = filtered_df.loc[selected_idx]
        center_lat = target_store["위도"]
        center_lon = target_store["경도"]
        
        filtered_df["거리"] = filtered_df.apply(
            lambda row: haversine_distance(center_lat, center_lon, row["위도"], row["경도"]),
            axis=1
        )
        
        filtered_df = filtered_df[filtered_df["거리"] <= radius_km]
        search_subtitle = f"📍 **{target_store['상호명']}** 기준 반경 **{radius_km} km** 이내"
    else:
        st.sidebar.warning("선택한 지역/동에 매장이 없습니다.")


# -----------------------------------------------------------------------------
# 6. 메인 화면 - 지표 카드 (st.metric)
# -----------------------------------------------------------------------------
if search_subtitle:
    st.markdown(f"#### {search_subtitle}")

convenience_count = len(filtered_df[filtered_df["상권업종소분류명"] == "편의점"])
cafe_count = len(filtered_df[filtered_df["상권업종소분류명"] == "카페"])
total_count = len(filtered_df)

col1, col2, col3 = st.columns(3)
col1.metric("🏪 편의점 수", f"{convenience_count:,} 개")
col2.metric("☕ 카페 수", f"{cafe_count:,} 개")
col3.metric("🏢 전체 매장 수", f"{total_count:,} 개")

st.markdown("---")


# -----------------------------------------------------------------------------
# 7. 메인 화면 - 지도 시각화
# -----------------------------------------------------------------------------
if filtered_df.empty:
    st.info("💡 조건에 일치하는 매장이 없습니다. 검색 조건이나 반경을 변경해 보세요.")
else:
    # 툴팁(마우스 호버)에 동명 정보 추가
    map_kwargs = {
        "data_frame": filtered_df,
        "lat": "위도",
        "lon": "경도",
        "color": "상권업종소분류명",
        "color_discrete_map": {"편의점": "blue", "카페": "orange"},
        "hover_name": "상호명",
        "hover_data": {"동명": True, "상권업종소분류명": True, "위도": False, "경도": False},
        "zoom": 13 if (use_radius_search or selected_dong != "전체 (모든 동)") else 10,
        "height": 500
    }

    if use_radius_search and center_lat is not None and center_lon is not None:
        map_kwargs["center"] = {"lat": center_lat, "lon": center_lon}

    if hasattr(px, "scatter_map"):
        fig_map = px.scatter_map(**map_kwargs, map_style="open-street-map")
    else:
        fig_map = px.scatter_mapbox(**map_kwargs, mapbox_style="open-street-map")

    fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig_map, use_container_width=True)

    # -------------------------------------------------------------------------
    # 8. 동별 집계 표 및 통계 차트 (신규 추가)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 동별 편의점 & 카페 현황")

    # 동별, 업종별 피벗 테이블 작성
    pivot_df = pd.pivot_table(
        filtered_df,
        index="동명",
        columns="상권업종소분류명",
        values="상호명",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    # 컬럼 정리 (편의점이나 카페 컬럼이 없는 경우 대비)
    if "편의점" not in pivot_df.columns:
        pivot_df["편의점"] = 0
    if "카페" not in pivot_df.columns:
        pivot_df["카페"] = 0

    pivot_df["합계"] = pivot_df["편의점"] + pivot_df["카페"]
    pivot_df = pivot_df.sort_values(by="합계", ascending=False)

    col_chart, col_table = st.columns([6, 4])

    with col_chart:
        # 동별 막대 그래프
        fig_bar = px.bar(
            pivot_df,
            x="동명",
            y=["편의점", "카페"],
            title="동별 매장 수 비교",
            barmode="group",
            color_discrete_map={"편의점": "blue", "카페": "orange"},
            labels={"value": "매장 수", "variable": "업종"}
        )
        fig_bar.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_table:
        # 동별 요약 표
        st.write("**동별 매장 수 요약**")
        st.dataframe(
            pivot_df[["동명", "편의점", "카페", "합계"]],
            use_container_width=True,
            hide_index=True
        )
