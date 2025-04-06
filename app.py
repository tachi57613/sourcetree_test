import requests  # リクエスト機能をインポート
from bs4 import BeautifulSoup  # HTML解析機能をインポート
import pandas as pd  # データフレームを扱うpandasをインポート
import gspread  # スプレッドシートのデータを扱うライブラリをインポート
from google.oauth2.service_account import Credentials  # スプレッドシートの認証機能をインポート
from gspread_dataframe import set_with_dataframe  # データフレームとスプレッドシートを連携する機能をインポート
import time  # 実行待機のための機能をインポート
import schedule  # 定期実行するための機能をインポート

# 定期実行する内容
def job():
    REQUEST_URL = 'https://travel.rakuten.co.jp/yado/okinawa/nahashi.html'  # リクエストのアクセス先をREQUEST_URLに代入
    res = requests.get(REQUEST_URL)  # 楽天トラベルにアクセスし、そのデータをresに代入
    res.encoding = 'utf-8'  # 文字化けしないように文字コードをutf-8に指定
    soup = BeautifulSoup(res.text, "html.parser")  # 取得したHTMLを解析して、soupに代入

    # ホテル情報のセクションを取得
    hotel_section_from_html = soup.select('ul#htlBox li.htl-list-card')

    # 必要なホテル情報のみを抽出
    hotel_section = []
    for hs in hotel_section_from_html:
        a = hs.select_one('p.area')
        if a is not None:
            hotel_section.append(hs)  # 'p.area'が存在するセクションのみ追加

    # データ格納用のリストを用意
    hotelName = []  # ホテル名を格納する空配列を用意します。
    hotelMinCharge = []  # ホテルの料金を格納する空配列を用意します。
    reviewAverage = []  # ホテル評価を格納する空配列を用意します。
    hotel_locate = []  # ホテル住所を格納する空配列を用意します。

    # hotel_sectionから情報を抽出
    for hs in hotel_section:
        # ホテル名を取得
        hs1_element = hs.select_one('h2 a')
        hs1 = hs1_element.text.strip() if hs1_element else None

        # 最低料金を取得
        hs2_element = hs.select_one('span.htlLowprice')
        if hs2_element:
            hs2_text = hs2_element.text.split("消費税込")[0]
            hs2_text = hs2_text.replace("円〜", "").replace(",", "").replace("最安値", "")
            try:
                hs2 = int(hs2_text.strip())
            except ValueError:
                hs2 = None
        else:
            hs2 = None

        # レビュー平均を取得
        hs3_element = hs.select_one('p.cstmrEvl a')
        if hs3_element:
            hs3_text = hs3_element.text.split("（")[0].replace("\n", "")
            try:
                hs3 = float(hs3_text.strip())
            except ValueError:
                hs3 = None
        else:
            hs3 = None

        # 住所を取得
        hs4_element = hs.select_one('p.htlAccess')
        if hs4_element:
            hs4 = hs4_element.text.strip()
            hs4 = hs4.replace("\n", "").replace(" ", "").replace("[地図を見る]", "").replace("　", "")
        else:
            hs4 = None

        # リストに追加
        hotelName.append(hs1)
        hotelMinCharge.append(hs2)
        reviewAverage.append(hs3)
        hotel_locate.append(hs4)

    # pandasのデータフレームに使うデータを定義します。
    data_list = {
        "hotelName": hotelName,
        "hotelMinCharge": hotelMinCharge,
        "reviewAverage": reviewAverage,
        "hotel_locate": hotel_locate,
    }

    # 定義したデータをpandasに読み込ませます
    df = pd.DataFrame(data_list)

    # 重複したデータを削除し、インデックスをリセット
    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 認証のために機能役割を決めるアクセス先をscopesに設定
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    # その役割の許可をもらうAPIキーをservice_account.jsonから読み込み、credentialsに代入
    credentials = Credentials.from_service_account_file(
        'service_account.json',
        scopes=scopes
    )

    # 認証情報を格納しているcredentialsを使って、gspread.authorizeでスプレッドシートの使用許可を取り、その認証結果をgcに代入
    gc = gspread.authorize(credentials)

    # 使用するスプレッドシートのアクセス先をSP_SHEET_KEYに代入
    # https://docs.google.com/spreadsheets/d/「ここの部分がSP_SHEET_KEYに代入される」
    SP_SHEET_KEY = '1a-lk8e9ZdDt23qkvvd4UCMNJh6nuLV3IH1bvhnS5x24'

    # 開きたいスプレッドシートを認証結果を格納したgcを使ってgc.open_by_keyで開く
    sh = gc.open_by_key(SP_SHEET_KEY)

    # 参照するシート名をSP_SHEETに代入
    SP_SHEET = 'sample'

    # gc.open_by_keyで開いたスプレッドシートのsampleシートをsh.worksheet(SP_SHEET)で情報を得て、worksheetに代入する
    worksheet = sh.worksheet(SP_SHEET)

    data = worksheet.get_all_values()  # スプレッドシートにある既存のデータをdataに代入
    if data:
        df_old = pd.DataFrame(data[1:], columns=data[0])  # 既存のデータをデータフレームに格納
    else:
        # データがない場合は空のデータフレームを作成
        df_old = pd.DataFrame(columns=["hotelName", "hotelMinCharge", "reviewAverage", "hotel_locate"])

    df_new = df  # スクレイピングで取得した新しいデータdfをdf_newに代入

    # データを結合し、重複を削除
    df_upload = pd.concat([df_old, df_new])
    df_upload.drop_duplicates(inplace=True)
    df_upload.reset_index(drop=True, inplace=True)

    # シートにアクセス準備が出来たので、set_with_dataframeを使ってシートにデータフレームのデータを書き込みます。
    set_with_dataframe(worksheet, df_upload, include_index=False)

# スケジュールをクリアして新しいタスクを設定
schedule.clear()
schedule.every(2).seconds.do(job)  # 2秒ごとにジョブを実行

# スケジュールを実行
while True:
    schedule.run_pending()
    time.sleep(1)
