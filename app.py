import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium

# 音声入力ライブラリの読み込み（インストールされていない場合の対策付き）
try:
    from streamlit_mic_recorder import speech_to_text
except ImportError:
    # ライブラリがない場合はダミー関数を定義してエラーを防ぐ
    def speech_to_text(language='ja', start_prompt="", stop_prompt="", just_once=True, key="rec"):
        return None

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント L3", layout="wide")
st.title("🚛 配車最適化AI - 相性診断機能付き (Level 3)")

# --- 1. データ生成（属性拡張版） ---
def generate_dummy_data():
    # スタッフデータに「コミュ力」を追加
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "コミュ力": "低", "色": "red"},   # 黙々職人
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅",     "コミュ力": "高", "色": "blue"},  # バランス型
        {"ID": "C", "名前": "田中(C)", "スキル": "新人",     "コミュ力": "高", "色": "green"}  # 元気な新人
    ]
    office = {"現場名": "🏢 事務所(START)", "lat": 35.4658, "lon": 139.6223}
    
    # 現場データに「対人ストレス度」を追加
    locations = [
        {"現場名": "青葉区マンション", "lat": 35.55, "lon": 139.53, "難易度": "高", "ストレス": "低"},
        {"現場名": "中央ビル",         "lat": 35.45, "lon": 139.63, "難易度": "低", "ストレス": "高"}, # 管理人が厳しい
        {"現場名": "港北倉庫",         "lat": 35.52, "lon": 139.60, "難易度": "中", "ストレス": "低"},
        {"現場名": "緑区役所",         "lat": 35.51, "lon": 139.54, "難易度": "低", "ストレス": "中"},
        {"現場名": "南モール",         "lat": 35.42, "lon": 139.60, "難易度": "高", "ストレス": "高"}  # 最難関
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

# セッション初期化（データ保持用）
if 'office' not in st.session_state or 'df_site' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()

# --- 2. 新・相性診断ロジック (Level 3 Core) ---
def calculate_affinity(staff_row, site_row):
    """
    担当者と現場の属性を比較してスコア(0-100)と理由を返す関数
    """
    score = 70 # 基礎点
    reasons = []

    # 1. 技術マッチング
    if site_row["作業難易度"] == "高":
        if staff_row["スキル"] == "ベテラン":
            score += 20
            reasons.append("✅ 難所をベテラン技術でカバー")
        elif staff_row["スキル"] == "新人":
            score -= 30
            reasons.append("⚠️ 新人には技術的に荷が重いです")
    
    # 2. 対人ストレスマッチング
    if site_row["対人ストレス"] == "高":
        if staff_row["コミュ力"] == "高":
            score += 20
            reasons.append("✅ 厳しい管理人をコミュ力で対応")
        elif staff_row["コミュ力"] == "低":
            score -= 30
            reasons.append("⚠️ コミュニケーション懸念あり")
            
    # 3. ベテランの無駄遣い防止（簡単な現場にベテラン）
    if site_row["作業難易度"] == "低" and staff_row["スキル"] == "ベテラン":
        score -= 10
        reasons.append("ℹ️ ベテランには物足りない現場")

    # スコアの正規化 (0-100)
    score = max(0, min(100, score))
    
    if not reasons:
        reasons.append("特になし（標準的な配置）")
        
    return score, " / ".join(reasons)

# --- 3. AIロジック（診断機能統合版） ---
def run_optimization(instruction, df_site, df_staff):
    df = df_site.copy()
    
    # --- A. 簡易割り当てルール ---
    if "新人" in instruction:
        # 新人を簡単な現場へ優先割り当て
        mask_easy = df["作業難易度"] == "低"
        df.loc[mask_easy, "担当者"] = "田中(C)"
        # 残りをランダム
        df.loc[~mask_easy, "担当者"] = df.loc[~mask_easy, "担当者"].apply(lambda x: random.choice(["佐藤(A)", "鈴木(B)"]))
    
    elif "トラブル" in instruction:
        # ランダム配置（緊急時想定）
        df["担当者"] = df["担当者"].apply(lambda x: random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"]))
        
    else:
        # デフォルト: 未定のみ埋める
        for i in df.index:
            if df.at[i, "担当者"] == "未定":
                df.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"])
    
    # --- B. 診断ロジックの適用 (Level 3) ---
    for index, row in df.iterrows():
        staff_name = row["担当者"]
        if staff_name != "未定":
            # スタッフ情報を取得
            staff_info = df_staff[df_staff["名前"] == staff_name].iloc[0]
            # スコア計算
            score, reason = calculate_affinity(staff_info, row)
            # データフレーム更新
            df.at[index, "適合スコア"] = score
            df.at[index, "判定理由"] = reason

    # --- C. 訪問順の整理 ---
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        mask = df["担当者"] == name
        count = df[mask].shape[0]
        if count > 0:
            df.loc[mask, "訪問順"] = range(1, count + 1)
            
    return df

# --- 4. 地図描画 ---
def render_map(df_site, df_staff, office):
    m = folium.Map(location=[35.50, 139.60], zoom_start=11)
    folium.Marker([office["lat"], office["lon"]], tooltip="事務所", icon=folium.Icon(color="black", icon="building", prefix="fa")).add_to(m)
    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    # ルート線描画
    for _, staff in df_staff.iterrows():
        name = staff["名前"]
        my_sites = df_site[df_site["担当者"] == name].sort_values("訪問順")
        if not my_sites.empty:
            points = [[office["lat"], office["lon"]]]
            for _, site in my_sites.iterrows():
                points.append([site["緯度"], site["経度"]])
            folium.PolyLine(points, color=staff["色"], weight=5, opacity=0.7, tooltip=f"{name}ルート").add_to(m)

    # マーカー描画
    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        
        # ツールチップに診断情報を追加
        tip_text = f"{row['現場名']}"
        if assignee != "未定":
            tip_text += f" ({assignee})\nスコア: {row['適合スコア']}点"

        icon_type = "wrench"
        if row["適合スコア"] <= 40 and assignee != "未定":
            icon_type = "exclamation-triangle" # 低スコアは警告アイコン

        folium.Marker(
            [row["緯度"], row["経度"]], 
            tooltip=tip_text, 
            icon=folium.Icon(color=color, icon=icon_type, prefix="fa")
        ).add_to(m)
    return m

# --- 5. メイン画面レイアウト ---
col_map, col_diag = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ リアルタイム ルートマップ")
    map_obj = render_map(st.session_state.df_site, st.session_state.df_staff, st.session_state.office)
    st_folium(map_obj, height=400, width="100%", returned_objects=[])

# --- ★Level 3: 相性診断パネル ---
with col_diag:
    st.subheader("📊 相性スコア診断")
    st.markdown("AIが「なぜその人を配置したか」の根拠を表示します。")
    
    assigned_df = st.session_state.df_site[st.session_state.df_site["担当者"] != "未定"].sort_values(["担当者", "訪問順"])
    
    if assigned_df.empty:
        st.info("左下のチャットで指示を出すと、診断結果が表示されます。")
    else:
        for _, row in assigned_df.iterrows():
            with st.expander(f"{row['担当者']} ▶ {row['現場名']}", expanded=True):
                score = row['適合スコア']
                
                # スコアとバーの表示
                col_score, col_bar = st.columns([1, 3])
                with col_score:
                    st.metric("Score", f"{score}点")
                with col_bar:
                    # 色決定
                    bar_color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                    st.progress(score / 100)
                    if score < 50:
                        st.caption(f":red[**注意: 相性が悪いです**]")
                
                # 理由の表示
                st.markdown(f"**判定理由:** {row['判定理由']}")
                
                # 現場詳細スペック
                st.caption(f"現場難度: {row['作業難易度']} | 対人ストレス: {row['対人ストレス']}")


st.divider()

# --- データテーブル（デバッグ用） ---
with st.expander("📋 データ詳細確認（管理者用）"):
    st.dataframe(st.session_state.df_site)

# --- 6. チャットインターフェース ---
st.subheader("💬 AIへの配車指示")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "現在の配置状況を表示しています。「新人を優先して」「トラブル発生」などで再計算します。"}]

