import sys
import os

# 1つ上の階層（APPVENTURE）をパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.sheets import connect_to_sheets_by_id, get_dataframe, update_dataframe

import streamlit as st
from utils.sheets import connect_to_sheets_by_id, get_dataframe
import pandas as pd


# データ読み込み
spreadsheet_id = st.secrets["spreadsheet_id"]
spreadsheet = connect_to_sheets_by_id(spreadsheet_id)

persons_ws = spreadsheet.worksheet("persons")
groups_ws = spreadsheet.worksheet("groups")
persons_df = get_dataframe(persons_ws)
groups_df = get_dataframe(groups_ws)

st.title("Persons list")

# 検索窓
search = st.text_input("名前で検索")
filtered_df = persons_df[persons_df['name'].str.contains(search, case=False, na=False)]

# グループ辞書を作成（id <-> name 変換用）
group_id_to_name = dict(zip(groups_df["group_id"], groups_df["group_name"]))
groups_name_to_id = dict(zip(groups_df["group_name"], groups_df["group_id"]))

# --- 登録フォーム ---
with st.form("register_form"):
    name = st.text_input("name")
    group_name = st.selectbox("group", groups_df["group_name"])
    submitted = st.form_submit_button("Submit")

    if submitted and name:
        new_id = persons_df["person_id"].max() + 1 if not persons_df.empty else 1
        group_id = groups_name_to_id[group_name]
        new_row = pd.DataFrame([{
            "person_id" : new_id,
            "name" : name,
            "group_id" : group_id
        }])
        persons_df = pd.concat([persons_df, new_row], ignore_index=True)
        update_dataframe(persons_ws, persons_df)
        st.success(f"{name} さんを登録しました")
        st.experimental_return()

# 登録一覧表示
if not persons_df.empty:
    for _, row in persons_df.iterrows():
        col1, col2 = st.columns([3, 1])
        with col1:
            group_name = group_id_to_name.get(row["group_id"],"不明")
            st.write(f"■{row['name']} ({group_name}) ")
        with col2:
            if st.button(f"詳細: {row['name']}", key=row["person_id"]):
                st.session_state["person_id"] = row["person_id"]
                st.switch_page("pages/2_persons_detail.py")
