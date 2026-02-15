import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium

# 音声入力ライブラリ（なければ無効化）
try:
    from streamlit_mic_recorder import speech_to_text
except ImportError:
    def speech_to_text(language='ja', start_prompt="", stop_prompt="", just_once=True, key="rec"):
        return None

# --- ページ設定 ---
st.set_page_config(page_title="AI配車統括ダッシュボード", layout="wide", initial_sidebar_state="expanded")
st.title("🚛 AI配車統括ダッシュボード (Final Integration)")

# --- 1. データ生成（属性拡張版） ---
def generate_dummy_data():
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "コミュ力": "低", "色": "red"},
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅",     "コミュ力": "高", "色": "blue"},
        {"ID": "C", "名前": "田中(C)", "スキル": "新人",     "コミュ力": "高", "色": "green"}
    ]
    office = {"現場名": "🏢 事務所(START)", "lat": 35.4658, "lon": 139.6223}
    locations = [
        {"現場名": "青葉区マンション", "lat": 35.55, "lon": 139.53, "難易度": "高", "ストレス": "低"},
        {"現場名": "中央ビル",         "lat": 35.45, "lon": 139.63, "難易度": "低", "ストレス": "高"},
        {"現場名": "港北倉庫",         "lat": 35.52, "lon": 139.60, "難易度": "中", "ストレス": "低"},
        {"現場名": "緑区役所",         "lat": 35.51, "lon": 139.54, "難易度": "低", "ストレス": "中"},
        {"現場名": "南モール",         "lat": 35.42, "lon": 139.60, "難易度": "高", "ストレス": "高"}
    ]
    site_data = []
    for loc in locations:
        site_data.append({
            "現場名": loc["現場名"],
            "緯度": loc["lat"],
            "経度": loc["lon"],
            "作業難易度": loc["難易度"],
            "対人ストレス": loc["ストレス"],
            "担当者": "未定", 
            "適合スコア": 0,
            "判定理由": "",
            "訪問順": 0
        })
    return pd.DataFrame(staff_data), pd.DataFrame(site_data), office

# セッション初期化
if 'office' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()

# --- 2. 診断ロジック ---
def calculate_affinity(staff_row, site_row):
    score = 70
    reasons = []
    
    # 技術マッチング
    if site_row["作業難易度"] == "高":
        if staff_row["スキル"] == "ベテラン":
            score += 20
            reasons.append("技術適合(◎)")
        elif staff_row["スキル"] == "新人":
            score -= 30
            reasons.append("技術不足懸念(⚠)")
            
    # ストレスマッチング
    if site_row["対人ストレス"] == "高":
        if staff_row["コミュ力"] == "高":
            score += 20
            reasons.append("対人適性あり(◎)")
        elif staff_row["コミュ力"] == "低":
            score -= 30
            reasons.append("対人トラブル懸念(⚠)")
    
    # 資源の最適化
    if site_row["作業難易度"] == "低" and staff_row["スキル"] == "ベテラン":
        score -= 10
        reasons.append("オーバースペック(△)")

    score = max(0, min(100, score))
    return score, " / ".join(reasons) if reasons else "標準マッチング"

