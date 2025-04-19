import os
import requests
import openai
import streamlit as st
from newspaper import Article
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials

# === OpenAI APIキー ===
OPENAI_API_KEY = st.secrets["openai_api_key"]
NEWS_API_KEY = st.secrets["news_api_key"]
WEATHER_API_KEY = st.secrets["weather_api_key"]

# === Google Sheets 初期化（secrets.toml 対応） ===
def init_google_sheets():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scopes)
    client = gspread.authorize(creds)

    SPREADSHEET_ID = st.secrets["spreadsheet_id"]
    return {
        "topics": client.open_by_key(SPREADSHEET_ID).worksheet("topics"),
        "groups": client.open_by_key(SPREADSHEET_ID).worksheet("groups"),
        "persons": client.open_by_key(SPREADSHEET_ID).worksheet("persons"),
        "talk_logs": client.open_by_key(SPREADSHEET_ID).worksheet("talk_logs"),
    }

def get_dataframe(worksheet):
    return pd.DataFrame(worksheet.get_all_records())

def update_dataframe(worksheet,df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# 雑談ネタ保存
def append_to_google_sheet(mode, topics, sheet):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [line.strip() for line in topics.strip().split("\n") if line.strip()]
    for line in lines:
        try:
            title, content = line.split(":", 1)
            topic_id = str(uuid.uuid4())
            row = [topic_id, now, title.strip(), mode, content.strip()]
            sheet.append_row(row)
        except ValueError:
            continue

# 雑談ネタ取得
def load_topics_from_sheet(sheet):
    records = sheet.get_all_values()[1:]
    topics = {}
    for row in records:
        _, _, title, _, content = row[:5]
        topics[title] = content
    return topics

# 天気予報詳細（AM/PM降水確率＋アイコン）
def get_weather_forecast(city="Tokyo"):
    try:
        url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={city}&lang=ja&days=1"
        res = requests.get(url)
        data = res.json()

        condition = data["current"]["condition"]["text"]
        hours = data["forecast"]["forecastday"][0]["hour"]

        am_rain = hours[9]["chance_of_rain"]
        pm_rain = hours[15]["chance_of_rain"]
        icon_url = "https:" + data["current"]["condition"]["icon"]

        return condition, am_rain, pm_rain, icon_url
    except Exception as e:
        return "取得エラー", "-", "-", ""

# ニュース取得
def get_news_full():
    try:
        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
        res = requests.get(url)
        data = res.json()
        return data.get("articles", [])[:5]
    except Exception as e:
        return []

# GPT翻訳（ニュース日本語化）
def translate_news_to_japanese(client, title, description):
    prompt = (
        f"以下の英語ニュースのタイトルと概要を自然な日本語に翻訳してください：\n\n"
        f"Title: {title}\nDescription: {description}"
    )
    return generate_topic(client, prompt)

# GPT出力
def generate_topic(client, prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ChatGPT生成エラー: {e}"

# ニュース本文取得
def get_article_text(url):
    try:
        article = Article(url, language='en')
        article.download()
        article.parse()
        return article.text.strip()
    except Exception as e:
        return f"（本文取得失敗: {e}）"

# === 雑談ネタ生成 ===
def generate_weather_only_topic(client, city="Tokyo"):
    weather = get_weather_forecast(city)
    prompt = (
        f"今日の天気は「{weather}」です。\n"
        f"この天気をテーマに、日常会話で使える雑談ネタを3つ提案してください。\n"
        f"それぞれ以下の形式で出力してください：\n"
        f"---\nタイトル: ○○\nカテゴリ: ○○\n内容: ○○\n---"
    )
    return generate_topic(client, prompt)

def generate_news_only_topic(client):
    news = get_news_full()
    if not news:
        return "ニュース情報が取得できませんでした。"
    article = news[0]
    title, description, url = article.get("title", ""), article.get("description", ""), article.get("url", "")
    body = get_article_text(url) or description
    prompt = (
        f"以下のニュースをもとに雑談ネタを3つ作成してください。\n"
        f"■タイトル: {title}\n■本文: {body[:500]}\n"
        f"それぞれ以下の形式で出力してください：\n"
        f"---\nタイトル: ○○\nカテゴリ: ○○\n内容: ○○\n---"
    )
    return generate_topic(client, prompt)

# ホーム画面（翻訳ニュース＋天気詳細）
def show_home_page(client):
    st.title("🗂 雑談管理アプリ")
    st.button("🟥 他のネタを探す", use_container_width=True)

    news_list = get_news_full()
    if news_list:
        article = random.choice(news_list)
        title = article.get("title", "")
        description = article.get("description", "")
        ja_news = translate_news_to_japanese(client, title, description)
        st.markdown("### 📰 今日のランダムニュース（日本語）")
        st.info(ja_news)
    else:
        st.warning("ニュース情報を取得できませんでした。")

    cities = ["Tokyo", "Osaka", "Nagoya", "Sapporo", "Fukuoka"]
    city = random.choice(cities)
    condition, am_rain, pm_rain, icon_url = get_weather_forecast(city)
    st.markdown(f"### 🌤 今日の天気：{city}")
    if icon_url:
        st.image(icon_url, width=64)
    st.success(f"現在の天気は「{condition}」です")
    st.info(f"☔ 降水確率：午前 {am_rain}% ／ 午後 {pm_rain}%")

# TOPIC一覧画面
def show_topic_list_page(sheet):
    st.title("📝 TOPIC 一覧")
    topics = load_topics_from_sheet(sheet)
    people = ["たっちーさん", "さんこんさん", "りじちょー", "List item 1", "List item 2"]
    for title, content in topics.items():
        st.markdown(f"#### 💡 {title}")
        st.markdown(f"{content}")
        st.markdown("**👥 話した人チェック**")
        for person in people:
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.write(f"👤 {person}")
            with col2:
                st.checkbox("", key=f"{title}_{person}")
        st.markdown("---")

# === topicsシートに保存 ===
def save_generated_topics(sheet, topics_text):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entries = [e.strip() for e in topics_text.strip().split("---") if e.strip()]
    existing_ids = sheet.col_values(1)[1:]
    ids = [int(x) for x in existing_ids if x.isdigit()]
    current_id = max(ids) if ids else 0
    new_ids = []

    for entry in entries:
        lines = [l.strip() for l in entry.strip().split("\n") if ":" in l]
        try:
            title = next(l.split(":",1)[1].strip() for l in lines if l.startswith("タイトル"))
            category = next(l.split(":",1)[1].strip() for l in lines if l.startswith("カテゴリ"))
            content = next(l.split(":",1)[1].strip() for l in lines if l.startswith("内容"))
            current_id += 1
            sheet.append_row([str(current_id), now, title, category, content])
            new_ids.append(current_id)
        except Exception as e:
            print(f"保存失敗: {e}\n内容: {entry}")
            continue
    return new_ids

# === talk_logsに記録 ===
def log_talk(sheet, topic_ids, person_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for topic_id in topic_ids:
        sheet.append_row([str(topic_id), str(person_id)])

# === person_listページ ===
def show_persons_list_page(sheets):
    persons_df = get_dataframe(sheets["persons"])
    groups_df = get_dataframe(sheets["groups"])

    st.title("🧑‍🤝‍🧑 話す人一覧")

    search = st.text_input("名前で検索")
    filtered_df = persons_df[persons_df['name'].str.contains(search, case=False, na=False)]

    
    groups_name_to_id = dict(zip(groups_df["group_name"], groups_df["group_id"]))
    group_id_to_name = dict(zip(groups_df["group_id"], groups_df["group_name"]))
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
        persons_ws = sheets["persons"]
        update_dataframe(persons_ws, persons_df)
        st.success(f"{name} さんを登録しました")
        st.rerun()

    for _, row in persons_df.iterrows():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"{row['name']}（{group_id_to_name.get(row['group_id'], '不明')}）")
        with col2:
            if st.button("詳細を見る", key=f"detail_{row['person_id']}"):
                st.session_state["selected_person_id"] = row["person_id"]
                st.session_state["page"] = "person_detail"
                st.rerun()

def show_persons_detail_page(sheets):
    persons_df = get_dataframe(sheets["persons"])
    topics_df = get_dataframe(sheets["topics"])
    talk_log_df = get_dataframe(sheets["talk_logs"])

    person_id = st.session_state.get("selected_person_id")
    if person_id is None:
        st.warning("話す相手が選ばれていません。")
        return

    person_name = persons_df[persons_df["person_id"] == person_id]["name"].values[0]
    st.title(f"🗣 {person_name} さんのトピック管理")

    # ✅ ここから下、全部インデントしてください！
    person_logs = talk_log_df[talk_log_df["person_id"] == person_id]
    merged_df = pd.merge(person_logs, topics_df, on="topic_id")
    merged_df["talked_flag"] = merged_df["talked"].isin(["TRUE", True])
    merged_df = merged_df.sort_values("talked_flag")

    for _, row in merged_df.iterrows():
        is_talked = row["talked_flag"]
        bg_color = "#eeeeee" if is_talked else "#ffffff"

        new_state = st.checkbox(
            f"{row['title']}",
            value=is_talked,
            key=f"{row['topic_id']}",
            help="チェックすると話したことになります 💬"
        )

        st.markdown(
            f"<div style='background-color:{bg_color}; height:1px; margin-bottom:8px;'></div>",
            unsafe_allow_html=True
        )

        if new_state != is_talked:
            talk_log_df.loc[
                (talk_log_df["topic_id"] == row["topic_id"]) &
                (talk_log_df["person_id"] == person_id),
                "talked"
            ] = "TRUE" if new_state else "FALSE"

    if st.button("保存する"):
        update_dataframe(sheets["talk_logs"], talk_log_df)
        st.success("保存しました！")

# === Streamlit UI ===
def main():
    if "page" not in st.session_state:
        st.session_state.page = "ホーム"

    if st.session_state.page != "person_detail":
        selected = st.sidebar.selectbox("ページを選択", ["ホーム", "TOPIC一覧", "ネタ生成", "話す人一覧"])
        st.session_state.page = selected

    page = st.session_state.page

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
    except Exception as e:
        st.error(f"OpenAI初期化失敗: {e}")
        return

    sheet = None
    try:
        sheets = init_google_sheets()

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
     
    except Exception as e:
        st.error("初期化エラー")
        st.write(e)
        return  
    except Exception as e:
        st.warning(f"Googleスプレッドシートに接続できませんでした: {e}")
        

    if page == "ホーム":
        show_home_page(client)
    elif page == "TOPIC一覧":
       if sheets and "topics" in sheets:
            show_topic_list_page(sheets["topics"])
       else:
            st.error("スプレッドシートが読み込めませんでした。")
    elif page == "ネタ生成":
        st.title("🎙️ 雑談ネタ生成")
         # グループと人物選択
        group_data = sheets["groups"].get_all_records()
        group_names = [g["group_name"] for g in group_data]
        selected_group_name = st.selectbox("対象グループを選択：", group_names)
        group = next(g for g in group_data if g["group_name"] == selected_group_name)
        persons = sheets["persons"].get_all_records()
        group_persons = [p for p in persons if str(p["group_id"]) == str(group["group_id"])]
        person_names = [p["name"] for p in group_persons]
        selected_person_name = st.selectbox("話した相手を選択：", person_names)
        person = next(p for p in group_persons if p["name"] == selected_person_name)

        mode = st.radio("ネタの種類：", ("天気ネタ", "ニュースネタ"))
        city = st.text_input("都市名（天気ネタ用）", "Tokyo")

        if st.button("🧠 雑談ネタを生成"):
            with st.spinner("生成中..."):
                result = generate_weather_only_topic(client, city) if mode.startswith("天気") else generate_news_only_topic(client)
            st.markdown("### ✅ 生成された雑談ネタ")
            st.markdown(result.replace("\n", "  \n"))

            try:
                topic_ids = save_generated_topics(sheets["topics"], result)
                log_talk(sheets["talk_logs"], topic_ids, person["person_id"])
                st.success("✅ topics と talk_logs に保存しました！")
            except Exception as e:
                st.error("保存エラー")
                st.write(e)

    elif page == "話す人一覧":
        if sheets:
            show_persons_list_page(sheets)  # sheets辞書ごと渡す
        else:
            st.error("読み込み失敗")

    elif page == "person_detail":
        if sheets:
            show_persons_detail_page(sheets)
        else:
            st.error("読み込み失敗")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("アプリ実行エラー")
        st.write(e)
