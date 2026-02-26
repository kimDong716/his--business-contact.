import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="영업/미수금 통합 관리 시스템", layout="wide")

# --- 2. 구글 시트 연결 설정 ---
# 시트 URL (본인의 시트 주소)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YD0AolMY-Ed6vNogf3L04OuaLV3RFLbJxHEd56UISzE/edit#gid=621616384"
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 로드 함수 (캐시 적용)
@st.cache_data(ttl=5) # 5초 후 자동 갱신
def load_data(worksheet_id):
    df = conn.read(spreadsheet=SHEET_URL, worksheet=str(worksheet_id))
    # 제목줄 자동 찾기
    header_idx = 0
    for i in range(min(len(df), 10)):
        if df.iloc[i].notna().any():
            header_idx = i
            break
    df.columns = df.iloc[header_idx].astype(str).str.strip()
    df = df.iloc[header_idx+1:].reset_index(drop=True)
    return df.fillna('')

# 데이터 저장 함수 (핵심!)
def save_to_sheet(df, worksheet_id):
    conn.update(spreadsheet=SHEET_URL, worksheet=str(worksheet_id), data=df)
    st.cache_data.clear() # 저장 후 화면 갱신을 위해 캐시 삭제

# 데이터 로드
df_summary = load_data("621616384") # 요약/업체 시트
df_history = load_data("0")         # 거래 내역 시트

# 유틸리티: 컬럼명 찾기
def find_col(df, keywords):
    for col in df.columns:
        if any(k in str(col) for k in keywords): return str(col)
    return None

# --- 3. 사이드바 메뉴 ---
menu = st.sidebar.radio("메뉴 선택", ["🔍 거래처 검색", "📊 전체 현황", "✍️ 거래 내역 입력", "⚙️ 거래처 관리"])

# --- 4. 메뉴별 기능 구현 ---

# [메뉴 1] 거래처 검색 및 상세
if menu == "🔍 거래처 검색":
    st.title("🔍 거래처 상세 정보")
    name_col = find_col(df_summary, ['업체명', '상호'])
    status_col = find_col(df_summary, ['상태', '비고'])
    
    # 종료 업체 제외 리스트
    active_list = df_summary.copy()
    if status_col:
        active_list = active_list[~active_list[status_col].str.contains('종료', na=False)]
    
    target = st.selectbox("업체를 선택하세요", ["선택하세요"] + list(active_list[name_col].unique()))
    
    if target != "선택하세요":
        info = active_list[active_list[name_col] == target].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("담당자", info.get(find_col(df_summary, ['담당자']), '정보없음'))
        c2.metric("연락처", info.get(find_col(df_summary, ['연락처', '전화']), '정보없음'))
        c3.metric("주요내용", info.get(find_col(df_summary, ['내용', '품목']), '정보없음'))
        
        st.write("#### 📅 월별 거래 요약")
        # 여기서 History 데이터를 필터링해서 보여줍니다.
        hist_name_col = find_col(df_history, ['업체명', '상호'])
        if hist_name_col:
            personal_hist = df_history[df_history[hist_name_col] == target]
            st.dataframe(personal_hist, use_container_width=True)

# [메뉴 2] 전체 현황
elif menu == "📊 전체 현황":
    st.title("📊 전체 거래처 현황")
    st.dataframe(df_summary, use_container_width=True)

# [메뉴 3] 거래 내역 입력 (쓰기 기능)
elif menu == "✍️ 거래 내역 입력":
    st.title("✍️ 새로운 거래 입력")
    with st.form("input_form"):
        name_col = find_col(df_summary, ['업체명', '상호'])
        target_name = st.selectbox("업체 선택", df_summary[name_col].unique())
        date = st.date_input("일자", datetime.now())
        amount = st.number_input("금액", step=1000)
        memo = st.text_input("적요")
        
        if st.form_submit_button("시트에 저장"):
            # 새 데이터 생성
            new_data = pd.DataFrame([[date.strftime('%Y-%m-%d'), target_name, amount, memo]], 
                                    columns=['일자', '업체명', '금액', '비고'])
            # 기존 데이터와 병합
            updated_history = pd.concat([df_history, new_data], ignore_index=True)
            # 저장 실행
            save_to_sheet(updated_history, "0")
            st.success("✅ 구글 시트에 성공적으로 저장되었습니다!")
            st.balloons()

# [메뉴 4] 거래처 관리 (수정/종료)
elif menu == "⚙️ 거래처 관리":
    st.title("⚙️ 거래처 정보 수정/종료")
    tab1, tab2 = st.tabs(["🆕 신규 등록", "✏️ 수정 및 종료"])
    
    with tab1: # 신규 등록
        with st.form("add_client"):
            new_name = st.text_input("신규 업체명")
            new_manager = st.text_input("담당자")
            if st.form_submit_button("업체 추가"):
                new_client = pd.DataFrame([[new_name, new_manager, '거래중']], 
                                          columns=['업체명', '담당자', '상태'])
                updated_summary = pd.concat([df_summary, new_client], ignore_index=True)
                save_to_sheet(updated_summary, "621616384")
                st.success(f"{new_name} 등록 완료!")

    with tab2: # 수정 및 종료
        name_col = find_col(df_summary, ['업체명', '상호'])
        edit_target = st.selectbox("수정할 업체", df_summary[name_col].unique())
        if st.button("해당 업체 거래 종료 처리"):
            # '상태' 컬럼 찾아서 '종료'로 변경
            status_col = find_col(df_summary, ['상태', '비고'])
            if status_col:
                df_summary.loc[df_summary[name_col] == edit_target, status_col] = '종료'
                save_to_sheet(df_summary, "621616384")
                st.warning(f"{edit_target} 거래 종료 처리됨")
