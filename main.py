
# main.py
# 초보자를 위한 KOBIS 일별 박스오피스 대시보드

import datetime
import json
import html
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 2. KOBIS 일별 박스오피스 API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 3. 한국 시간 기준 어제를 계산합니다.
# 서버가 해외 시간대를 사용해도 한국 날짜를 기준으로 합니다.
KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)


# 4. 달력에서 조회 날짜를 선택합니다.
st.title("🎬 일별 박스오피스")
st.caption("영화진흥위원회 KOBIS 일별 박스오피스")

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=datetime.date(1900, 1, 1),
    max_value=yesterday,
    format="YYYY-MM-DD",
)

# API는 YYYYMMDD 형식의 날짜를 요구합니다.
target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {selected_date.strftime('%Y년 %m월 %d일')}"
    f" · 오늘({today_kst.isoformat()}) 이전 날짜만 선택할 수 있습니다."
)


# 5. API 요청 함수
# 같은 날짜의 데이터는 1시간 동안 캐시에 보관합니다.
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(date_str: str, api_key: str) -> dict:
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str,
        },
        timeout=20,
    )

    # HTTP 오류 상태 코드가 있으면 예외를 발생시킵니다.
    response.raise_for_status()

    # 응답이 올바른 JSON인지 확인합니다.
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            "API 응답을 JSON으로 해석할 수 없습니다."
        ) from exc


# 6. 비밀 금고(Secrets)에서 API 인증키를 읽습니다.
# 실제 인증키를 코드에 직접 작성하지 마세요.
try:
    api_key = str(st.secrets["KOBIS_KEY"]).strip()
except (KeyError, FileNotFoundError):
    st.error("KOBIS API 인증키를 찾을 수 없습니다.")
    st.markdown(
        """
        **확인 방법**
        1. Streamlit Cloud의 Settings → Secrets로 이동합니다.
        2. 아래 설정을 추가하고 저장합니다.
        """
    )
    st.code('KOBIS_KEY = "발급받은_실제_API_인증키"')
    st.stop()

if not api_key:
    st.error("KOBIS_KEY 값이 비어 있습니다.")
    st.info("Settings → Secrets에서 올바른 인증키를 입력해 주세요.")
    st.stop()


# 7. 선택한 날짜의 데이터를 요청합니다.
try:
    with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_dt, api_key)

except requests.exceptions.Timeout:
    st.error("KOBIS API 요청 시간이 초과되었습니다.")
    st.info("잠시 후 다시 시도하거나 네트워크 상태를 확인해 주세요.")
    st.stop()

except requests.exceptions.HTTPError as exc:
    st.error("KOBIS 서버에서 HTTP 오류가 발생했습니다.")
    st.caption(f"상세 내용: {exc}")
    st.info("API 주소와 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()

except requests.exceptions.RequestException as exc:
    st.error("KOBIS API 서버에 연결할 수 없습니다.")
    st.caption(f"상세 내용: {exc}")
    st.info("네트워크 연결과 서버 상태를 확인해 주세요.")
    st.stop()

except ValueError as exc:
    st.error("KOBIS API 응답을 읽을 수 없습니다.")
    st.caption(str(exc))
    st.info("API 응답 형식과 서버 상태를 확인해 주세요.")
    st.stop()


# 8. HTTP 200이어도 faultInfo가 있으면 API 오류입니다.
if "faultInfo" in data:
    fault = data.get("faultInfo") or {}

    st.error("KOBIS API가 오류를 반환했습니다.")
    st.write(
        "**오류 코드:**",
        fault.get("errorCode", "정보 없음"),
    )
    st.write(
        "**오류 내용:**",
        fault.get("message", "오류 메시지가 없습니다."),
    )
    st.markdown(
        """
        **확인할 사항**
        - Secrets의 `KOBIS_KEY`가 정확한지 확인합니다.
        - 인증키가 발급 및 사용 가능한 상태인지 확인합니다.
        - KOBIS 오픈API 사이트에서 해당 API를 확인합니다.
        """
    )
    st.stop()


# 9. 응답에서 영화 목록을 확인합니다.
boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error("API 응답에 boxOfficeResult 항목이 없습니다.")
    st.info("KOBIS API 응답 구조와 서버 상태를 확인해 주세요.")
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

if not isinstance(movies, list) or len(movies) == 0:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        "선택한 날짜의 박스오피스 자료가 아직 제공되지 않거나 "
        "영화 목록이 비어 있습니다. KOBIS에서 해당 날짜를 직접 "
        "조회하거나 잠시 후 다시 시도해 주세요."
    )
    st.stop()


