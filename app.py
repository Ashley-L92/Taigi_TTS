import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image
import tempfile

st.set_page_config(page_title="銀齡標籤", layout="centered")

# 範例小資料庫
ingredient_info = {
    "苯甲酸鈉": {"用途": "防腐劑，抑制黴菌與酵母菌生長", "風險": "部分人可能對其產生過敏反應，兒童過量攝取可能影響注意力"},
    "亞硝酸鈉": {"用途": "肉品防腐、固定紅色", "風險": "與胺類反應可能產生亞硝胺，有潛在致癌疑慮"},
    "阿斯巴甜": {"用途": "人工甜味劑，代替蔗糖", "風險": "苯酮尿症患者須避免，部分研究指出可能影響代謝"},
    "膠原蛋白": {"用途": "測試中", "風險": "測試中"},
}

# 流量控管
MAX_TAIWANES_TTS_PER_SESSION = 3
if "yating_tts_count" not in st.session_state:
    st.session_state["yating_tts_count"] = 0

MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
YATING_API_KEY = st.secrets["YATING_API_KEY"]

st.title("👵 銀齡標籤")
st.markdown("**上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。**")

# 語音語言選擇
voice_lang = st.radio("語音語言", ["中文", "台語"], index=0, horizontal=True)
speech_speed = st.radio("語音播放速度", ["正常語速", "慢速播放"], index=0, horizontal=True)

uploaded_files = st.file_uploader("請上傳商品標籤圖片（可多張，jpg/png，5MB 內）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.markdown("---")
        st.image(uploaded_file, caption="你上傳的圖片預覽", use_container_width=True)

        if uploaded_file.size > MAX_FILE_SIZE:
            st.error("❗ 檔案太大了，請上傳 5MB 以下的圖片。")
            continue

        try:
            image = Image.open(uploaded_file).convert("RGB")
            image.thumbnail((1024, 1024))
        except Exception as e:
            st.error(f"❌ 圖片處理失敗：{e}")
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            image.save(temp_file.name, format="JPEG")
            image_path = temp_file.name

        with open(image_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        prompt_text = """
這是一張商品標籤的圖片，請協助我判讀以下資訊，並在最後加上一段「總結說明」，適合以語音形式朗讀：

1. 判斷這是食品或藥品。
2. 清楚列出以下項目：
   - 類型（食品 / 藥品）
   - 中文名稱（如果有）
   - 主要成分：每項成分的功能（例如防腐、調味、營養）以及可能注意事項（例如過敏原、對特定族群不建議）
3. 使用不超過國中程度的中文描述，適合長者與一般民眾閱讀
4. **在最後加入一段「總結說明」**，用簡短白話總結這項產品的核心資訊（例如用途、成分關鍵點、誰應避免）

只輸出清楚段落文字，無需任何多餘說明。
        """

        url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        params = {"key": GEMINI_API_KEY}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": img_base64
                            }
                        }
                    ]
                }
            ]
        }

        with st.spinner("AI 正在解讀標籤中..."):
            response = requests.post(url, params=params, json=payload)

        if response.status_code == 200:
            try:
                text = response.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                import re
                summary_match = re.search(r"總結說明[:：]?\s*(.*)", text, re.DOTALL)
                if summary_match:
                   summary = summary_match.group(1).strip()
                else:
                   summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

                # ----------- 語音產生邏輯 -----------
                st.subheader("🔈 總結語音播放")
                audio_bytes = None
                audio_type = "mp3"
                import streamlit.components.v1 as components

                if voice_lang == "中文":
                    tts = gTTS(summary, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    tts.save(temp_audio.name)
                    with open(temp_audio.name, 'rb') as f:
                        audio_bytes = f.read()
                    audio_type = "mp3"
                else:  # 台語
                    if st.session_state["yating_tts_count"] >= MAX_TAIWANES_TTS_PER_SESSION:
                        st.warning("⚠️ 台語語音合成已達本次免費額度上限，請稍後再試或改用中文。")
                    else:
                        # 1. 直接送漢字給雅婷
                        yating_url = "https://tts-api.yating.tw/v2/tts"
                        yating_headers = {
                            "Authorization": "Bearer " + YATING_API_KEY,
                            "Content-Type": "application/json"
                        }
                        yating_data = {
                            "input": {"text": summary, "lang": "nan-TW"},
                            "voice": {"name": "nan-TW-KangKangNeural"},
                            "audioConfig": {"audioEncoding": "MP3"}
                        }
                        tts_resp = requests.post(yating_url, headers=yating_headers, json=yating_data)
                        if tts_resp.status_code == 200:
                            audio_bytes = tts_resp.content
                            audio_type = "mp3"
                            st.session_state["yating_tts_count"] += 1
                        else:
                            # 若出現 400 錯誤才 fallback Gemini POJ
                            if tts_resp.status_code == 400:
                                st.info("⚠️ 漢字直轉台語失敗，自動嘗試 Gemini 白話字翻譯…")
                                translate_prompt = f"請將下列文字翻譯成台灣台語的白話字（POJ），語句自然、適合語音直接播報：\n\n{summary}"
                                translate_payload = {
                                    "contents": [
                                        {
                                            "parts": [
                                                {"text": translate_prompt}
                                            ]
                                        }
                                    ]
                                }
                                trans_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
                                trans_params = {"key": GEMINI_API_KEY}
                                with st.spinner("AI 正在翻譯為台語白話字..."):
                                    trans_resp = requests.post(trans_url, params=trans_params, json=translate_payload)
                                if trans_resp.status_code == 200:
                                    taigi_text = trans_resp.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                                    # 再送給雅婷
                                    yating_data["input"]["text"] = taigi_text
                                    tts_resp2 = requests.post(yating_url, headers=yating_headers, json=yating_data)
                                    if tts_resp2.status_code == 200:
                                        audio_bytes = tts_resp2.content
                                        audio_type = "mp3"
                                        st.session_state["yating_tts_count"] += 1
                                    else:
                                        st.error("台語語音產生失敗！")
                                else:
                                    st.error("Gemini 台語翻譯失敗，無法產生語音。")
                            else:
                                st.error("台語語音產生失敗！")

                # ----------- 語音播放區塊 -----------
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    if audio_type == "mp3":
                        mimetype = "audio/mp3"
                    else:
                        mimetype = "audio/wav"
                    components.html(f"""
<audio id="summary-audio" controls>
    <source src="data:{mimetype};base64,{audio_base64}" type="{mimetype}">
    您的瀏覽器不支援音訊播放，請改用其他裝置或更新瀏覽器。
</audio>
<script>
    const audio = document.getElementById("summary-audio");
    audio.onerror = function() {{
        alert("⚠️ 無法播放語音：您的裝置或瀏覽器可能不支援該格式。");
    }};
</script>
""", height=80)
                else:
                    st.info("❗ 本次語音無法播放。")
            except Exception as e:
                st.error(f"✅ 成功回傳但解析失敗：{e}")

        else:
            st.error(f"❌ 請求錯誤（{response.status_code}）")
            try:
                err = response.json()
            except Exception:
                err = {"raw_text": response.text}
            st.subheader("🔍 API 回傳錯誤 JSON")
            st.json(err)
            st.stop()


          
   
