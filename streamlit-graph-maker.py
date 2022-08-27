import pandas as pd
import altair as alt
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# streamlitの設定
st.set_page_config(
    page_title="Blog Rank Checker",     #ページタイトル
    layout="wide",                      #ページをwide modeに
    initial_sidebar_state="expanded"    #サイドバーを表示
)

st.title('ブログ記事 検索順位チェッカー')

st.sidebar.write("""
## Blog Rank Checker
""")

@st.cache(ttl=43200)    # 12時間(43200秒)毎に再実行する
def get_data():
    # スプレッドシートの認証    
    service_account_key = st.secrets.service_account_file
    credentials = Credentials.from_service_account_info(service_account_key)
    scoped_credentials = credentials.with_scopes(
    [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])
    
    gc = gspread.authorize(scoped_credentials)
    
    # スプレッドシート「blog-rank-database-share」からデータ取得
    SP_SHEET_KEY = st.secrets.SP_SHEET_KEY.key      # スプレッドシートのキー。シート名は「blog-rank-database-share」
    sh = gc.open_by_key(SP_SHEET_KEY)
    SP_SHEET = 'db_original'                        # シート名「db_original」を指定
    worksheet = sh.worksheet(SP_SHEET)              # db_shareシートを取得
    data = worksheet.get_all_values()               # シート内の全データを取得
    df = pd.DataFrame(data[1:], columns=data[0])    # 取得したデータをデータフレームに変換
    
    # 日付のフォーマットを変更
    df['date'] = pd.to_datetime('20' + df['date'].astype(str))  #日付が220101形式なので、20220101形式に変換
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')             #日付を2022/01/01形式の文字列に変更
    df = df.set_index('date')                                   #日付列をインデックスに指定
    return df

df = get_data()

# サイドバーで検索順位を確認する記事を選択
title_list = []
title_list = df['title'].unique().tolist()
title_name = st.sidebar.selectbox(
     '記事を選択',
     title_list
)
st.write(f"""
    ***{title_name}***
""")
article_url = df.query('title == @title_name').iloc[0,0]    #選択した記事名からURLを取得する
st.write(article_url)
st.write("""---""")

df = df.query('url == @article_url')    #選択した記事のみをデータフレームから抜き出す
df = df.loc[:,['keyword', 'rank']]      #データフレームからkeyword列とrank列のみ抜き出す（日付はindex列としている）
rank_max = df['rank'].replace('>100', '-100').astype(int).max()

# 表示する表の形式を整える（日付を横に表示する）
keyword_list = []
keyword_list = df['keyword'].unique().tolist()

table_data = pd.DataFrame()
for keyword in keyword_list:
    table_data_val = df.query('keyword == @keyword')
    table_data_val = table_data_val['rank']
    table_data_val = pd.DataFrame(table_data_val)
    table_data_val.columns = [keyword]
    table_data_val = table_data_val.T
    table_data = pd.concat([table_data, table_data_val])

# グラフで表示する検索順位の範囲をサイドバーで指定する
st.sidebar.write("""
## 検索順位の範囲指定
""")
ymin, ymax = st.sidebar.slider(
    '範囲を指定',
    0, 101, (0, int(rank_max+1))
)

# グラフ用にデータフレームを整える
graph_data = table_data.T.reset_index().rename(columns={'index': 'date'})   # 欠損値がある場合、カラム名の'date'が消えているので、カラム名が'index'になる。renameしておく
graph_data = pd.melt(graph_data, id_vars=['date']).rename(
    columns={'variable': 'keyword', 'value': 'rank'}
)

# グラフに表示するキーワードをサイドバーでマルチセレクトで指定する
graph_keyword_list = []
graph_keyword_list = graph_data['keyword'].unique().tolist()
keywords = st.multiselect(
    'KeyWordを選択',
    graph_keyword_list,
    graph_keyword_list
)

if not keywords:
    st.error('キーワードを選んでください')      #キーワードを一つも選んでいない時はエラーを表示する
else:
    graph_data = graph_data.query('keyword in @keywords')    #選択されたキーワードの行のみ、データフレーム（グラフ用）から抽出
    st.write(table_data.query('index in @keywords').reset_index().sort_index(ascending=False, axis=1).sort_index(ascending=True, axis=0))        #選択されたキーワードの行のみ、データフレーム（テーブル用）から抽出
    st.write("""---""")
 
    # Altairでグラフを表示する   
    def get_chart(data):
        
        # 折れ線グラフの設定
        selection = alt.selection_multi(fields=['keyword'], bind='legend')
        lines = (
            alt.Chart(data, title="Blog Rank Checker")
            .mark_line(opacity=0.8, clip=True)
            .encode(
                x="date:T",
                y=alt.Y("rank:Q", stack=None, scale=alt.Scale(domain=[ymin, ymax])),
                color=alt.Color('keyword', sort=None),
                opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
            ).add_selection(
                selection
            )
        )
        
        # ホバー時にマークを表示する
        hover = alt.selection_single(
            fields=["date"],
            nearest=True,
            on="mouseover",
            empty="none",
        )
        lines2 = (
            alt.Chart(data)
            .encode(
                x="date:T",
                y=alt.Y("rank:Q", stack=None, scale=alt.Scale(domain=[ymin, ymax])),
                color=alt.Color('keyword', sort=None),
            )
        )
        points = lines2.transform_filter(hover).mark_circle(size=50)

        # ホバー時にツールチップを表示
        tooltips = (
            alt.Chart(data)
            .mark_rule()
            .encode(
                x="date:T",
                y=alt.Y("rank:Q", stack=None, scale=alt.Scale(domain=[ymin, ymax])),
                opacity=alt.condition(hover, alt.value(0.1), alt.value(0)),
                tooltip=[
                    alt.Tooltip("date:T", title="date"),
                    alt.Tooltip("keyword", title="keyword"),
                    alt.Tooltip("rank", title="rank"),
                ],
            )
            .add_selection(hover)
        )
        
        return (lines + points + tooltips).interactive()

    chart = get_chart(graph_data)
    st.altair_chart(chart, use_container_width=True)
