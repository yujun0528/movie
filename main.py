
# main.py
# 어제의 박스오피스 — KOBIS 일별 박스오피스 대시보드

import datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. 페이지의 제목과 넓이를 설정합니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 2. KOBIS API 주소입니다.
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 3. 한국 시간 기준으로 어제 날짜를 계산합니다.
# 배포 서버가 어느 나라 시간대를 사용하든 한국 날짜를 기준으로 합니다.
KST = ZoneInfo("Asia/Seoul")
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식은 YYYYMMDD입니다.
target_dt = yesterday.strftime("%Y%m%d")


# 4. API에서 박스오피스 데이터를 가져오는 함수입니다.
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(date_str: str, api_key: str) -> dict:
    """KOBIS API에 요청하고 JSON 응답을 반환합니다."""
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str,
        },
        timeout=20,
    )

    # HTTP 4xx 또는 5xx 오류가 발생하면 예외를 발생시킵니다.
    response.raise_for_status()

    # HTTP 200이어도 API 자체 오류가 있을 수 있으므로
    # JSON 내용은 아래에서 별도로 검사합니다.
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            "API 응답을 JSON으로 해석할 수 없습니다."
        ) from exc


# 5. 화면 상단 제목을 표시합니다.
st.title("🎬 어제의 박스오피스")
st.caption(
    f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    "(한국 시간 기준)"
)

st.info(
    "KOBIS의 일별 집계 자료를 조회합니다. "
    "데이터 제공 상황에 따라 조회 결과가 늦게 반영될 수 있습니다."
)


# 6. Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
# 인증키를 소스 코드에 직접 적지 마세요.
try:
    api_key = st.secrets["KOBIS_KEY"]
except (KeyError, FileNotFoundError):
    st.error("KOBIS API 인증키를 찾을 수 없습니다.")
    st.markdown(
        """
        **확인 방법**
        1. Streamlit Cloud에서 앱의 **Settings → Secrets**를 엽니다.
        2. 아래 설정을 추가합니다.
        3. 저장한 뒤 앱을 다시 실행합니다.
        """
    )
    st.code('KOBIS_KEY = "발급받은_인증키"')
    st.stop()

# 인증키가 공백뿐인 경우도 미리 확인합니다.
api_key = str(api_key).strip()

if not api_key:
    st.error("KOBIS_KEY 값이 비어 있습니다.")
    st.info("Streamlit Cloud의 Settings → Secrets에서 인증키를 입력해 주세요.")
    st.stop()


