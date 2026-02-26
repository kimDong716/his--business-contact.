import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="영업 관리 시스템", layout="wide")

# --- 구글 시트 연결 ---
conn = st.connection("gsheets", type=GSheetsConnection)
# URL 확인: 마지막에 gid=0 부분을 유지하거나 필요에 따라 수정
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jtSmKfMn4nuJxk5JPQmbkMhP4FrXpD6mD7FsoEEmKtM/edit#gid=0"

@st.cache_data(ttl=5)
def load_data(worksheet_id):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=str(worksheet_id))
        if df.empty: return pd.DataFrame()
        
        # 헤더 찾기 (최대 50행 검색)
        header_idx = 0
        for i in range(min(len(df), 50)):
            row_values = df.iloc[i].astype(str).tolist()
            if any(k in "".join(row_values) for k in ['업체명', '상호', '일자', '잔고']):
                header_idx = i
                break
        
        df.columns = df.iloc[header_idx].astype(str).str.strip()
        df = df.iloc[header_idx+1:].reset_index(drop=True)
        # 데이터 정제 (공백 제거 및 결측치 처리)
        return df.astype(str).replace(['nan', 'None', 'NaN', 'NaT', ''], '')
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

def save_data(df, worksheet_id):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=str(worksheet_id), data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"저장 실패 (권한이나 시트 ID를 확인하세요): {e}")
        return False

# 데이터 로드
df_summary = load_data("621616384") # 업체 정보 시트 ID
df_history = load_data("0")         # 거래 내역 시트 ID (보통 첫번째 탭은 0)

def find_col(df, keywords):
    for col in df.columns:
        if any(k in str(col) for k in keywords):
            return str(col)
    return None

# --- 메뉴 구성 ---
menu = st.sidebar.radio("메뉴 선택", ["🔍 거래처 검색", "📊 전체 현황", "✍️ 거래 내역 입력", "⚙️ 거래처 관리"])

# 1. 거래처 검색
if menu == "🔍 거래처 검색":
    st.title("🔍 거래처 상세 정보")
    name_col = find_col(df_summary, ['업체명', '상호'])
    status_col = find_col(df_summary, ['상태', '구분', '비고'])
    
    if name_col:
        # '종료'된 업체 제외 옵션
        active_df = df_summary.copy()
        if status_col:
            active_df = active_df[~active_df[status_col].str.contains('종료|중단', na=False)]
            
        search_q = st.text_input("업체명 또는 전화번호 검색")
        target_list = active_df[name_col].unique()
        target = st.selectbox("업체를 선택하세요", ["선택하세요"] + list(target_list))
        
        if target != "선택하세요":
            info = df_summary[df_summary[name_col] == target].iloc[0]
            c1, c2, c3 = st.columns(3)
            
            mgr_col = find_col(df_summary, ['담당자', '대표'])
            tel_col = find_col(df_summary, ['연락처', '전화'])
            item_col = find_col(df_summary, ['내용', '품목'])
            
            c1.metric("담당자", info.get(mgr_col, "정보없음"))
            c2.metric("연락처", info.get(tel_col, "정보없음"))
            c3.info(f"**거래내용:**\n{info.get(item_col, '정보없음')}")
            
            st.divider()
            st.write(f"#### 📜 {target} 최근 거래 이력")
            h_name_col = find_col(df_history, ['업체명', '상호'])
            if h_name_col:
                personal_hist = df_history[df_history[h_name_col] == target]
                st.dataframe(personal_hist, use_container_width=True)

# 2. 전체 현황
elif menu == "📊 전체 현황":
    st.title("📊 전체 거래처 리스트")
    st.dataframe(df_summary, use_container_width=True)

# 3. 거래 내역 입력
elif menu == "✍️ 거래 내역 입력":
    st.title("✍️ 거래 내역 기록")
    name_col = find_col(df_summary, ['업체명', '상호'])
    if name_col:
        with st.form("history_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sel_name = c1.selectbox("업체명", df_summary[name_col].unique())
            sel_date = c2.date_input("날짜", datetime.now())
            sel_price = c1.number_input("금액", step=1000)
            sel_memo = c2.text_input("비고 (적요)")
            
            if st.form_submit_button("시트에 저장하기"):
                # 실제 시트의 컬럼 순서와 이름을 확인하여 맞춰야 함
                new_row = pd.DataFrame([[sel_date.strftime('%Y-%m-%d'), sel_name, sel_price, sel_memo]], 
                                        columns=df_history.columns[:4]) # 예시로 처음 4개 컬럼 사용
                updated_df = pd.concat([df_history, new_row], ignore_index=True)
                if save_data(updated_df, "0"):
                    st.success(f"{sel_name} 내역 저장 완료!")
                    st.balloons()

# 4. 거래처 관리 (신규/수정/종료)
elif menu == "⚙️ 거래처 관리":
    st.title("⚙️ 거래처 정보 관리")
    t1, t2 = st.tabs(["🆕 신규 거래처 등록", "✏️ 수정 및 종료"])
    
    with t1:
        with st.form("new_client_form", clear_on_submit=True):
            st.write("새로운 거래처 정보를 입력하세요.")
            n_name = st.text_input("업체명 (필수)*")
            n_mgr = st.text_input("담당자")
            n_tel = st.text_input("연락처")
            n_item = st.text_area("주요 거래 내용")
            
            if st.form_submit_button("등록하기"):
                if n_name:
                    # Summary 시트 컬럼 구조에 맞춰 빈 데이터프레임 생성
                    new_client = pd.DataFrame([[n_name, n_mgr, n_tel, n_item, '거래중']], 
                                              columns=df_summary.columns[:5])
                    updated_summary = pd.concat([df_summary, new_client], ignore_index=True)
                    if save_data(updated_summary, "621616384"):
                        st.success(f"{n_name} 등록 성공!")
                else:
                    st.error("업체명은 필수입니다.")

    with t2:
        name_col = find_col(df_summary, ['업체명', '상호'])
        if name_col:
            edit_name = st.selectbox("수정할 업체 선택", df_summary[name_col].unique())
            target_row = df_summary[df_summary[name_col] == edit_name]
            
            with st.form("edit_form"):
                st.write(f"**{edit_name}**의 정보를 수정합니다.")
                # 기존 데이터 가져오기 (컬럼 인덱스는 시트 구조에 따라 조정 필요)
                u_status = st.checkbox("거래 종료 (체크 시 검색 리스트에서 숨김)", 
                                       value=('종료' in str(target_row.values[0])))
                
                if st.form_submit_button("정보 업데이트"):
                    status_col = find_col(df_summary, ['상태', '비고'])
                    if status_col:
                        df_summary.loc[df_summary[name_col] == edit_name, status_col] = '종료' if u_status else '거래중'
                        if save_data(df_summary, "621616384"):
                            st.success("정보가 변경되었습니다.")
