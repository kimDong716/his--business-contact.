import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="영업 관리 시스템", layout="wide")

# --- 구글 시트 연결 ---
# Secrets에 등록한 설정을 자동으로 불러옵니다.
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jtSmKfMn4nuJxk5JPQmbkMhP4FrXpD6mD7FsoEEmKtM/edit?gid=0#gid=0"

@st.cache_data(ttl=5)
def load_data(worksheet_id):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=str(worksheet_id))
        if df.empty: return pd.DataFrame()
        
        # 제목줄(Header) 찾기 강화: 데이터가 있는 첫 20행을 뒤짐
        header_idx = 0
        for i in range(min(len(df), 50)):
            row_values = df.iloc[i].astype(str).tolist()
            if any(k in "".join(row_values) for k in ['업체명', '상호', '일자', '잔고']):
                header_idx = i
                break
        
        df.columns = df.iloc[header_idx].astype(str).str.strip()
        df = df.iloc[header_idx+1:].reset_index(drop=True)
        return df.astype(str).replace(['nan', 'None', 'NaN', 'NaT'], '')
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

# 데이터 저장 함수
def save_data(df, worksheet_id):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=str(worksheet_id), data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# 데이터 로드
df_summary = load_data("621616384")
df_history = load_data("0")

# 컬럼 찾기 함수 (에러 방지용)
def find_col(df, keywords, default_name="Unknown"):
    for col in df.columns:
        if any(k in str(col) for k in keywords):
            return str(col)
    return None

# --- 메뉴 구성 ---
menu = st.sidebar.radio("메뉴 선택", ["🔍 거래처 검색", "📊 전체 현황", "✍️ 거래 내역 입력", "⚙️ 거래처 관리"])

if menu == "🔍 거래처 검색":
    st.title("🔍 거래처 상세 정보")
    name_col = find_col(df_summary, ['업체명', '상호'])
    
    if name_col and not df_summary.empty:
        # 검색 기능 추가
        search_q = st.text_input("업체명 검색")
        filtered_list = df_summary[df_summary[name_col].str.contains(search_q)] if search_q else df_summary
        
        target = st.selectbox("업체를 선택하세요", ["선택하세요"] + list(filtered_list[name_col].unique()))
        
        if target != "선택하세요":
            info = df_summary[df_summary[name_col] == target].iloc[0]
            c1, c2, c3 = st.columns(3)
            
            # 정보 표시 (컬럼 유연하게 매칭)
            mgr_col = find_col(df_summary, ['담당자', '대표'])
            tel_col = find_col(df_summary, ['연락처', '전화', '핸드폰'])
            item_col = find_col(df_summary, ['내용', '품목', '거래내용'])
            
            c1.metric("담당자", info.get(mgr_col, "정보없음") if mgr_col else "정보없음")
            c2.metric("연락처", info.get(tel_col, "정보없음") if tel_col else "정보없음")
            c3.info(f"**거래내용:** {info.get(item_col, '정보없음') if item_col else '정보없음'}")
            
            st.divider()
            st.write("#### 📜 최근 거래 이력")
            h_name_col = find_col(df_history, ['업체명', '상호'])
            if h_name_col:
                st.dataframe(df_history[df_history[h_name_col] == target], use_container_width=True)
    else:
        st.error("시트에서 '업체명' 컬럼을 찾을 수 없습니다. 시트의 제목줄을 확인해주세요.")

elif menu == "📊 전체 현황":
    st.title("📊 전체 거래처 리스트")
    st.dataframe(df_summary, use_container_width=True)

elif menu == "✍️ 거래 내역 입력":
    st.title("✍️ 거래 내역 기록")
    name_col = find_col(df_summary, ['업체명', '상호'])
    if name_col:
        with st.form("history_form"):
            c1, c2 = st.columns(2)
            sel_name = c1.selectbox("업체명", df_summary[name_col].unique())
            sel_date = c2.date_input("날짜", datetime.now())
            sel_price = c1.number_input("금액", step=1000)
            sel_memo = c2.text_input("비고")
            
            if st.form_submit_button("시트에 저장하기"):
                new_row = pd.DataFrame([[sel_date.strftime('%Y-%m-%d'), sel_name, sel_price, sel_memo]], 
                                        columns=['일자', '업체명', '금액', '비고'])
                updated_df = pd.concat([df_history, new_row], ignore_index=True)
                if save_data(updated_df, "0"):
                    st.success("성공적으로 저장되었습니다!")
                    st.balloons()
    else:
        st.error("업체 리스트를 불러올 수 없어 입력을 진행할 수 없습니다.")

elif menu == "⚙️ 거래처 관리":
    st.title("⚙️ 거래처 정보 수정 및 종료")
    st.info("신규 거래처 등록 및 수정 기능을 준비 중입니다.")