# 7. API를 호출하고 오류를 처리합니다.
try:
    with st.spinner("어제의 박스오피스 데이터를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_dt, api_key)

except requests.exceptions.Timeout:
    st.error("KOBIS API 응답 시간이 초과되었습니다.")
    st.info("네트워크 상태를 확인하고 잠시 후 페이지를 새로고침해 주세요.")
    st.stop()

except requests.exceptions.HTTPError as exc:
    st.error("KOBIS 서버가 HTTP 오류를 반환했습니다.")
    st.caption(f"상세 내용: {exc}")
    st.info("API 주소와 서버 상태를 확인해 주세요.")
    st.stop()

except requests.exceptions.RequestException as exc:
    st.error("KOBIS API 서버에 연결하지 못했습니다.")
    st.caption(f"상세 내용: {exc}")
    st.info("인터넷 연결, API 주소, 서버 상태를 확인해 주세요.")
    st.stop()

except ValueError as exc:
    st.error("KOBIS API 응답을 읽지 못했습니다.")
    st.caption(str(exc))
    st.info("API 응답 형식과 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()


# 8. HTTP 200이어도 faultInfo가 있으면 API 오류입니다.
# 특히 인증키가 잘못되었을 때 이 항목이 반환될 수 있습니다.
if "faultInfo" in data:
    fault = data.get("faultInfo") or {}
    error_code = fault.get("errorCode", "정보 없음")
    error_message = fault.get("message", "오류 메시지가 없습니다.")

    st.error("KOBIS API가 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {error_code}")
    st.write(f"**오류 내용:** {error_message}")
    st.markdown(
        """
        **확인할 사항**
        - Streamlit Cloud의 Secrets에 등록한 `KOBIS_KEY`가 정확한지 확인합니다.
        - 인증키에 불필요한 공백이나 따옴표가 들어가지 않았는지 확인합니다.
        - KOBIS 오픈API 사이트에서 키 발급 및 이용 상태를 확인합니다.
        """
    )
    st.stop()


# 9. 응답에서 영화 목록을 꺼냅니다.
boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error("API 응답에 boxOfficeResult 항목이 없습니다.")
    st.info("KOBIS API의 응답 구조와 서버 상태를 확인해 주세요.")
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

# 목록이 없으면 빈 표나 그래프를 그리지 않고 안내합니다.
if not isinstance(movies, list) or len(movies) == 0:
    st.warning("해당 날짜의 영화 목록이 비어 있습니다.")
    st.markdown(
        """
        **확인할 사항**
        - KOBIS에서 해당 날짜의 일별 박스오피스 집계가 완료되었는지 확인합니다.
        - KOBIS 오픈API 사이트에서 같은 날짜를 직접 조회해 봅니다.
        - 응답에 오류 정보가 있는지 확인합니다.
        - 날짜가 맞는지 확인합니다. 이 앱은 한국 시간 기준 어제를 조회합니다.
        """
    )
    st.stop()


# 10. 문자열로 받은 숫자 데이터를 숫자형으로 변환합니다.
df = pd.DataFrame(movies)

# API 응답에 필요한 항목이 있는지 확인합니다.
required_columns = [
    "rank",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    st.error("API 응답에 필요한 데이터 항목이 없습니다.")
    st.write("누락된 항목:", ", ".join(missing_columns))
    st.info("KOBIS API 응답 형식이 변경되었는지 확인해 주세요.")
    st.stop()

# 숫자 문자열을 숫자로 바꿔야 정렬과 그래프가 올바르게 동작합니다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 숫자로 변환할 수 없는 행은 제외하고 순위순으로 정렬합니다.
df = df.dropna(subset=["rank", "audiCnt", "audiAcc", "scrnCnt"])
df = df.sort_values("rank").reset_index(drop=True)

if df.empty:
    st.warning("표시할 수 있는 영화 데이터가 없습니다.")
    st.info("KOBIS 응답의 숫자 항목이 올바른지 확인해 주세요.")
    st.stop()


# 11. 1위 영화의 지표 카드 세 장을 크게 표시합니다.
top = df.iloc[0]

st.subheader(f"🥇 일별 박스오피스 1위: {top['movieNm']}")
st.caption(f"개봉일: {top['openDt'] or '정보 없음'}")

card1, card2, card3 = st.columns(3)

card1.metric(
    label="어제 관객수",
    value=f"{int(top['audiCnt']):,}명",
)

card2.metric(
    label="누적 관객수",
    value=f"{int(top['audiAcc']):,}명",
)

card3.metric(
    label="스크린수",
    value=f"{int(top['scrnCnt']):,}개",
)


# 12. 전체 영화의 순위표를 표시합니다.
st.subheader("📋 어제의 전체 박스오피스")

table = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

# 화면에 표시할 열 이름을 한국어로 바꿉니다.
table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 날짜가 없는 경우에는 빈칸으로 표시합니다.
table["개봉일"] = table["개봉일"].fillna("")

# 천 단위 쉼표를 적용해 숫자를 읽기 쉽게 표시합니다.
for col in ["관객수", "누적관객", "스크린수"]:
    table[col] = table[col].map(lambda value: f"{int(value):,}")

table["순위"] = table["순위"].map(lambda value: f"{int(value)}위")

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
)


# 13. 관객수가 많은 상위 5편을 막대그래프로 표시합니다.
st.subheader("📊 관객수 상위 5편")

top5 = df.nlargest(5, "audiCnt").sort_values(
    "audiCnt", ascending=True
).copy()

# 관객수 순서대로 막대가 표시되도록 가로 막대그래프를 사용합니다.
fig = px.bar(
    top5,
    x="audiCnt",
    y="movieNm",
    orientation="h",
    labels={
        "audiCnt": "어제 관객수(명)",
        "movieNm": "영화명",
    },
    text="audiCnt",
)

# 막대 끝에 관객수를 천 단위 쉼표로 표시합니다.
fig.update_traces(
    texttemplate="%{x:,.0f}명",
    textposition="outside",
    cliponaxis=False,
)

fig.update_layout(
    yaxis_title="",
    xaxis_title="어제 관객수(명)",
    xaxis=dict(tickformat=","),
    margin=dict(l=20, r=70, t=20, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# 14. 데이터 출처를 표시합니다.
st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 오픈API · "
    f"조회 기준일 {yesterday.isoformat()}"
)
