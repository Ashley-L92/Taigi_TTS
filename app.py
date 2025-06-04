import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image
import tempfile

# 📦 成分小資料庫（可以之後換成 csv）
ingredient_info = {
    "苯甲酸鈉": {
        "用途": "防腐劑，抑制黴菌與酵母菌生長",
        "風險": "部分人可能對其產生過敏反應，兒童過量攝取可能影響注意力"
    },
    "亞硝酸鈉": {
        "用途": "肉品防腐、固定紅色",
        "風險": "與胺類反應可能產生亞硝胺，有潛在致癌疑慮"
    },
    "阿斯巴甜": {
        "用途": "人工甜味劑，代替蔗糖",
        "風險": "苯酮尿症患者須避免，部分研究指出可能影響代謝"
    },
    "膠原蛋白": {
        "用途": "測試中",
        "風險": "測試中"
    },
    # 你可以繼續加～
}

st.set_page_config(page_title="銀齡標籤", layout="centered")

if "reset" in st.query_params:
    st.markdown(
        """<meta http-equiv="refresh" content="0; url='/'" />""",
        unsafe_allow_html=True
    )
    st.stop()

if st.button("🔄 重新開始"):
    st.query_params["reset"] = "true"
    st.rerun()

MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

st.title("👵 銀齡標籤")
st.markdown("""
**上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。**

⚠️ **提醒**  
由於目前使用的 API 額度較低，若同時有多人使用或使用過於頻繁，可能會遇到額度限制（Error 429）。如果出現錯誤，請稍後再試～
""")

st.markdown("""
<div style="padding:20px; border-radius:5px;">
  <p>📌 <b>使用流程說明：</b></p>
  <div style="background-color:#E94707; color:white;padding:10px; border-radius:5px; margin-top:5px;">
    1️⃣ 選擇介面字體大小與模式
  </div>
  <div style="background-color:#FFB405; color:white;padding:10px; border-radius:5px;margin-top:5px;">
    2️⃣ 上傳清晰的商品標籤圖片
  </div>
  <div style="background-color:#9BB300; color:white;padding:10px; border-radius:5px;margin-top:5px;">
    3️⃣ 查看解讀結果並收聽語音朗讀
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background-color:#E94707; color:white; padding:10px; border-radius:5px; text-align:center;">
<b>步驟1：請選擇介面整體字體大小和模式</b>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:0 px; border-radius:0 px">
<b>請選擇介面字體大小</b>
</div>""", unsafe_allow_html=True)

font_size_choice = st.radio(
    "", ["小", "中", "大"],
    index=1,
    horizontal=True
)
st.markdown(f"目前介面字體大小為：**{font_size_choice}**")
font_size_map = {
    "小": "16px",
    "中": "20px",
    "大": "26px"
}
chosen_font_size = font_size_map[font_size_choice]