# --- 3. 最適化エンジン ---
def run_optimization(instruction, df_site, df_staff):
    df = df_site.copy()
    
    # 簡易ルール適用
    if "新人" in instruction:
        mask_easy = df["作業難易度"] == "低"
        df.loc[mask_easy, "担当者"] = "田中(C)"
        df.loc[~mask_easy, "担当者"] = df.loc[~mask_easy, "担当者"].apply(lambda x: random.choice(["佐藤(A)", "鈴木(B)"]))
    elif "トラブル" in instruction:
        df["担当者"] = df["担当者"].apply(lambda x: random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"]))
    else:
        for i in df.index:
            if df.at[i, "担当者"] == "未定":
                # ↓ここを修正しました
                df.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"])
    
    # スコア計算
    for index, row in df.iterrows():
        if row["担当者"] != "未定":
            staff_info = df_staff[df_staff["名前"] == row["担当者"]].iloc[0]
            score, reason = calculate_affinity(staff_info, row)
            df.at[index, "適合スコア"] = score
            df.at[index, "判定理由"] = reason

    # 訪問順序
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        mask = df["担当者"] == name
        if df[mask].shape[0] > 0:
            df.loc[mask, "訪問順"] = range(1, df[mask].shape[0] + 1)
            
    return df

# --- 4. UIコンポーネント: 結論サマリー生成 ---
def render_summary(df):
    assigned = df[df["担当者"] != "未定"]
    if assigned.empty:
        st.info("👈 左側のチャットから指示を出してください。")
        return

    avg_score = assigned["適合スコア"].mean()
    low_scores = assigned[assigned["適合スコア"] <= 40]
    
    # スタイル定義
    card_style = """
    <div style='padding:15px; border-radius:10px; background-color:#f0f2f6; border-left: 5px solid {color};'>
        <h4 style='margin:0;'>{title}</h4>
        <p style='margin:0; font-size:18px;'>{content}</p>
    </div>
    """
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        color = "#4CAF50" if avg_score >= 70 else "#FF9800" if avg_score >= 50 else "#F44336"
        st.markdown(card_style.format(color=color, title="平均適合スコア", content=f"**{avg_score:.1f}点** / 100点"), unsafe_allow_html=True)
        
    with col2:
        st.markdown(card_style.format(color="#2196F3", title="配車完了数", content=f"**{len(assigned)}** / {len(df)} 現場"), unsafe_allow_html=True)

    with col3:
        if not low_scores.empty:
            alert_msg = f"⚠️ **{len(low_scores)}件** のリスクあり"
            st.markdown(card_style.format(color="#F44336", title="アラート", content=alert_msg), unsafe_allow_html=True)
        else:
            st.markdown(card_style.format(color="#4CAF50", title="アラート", content="✅ 問題なし"), unsafe_allow_html=True)

    # テキストによる結論（ここがポイント）
    st.write("")
    if not low_scores.empty:
        st.warning(f"**【AIからの報告】** 全体的に配置しましたが、**{low_scores.iloc[0]['担当者']}** さんの配置に無理がある可能性があります（{low_scores.iloc[0]['判定理由']}）。再検討を推奨します。")
    else:
        st.success("**【AIからの報告】** メンバーのスキルと現場の特性がマッチしており、非常にバランスの良い配置です。このプランでの実行を推奨します。")

# --- 5. UIコンポーネント: 地図 ---
def render_map(df_site, df_staff, office):
    m = folium.Map(location=[35.50, 139.60], zoom_start=11)
    folium.Marker([office["lat"], office["lon"]], tooltip="事務所", icon=folium.Icon(color="black", icon="building", prefix="fa")).add_to(m)
    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    for _, staff in df_staff.iterrows():
        name = staff["名前"]
        my_sites = df_site[df_site["担当者"] == name].sort_values("訪問順")
        if not my_sites.empty:
            points = [[office["lat"], office["lon"]]] + [[s["緯度"], s["経度"]] for _, s in my_sites.iterrows()]
            folium.PolyLine(points, color=staff["色"], weight=5, opacity=0.7).add_to(m)

    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        icon = "exclamation-triangle" if row["適合スコア"] <= 40 and assignee != "未定" else "wrench"
        folium.Marker(
            [row["緯度"], row["経度"]], 
            tooltip=f"{row['現場名']} ({assignee}) {row['適合スコア']}点", 
            icon=folium.Icon(color=color, icon=icon, prefix="fa")
        ).add_to(m)
    return m

# ================================
# メインレイアウト構築
# ================================

# --- A. チャット & 指示エリア (サイドバーまたは上部) ---
with st.sidebar:
    st.header("💬 AI指示コンソール")
    
    # 履歴表示
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "条件を入力してください。"}]
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # 入力ボタン類
    st.write("---")
    c1, c2 = st.columns(2)
    if c1.button("🔰 新人ケア"): user_input = "新人に簡単な現場を"
    elif c2.button("🎲 再計算"): user_input = "バランスよく再配置"
    else: user_input = None
    
    audio = speech_to_text(language='ja', key="rec")
    if audio: user_input = audio
    
    text_val = st.chat_input("例: 雨なので安全優先で")
    if text_val: user_input = text_val

    # 計算実行
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        new_df = run_optimization(user_input, st.session_state.df_site, st.session_state.df_staff)
        st.session_state.df_site = new_df
        st.session_state.messages.append({"role": "assistant", "content": "再計算しました。右側のダッシュボードを確認してください。"})
        st.rerun()

# --- B. メインダッシュボード ---

# 1. 結論サマリー（テキスト＆数値）
st.subheader("📊 診断サマリー")
render_summary(st.session_state.df_site)

st.divider()

# 2. 地図と詳細カードの分割レイアウト
col_map, col_details = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ ルートマップ")
    map_obj = render_map(st.session_state.df_site, st.session_state.df_staff, st.session_state.office)
    st_folium(map_obj, height=450, width="100%", returned_objects=[])

with col_details:
    st.subheader("🧐 診断詳細 (Why?)")
    df_active = st.session_state.df_site[st.session_state.df_site["担当者"] != "未定"].sort_values(["担当者", "訪問順"])
    
    if df_active.empty:
        st.info("まだ配車されていません")
    else:
        for _, row in df_active.iterrows():
            score = row['適合スコア']
            # カードの色分け
            border_color = "red" if score <= 40 else "green"
            with st.expander(f"{row['担当者']} ▶ {row['現場名']} ({score}点)", expanded=(score<=40)):
                st.progress(score / 100)
                st.markdown(f"**理由:** {row['判定理由']}")
                st.caption(f"難易度: {row['作業難易度']} | ストレス: {row['対人ストレス']}")

# 3. 管理者用データ（プルダウン）
st.divider()
with st.expander("📋 【管理者用】全データ・パラメータ確認"):
    tab1, tab2 = st.tabs(["要員リスト (Staff)", "現場リスト (Site)"])
    with tab1:
        st.dataframe(st.session_state.df_staff, use_container_width=True)
    with tab2:
        st.dataframe(st.session_state.df_site, use_container_width=True)