# 10. 영화 목록을 표로 만들고 데이터 형식을 정리합니다.
df = pd.DataFrame(movies)

required_columns = [
    "rank",
    "rankInten",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

missing_columns = [
    column for column in required_columns if column not in df.columns
]

if missing_columns:
    st.error("API 응답에 필요한 항목이 누락되었습니다.")
    st.write("누락된 항목:", ", ".join(missing_columns))
    st.info("KOBIS API 응답 형식을 확인해 주세요.")
    st.stop()

# API의 숫자는 문자열이므로 숫자로 변환합니다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

for column in numeric_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")

# 순위와 주요 통계가 정상적인 행만 남깁니다.
df = df.dropna(
    subset=["rank", "audiCnt", "audiAcc", "scrnCnt"]
).copy()

df = df.sort_values("rank").reset_index(drop=True)

if df.empty:
    st.warning("표시할 수 있는 영화 데이터가 없습니다.")
    st.info("KOBIS 응답의 숫자 항목을 확인해 주세요.")
    st.stop()


# 11. 영화명 옆에 트로피와 순위 변동 표시를 만듭니다.
def display_movie_name(row):
    """누적 관객수가 100만 명을 초과하면 트로피를 붙입니다."""
    name = str(row["movieNm"])
    accumulated = int(row["audiAcc"])

    if accumulated > 1_000_000:
        return f"🏆 {name}"

    return name


def display_rank_change(value):
    """전날보다 순위가 오르면 ↑, 내려가면 ↓를 표시합니다."""
    if pd.isna(value):
        return "—"

    change = int(value)

    if change > 0:
        # 빨간색 위 화살표: 순위 상승
        return f"🔴 ↑ {change}"

    if change < 0:
        # 파란색 아래 화살표: 순위 하락
        return f"🔵 ↓ {abs(change)}"

    # 변동이 없으면 화살표를 표시하지 않습니다.
    return "—"


# 12. 1위 영화의 지표 카드 세 장을 표시합니다.
top = df.iloc[0]

st.subheader(f"🥇 일별 박스오피스 1위: {display_movie_name(top)}")
st.caption(f"개봉일: {top['openDt'] or '정보 없음'}")

card1, card2, card3 = st.columns(3)

card1.metric(
    "당일 관객수",
    f"{int(top['audiCnt']):,}명",
)

card2.metric(
    "누적 관객수",
    f"{int(top['audiAcc']):,}명",
)

card3.metric(
    "스크린수",
    f"{int(top['scrnCnt']):,}개",
)


# 13. 전체 영화 표를 표시합니다.
st.subheader("📋 전체 박스오피스")

table = pd.DataFrame({
    "순위": df["rank"].map(lambda value: f"{int(value)}위"),
    "영화명": df.apply(display_movie_name, axis=1),
    "순위 변동": df["rankInten"].map(display_rank_change),
    "개봉일": df["openDt"].fillna("").replace("", "정보 없음"),
    "관객수": df["audiCnt"].map(lambda value: f"{int(value):,}"),
    "누적관객": df["audiAcc"].map(lambda value: f"{int(value):,}"),
    "스크린수": df["scrnCnt"].map(lambda value: f"{int(value):,}"),
})

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
)


# 14. 관객수 상위 5편을 막대그래프로 표시합니다.
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.nlargest(5, "audiCnt")
    .sort_values("audiCnt", ascending=True)
    .copy()
)

# 그래프에서도 누적 관객수가 100만 명을 넘으면 트로피를 표시합니다.
top5["표시명"] = top5.apply(display_movie_name, axis=1)

fig = px.bar(
    top5,
    x="audiCnt",
    y="표시명",
    orientation="h",
    labels={
        "audiCnt": "당일 관객수(명)",
        "표시명": "영화명",
    },
    text="audiCnt",
)

# 막대 끝에 관객수를 쉼표와 함께 표시합니다.
fig.update_traces(
    texttemplate="%{x:,.0f}명",
    textposition="outside",
    cliponaxis=False,
)

fig.update_layout(
    yaxis_title="",
    xaxis_title="당일 관객수(명)",
    xaxis=dict(tickformat=","),
    margin=dict(l=20, r=70, t=20, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# 15. 데이터 출처와 조회 날짜를 표시합니다.
st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 오픈API · "
    f"조회 기준일 {selected_date.isoformat()}"
)