st.markdown(
    f"""
    <style>
    html, body, [class*="css"]  {{
        font-size: {chosen_font_size} !important;
        line-height: 1.6;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("""
<div style="padding:0 px; border-radius:0 px">
<b>請選擇顯示模式</b>
</div>
""", unsafe_allow_html=True)

mode = st.radio("", ["簡易模式（僅總結）", "進階模式（完整解讀）"],index=1,
    horizontal=True)
st.markdown("""
<div style="padding:0 px; border-radius:0 px">
<b>請選擇語音播放速度</b>
</div>
""", unsafe_allow_html=True)
speech_speed = st.radio(" ", ["正常語速", "慢速播放"],index=1,
    horizontal=True)

# 語音語言選擇
st.markdown("""
<div style="padding:0 px; border-radius:0 px">
<b>請選擇語音播報語言</b>
</div>
""", unsafe_allow_html=True)
voice_lang = st.radio(
    "語音語言", ["中文", "台語"], index=0, horizontal=True
)

st.markdown("""
<div style="background-color:#FFB405; color:white;padding:10px; border-radius:5px;text-align:center;">
<b>步驟2：請上傳商品標籤圖片</b>
</div>
""", unsafe_allow_html=True)
uploaded_files = st.file_uploader("請上傳商品標籤圖片（可多張，jpg/png，5MB 內）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
st.markdown("""
📝 <span style="color:#ff4b4b;"><b>圖片上傳提示：</b></span>  
- 建議拍攝清晰、光線充足的圖片  
- 避免反光或模糊，以確保更好的辨識效果
""", unsafe_allow_html=True)
st.markdown("""
<div style="background-color:#9BB300; color:white;padding:10px; border-radius:5px;text-align:center;">
<b>步驟3：請查看解讀結果</b>
</div>
""", unsafe_allow_html=True)

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
                if not text:
                    st.warning("⚠️ 此圖片未產出有效文字，可能為圖像不清晰或無內容。")
                    continue

                import re
                summary_match = re.search(r"總結說明[:：]?\s*(.*)", text, re.DOTALL)
                if summary_match:
                   summary = summary_match.group(1).strip()
                else:
                   summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

                if not summary:
                    summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

                def highlight_ingredients(text, db):
                    for ing in db:
                        if ing in text:
                            replacement = f"<span style='color:#0066cc; font-weight:bold;'>{ing}</span>"
                            text = text.replace(ing, replacement)
                    return text

                highlighted_summary = highlight_ingredients(summary, ingredient_info)

                st.subheader("📝 成分說明")
                if mode == "進階模式（完整解讀）":
                    st.markdown(
                        f"<div style='font-size:{chosen_font_size}; line-height:1.8;'>{text}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div style='font-size:{chosen_font_size}; font-weight:bold;'>{highlighted_summary}</div>",
                        unsafe_allow_html=True
                    )
                for name, info in ingredient_info.items():
                    if name in summary:
                        with st.expander(f"🔍 關於「{name}」的說明"):
                            st.markdown(f"**用途：** {info['用途']}")
                            st.markdown(f"**風險：** {info['風險']}")

                # ----------- 台語翻譯與語音產生 -----------
                summary_for_tts = summary  # 預設用中文

                if voice_lang == "台語":
                    # Gemini 翻譯成台語白話字
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
                        try:
                            taigi_text = trans_resp.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                            summary_for_tts = taigi_text
                        except Exception as e:
                            st.error(f"台語翻譯回傳解析失敗：{e}")
                            summary_for_tts = summary  # fallback
                    else:
                        st.error("台語翻譯API失敗，將以中文語音播放")
                        summary_for_tts = summary  # fallback

                # ----------- 語音產生 -----------
                st.subheader("🔈 總結語音播放")
                audio_bytes = None
                audio_type = "mp3"
                import streamlit.components.v1 as components
                if voice_lang == "中文":
                    tts = gTTS(summary_for_tts, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    tts.save(temp_audio.name)
                    with open(temp_audio.name, 'rb') as f:
                        audio_bytes = f.read()
                    audio_type = "mp3"
                else:
                    url = "https://tts.ithuan.tw/api/tts"
                    tts_resp = requests.post(url, json={"text": summary_for_tts, "lang": "nan-TW"})
                    if tts_resp.status_code == 200:
                        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                        temp_audio.write(tts_resp.content)
                        temp_audio.close()
                        with open(temp_audio.name, 'rb') as f:
                            audio_bytes = f.read()
                        audio_type = "wav"
                    else:
                        st.error("iTaigi-tts 語音產生失敗！")
                        audio_bytes = None

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

                st.info("🤖 本解讀為 AI 推論結果，若有疑問請諮詢專業人員。")
                # 🔧 定義清理 markdown 的函式（可以放在檔案開頭）
                def remove_markdown(text):
                    import re
                    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
                    text = re.sub(r"\*(.*?)\*", r"\1", text)
                    text = re.sub(r"__(.*?)__", r"\1", text)
                    text = re.sub(r"`(.*?)`", r"\1", text)
                    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
                    text = re.sub(r"^- ", "", text, flags=re.MULTILINE)
                    return text.strip()

                plain_summary = remove_markdown(summary)

                st.markdown("### 📋 一鍵複製總結內容")
                components.html(f"""
                    <textarea id="summary-text" style="width:100%; height:150px;">{plain_summary}</textarea>
                    <button onclick="copyToClipboard()" style="margin-top:10px;">點我複製到剪貼簿</button>
                    <script>
                    function copyToClipboard() {{
                        var copyText = document.getElementById("summary-text");
                        copyText.select();
                        document.execCommand("copy");
                        alert("✅ 已複製到剪貼簿！");
                    }}
                    </script>
                """, height=250)

                from PIL import ImageDraw, ImageFont

                def generate_summary_image(text, output_path="summary_card.png"):
                    width, height = 800, 600
                    background_color = (255, 255, 255)
                    text_color = (30, 30, 30)
                    img = Image.new("RGB", (width, height), color=background_color)
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("arial.ttf", size=28)
                    except:
                        font = ImageFont.load_default()
                    lines = []
                    line = ""
                    for word in text.split():
                        if draw.textlength(line + " " + word, font=font) <= width - 80:
                            line += " " + word
                        else:
                            lines.append(line.strip())
                            line = word
                    lines.append(line.strip())
                    y = 50
                    for line in lines:
                        draw.text((40, y), line, font=font, fill=text_color)
                        y += 40
                    img.save(output_path)
                    return output_path

                image_path = generate_summary_image(plain_summary)
                st.image(image_path, caption="📸 分享用成分說明卡", use_column_width=True)
                with open(image_path, "rb") as file:
                    st.download_button(
                        label="⬇️ 下載圖片卡",
                        data=file,
                        file_name="summary_card.png",
                        mime="image/png"
                    )

            except Exception as e:
                st.error(f"✅ 成功回傳但解析失敗：{e}")

        else:
            if response.status_code == 429:
                st.error("⚠️ 由於目前使用的API為免費版本，若同時有多人使用或使用過於頻繁，可能會遇到額度限制（Error 429）。如果出現錯誤，請稍後再試～")
            else:
                st.error(f"❌ 請求錯誤（{response.status_code}）")
            try:
                err = response.json()
            except Exception:
                err = {"raw_text": response.text}
            st.error(f"❌ 請求錯誤（{response.status_code}）")
            st.subheader("🔍 API 回傳錯誤 JSON")
            st.json(err)
            st.stop()
