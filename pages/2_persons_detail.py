import sys
import os

# 1つ上の階層（APPVENTURE）をパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.sheets import connect_to_sheets_by_id, get_dataframe

import streamlit as st
import pandas as pd
from utils.sheets import connect_to_sheets_by_id, get_dataframe, update_dataframe

# URLパラメータから person_id を取得
params = st.query_params
if 'person_id' not in params:
    st.error("相手が指定されていません")
    st.stop()
    
person_id = int(params["person_id"][0])

# データ読み込み
spreadsheet_id = st.secrets["spreadsheet_id"]
spreadsheet = connect_to_sheets_by_id(spreadsheet_id)
topics_df = get_dataframe(spreadsheet.worksheet("topics"))
talk_log_df = get_dataframe(spreadsheet.worksheet("talk_log"))
persons_df = get_dataframe(spreadsheet.worksheet("persons"))

# 該当者名
person_name = persons_df[persons_df["person_id"] == person_id]["name"].values[0]
st.title(f"{person_name} さんの話題管理")

# トピック結合
person_logs = talk_log_df[talk_log_df["person_id"]==person_id]
merged_df = pd.merge(person_logs,topics_df, on="topic_id")

# チェックUIと色付き表示
for idx, row in merged_df.iterrows():
    is_talked = row["talked"] in ["TRUE",True]
    bg_color = "#f0f0f0" if is_talked else "#ffffff"

    st.markdown(
         f"""
        <div style='background-color:{bg_color}; padding:10px; border-radius:8px; margin-bottom:8px;'>
            <strong>{row['title']}</strong><br>
        </div>
        """,
        unsafe_allow_html=True
    )

    new_state = st.checkbox("話した？", value=is_talked, key=f"{row['topic_id']}")
    if new_state != is_talked:
        talk_log_df.loc[
            (talk_log_df["topic_id"] == row["topic_id"]) &
            (talk_log_df["person_id"] == person_id),
            "talked"
        ] = "TRUE" if new_state else "FALSE"

# 保存ボタン
if st.button("保存する"):
    update_dataframe(spreadsheet.worksheet("talk_log"), talk_log_df)
    st.success("保存しました！")