# チャット履歴表示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 入力エリア
col1, col2, col3 = st.columns(3)
user_input = None
if col1.button("🔰 新人ケア配置"): user_input = "新人に簡単な現場を優先して"
if col2.button("⚡️ トラブル発生"): user_input = "トラブル発生、配置をリセットして"
if col3.button("🎲 完全再計算"): user_input = "バランスよく再配置して"

audio = speech_to_text(language='ja', start_prompt="🎙 音声入力", stop_prompt="停止", just_once=True, key="rec")
if audio: user_input = audio

text = st.chat_input("指示を入力...")
if text: user_input = text

# --- 実行処理 ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 最適化＆診断実行
    new_df = run_optimization(user_input, st.session_state.df_site, st.session_state.df_staff)
    st.session_state.df_site = new_df
    
    # 応答メッセージ作成
    summary_text = f"指示「{user_input}」に基づいて再計算しました。\n右側のパネルで**相性診断スコア**を確認できます。"
    
    # 低スコアへの警告を含める
    low_scores = new_df[new_df["適合スコア"] <= 40]
    if not low_scores.empty:
        summary_text += "\n\n⚠️ **【注意】相性の悪い配置が含まれています！**\n"
        for _, row in low_scores.iterrows():
            summary_text += f"- {row['担当者']} → {row['現場名']} (理由: {row['判定理由']})\n"

    st.session_state.messages.append({"role": "assistant", "content": summary_text})
    st.rerun()