import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont # 確保導入 ImageDraw 和 ImageFont
import tempfile
import re # 確保導入 re 模組

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

# 🔧 輔助函數定義 (移到程式碼頂層)
def remove_markdown(text):
    """移除文字中的 Markdown 符號。"""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text) # 移除粗體 **
    text = re.sub(r"\*(.*?)\*", r"\1", text)     # 移除斜體 *
    text = re.sub(r"__(.*?)__", r"\1", text)     # 移除底線 __
    text = re.sub(r"`(.*?)`", r"\1", text)       # 移除程式碼塊 `
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE) # 移除標題 #
    text = re.sub(r"^- ", "", text, flags=re.MULTILINE)   # 移除列表 -
    return text.strip()

def highlight_ingredients(text_to_highlight, db):
    """將文本中包含在成分資料庫的成分名稱高亮顯示。"""
    for ing in db:
        if ing in text_to_highlight:
            # 使用更精確的正則表達式來避免部分匹配，例如「胺」匹配到「亞硝酸鈉」中的「胺」
            # 這裡簡單替換，如果需要更嚴謹，可能需要分詞或使用更複雜的匹配邏輯
            replacement = f"<span style='color:#0066cc; font-weight:bold;'>{ing}</span>"
            text_to_highlight = text_to_highlight.replace(ing, replacement)
    return text_to_highlight

def generate_summary_image(text_to_render, output_path="summary_card.png"):
    """
    根據提供的文本生成一張圖片。
    需要確保運行環境有支援中文的字型檔案。
    """
    width, height = 800, 600
    background_color = (255, 255, 255)
    text_color = (30, 30, 30)

    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)

    try:
        # 嘗試載入常見的中文字型
        # Windows: "msjh.ttf" (微軟正黑體), "simhei.ttf" (黑體)
        # macOS: "Arial Unicode.ttf", "PingFang.ttc" (蘋方)
        # Linux: "wqy-microhei.ttc" (文泉驛微米黑), "NotoSansCJK-Regular.ttc"
        # 請根據您的運行環境選擇或提供正確的路徑
        font = ImageFont.truetype("msjh.ttf", size=28) # 優先嘗試微軟正黑體
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", size=28) # 其次嘗試 Arial
        except IOError:
            font = ImageFont.load_default() # 如果都失敗，使用預設字型
            st.warning("⚠️ 未找到支援中文字型，生成的圖片可能無法正確顯示中文。")

    lines = []
    line = ""
    # 按字元分割來處理中文換行
    for char in text_to_render:
        # draw.textlength 估算文本寬度
        if draw.textlength(line + char, font=font) <= width - 80:
            line += char
        else:
            lines.append(line.strip())
            line = char
    lines.append(line.strip()) # 加入最後一行

    y = 50
    for line_content in lines:
        draw.text((40, y), line_content, font=font, fill=text_color)
        y += font.getbbox(line_content)[3] - font.getbbox(line_content)[1] + 10 # 計算行高加上間距

    img.save(output_path)
    return output_path

def generate_taiwanese_tts(text_to_synthesize, hf_api_token):
    """使用 Hugging Face API 生成台語語音。"""
    url = "https://api-inference.huggingface.co/models/smartlabs/tts-taiwanese-hf" # 這個模型是個不錯的選擇
    headers = {
        "Authorization": f"Bearer {hf_api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": text_to_synthesize,
        "options": {"use_cache": False}, # 避免快取舊的結果
    }

    try:
        response_tai = requests.post(url, headers=headers, json=payload, stream=True)

        if response_tai.status_code == 200:
            temp_tai_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            with open(temp_tai_audio.name, 'wb') as f:
                for chunk in response_tai.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return temp_tai_audio.name
        else:
            st.warning(f"⚠️ 台語語音產生失敗，API 回傳錯誤碼：{response_tai.status_code} ({response_tai.text})。請稍後再試。")
            return None
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ 台語語音產生失敗，網路請求錯誤：{e}")
        return None

# ✅ 強制放最前面
st.set_page_config(page_title="長者友善標籤小幫手", layout="centered")

# ✅ 頁面強制刷新處理（用 URL query 判斷）
if "reset" in st.query_params:
    st.markdown(
        """<meta http-equiv="refresh" content="0; url='/'" />""",
        unsafe_allow_html=True
    )
    st.stop()

# 🔄 重新開始按鈕（觸發 URL query）
if st.button("🔄 重新開始"):
    st.query_params["reset"] = "true"
    st.rerun()

MAX_FILE_SIZE = 5 * 1024 * 1024

# 從 Streamlit secrets 獲取 API 金鑰
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("錯誤：請在 `.streamlit/secrets.toml` 中設定 `GEMINI_API_KEY`。")
    st.stop()

try:
    HF_API_TOKEN = st.secrets["HF_API_TOKEN"]
except KeyError:
    st.error("錯誤：請在 `.streamlit/secrets.toml` 中設定 `HF_API_TOKEN`。")
    st.stop()


st.title("👵 長者友善標籤小幫手")
st.markdown("""
**上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。**

⚠️ **提醒** 由於目前使用的 API 額度較低，若同時有多人使用或使用過於頻繁，可能會遇到額度限制（Error 429）。如果出現錯誤，請稍後再試～
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
    html, body, [class*="css"] {{
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
            image.thumbnail((1024, 1024)) # 調整縮圖大小
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

        gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        gemini_params = {"key": GEMINI_API_KEY}
        gemini_payload = {
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
            response = requests.post(gemini_url, params=gemini_params, json=gemini_payload)

        if response.status_code == 200:
            try:
                text = response.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()

                if not text:
                    st.warning("⚠️ 此圖片未產出有效文字，可能為圖像不清晰或無內容。")
                    continue

                summary_match = re.search(r"總結說明[:：]?\s*(.*)", text, re.DOTALL)
                if summary_match:
                    summary = summary_match.group(1).strip()
                else:
                    summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

                # 確保 summary 不為空，以防解析失敗
                if not summary:
                    summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

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

                # 語音播放 (中文)
                tts = gTTS(summary, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(temp_audio.name)

                st.subheader("🔈 總結語音播放（若無法播放將提示）")
                import streamlit.components.v1 as components

                audio_bytes = open(temp_audio.name, 'rb').read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                components.html(f"""
    <audio id="summary-audio" controls>
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mpeg">
        您的瀏覽器不支援音訊播放，請改用其他裝置或更新瀏覽器。
    </audio>
    <script>
        const audio = document.getElementById("summary-audio");
        audio.onerror = function() {{
            console.error("無法播放語音：您的裝置或瀏覽器可能不支援 MP3 播放。");
        }};
    </script>
""", height=80)

                # 台語語音播放
                st.subheader("🗣️ 台語語音播放（實驗功能）")
                plain_summary_for_taiwanese = remove_markdown(summary)
                # 這裡呼叫 generate_taiwanese_tts 函數，並傳入 HF_API_TOKEN
                tai_audio_path = generate_taiwanese_tts(plain_summary_for_taiwanese, HF_API_TOKEN)

                if tai_audio_path:
                    with open(tai_audio_path, "rb") as f:
                        tai_bytes = f.read()
                        tai_base64 = base64.b64encode(tai_bytes).decode("utf-8")
                        components.html(f"""
                        <audio id="tai-audio" controls>
                        <source src="data:audio/wav;base64,{tai_base64}" type="audio/wav">
                        您的瀏覽器不支援台語語音播放，請改用其他裝置。
                        </audio>
                        <script>
                            const audio = document.getElementById("tai-audio");
                            audio.onerror = function() {{
                                console.error("無法播放台語語音：請確認裝置支援 WAV 格式。");
                            }};
                        </script>
                    """, height=80)
                else:
                    st.info("台語語音未能生成。")


                st.info("🤖 本解讀為 AI 推論結果，若有疑問請諮詢專業人員。")

                # 📝 建立純文字版 summary
                plain_summary_for_copy = remove_markdown(summary)

                # 📋 一鍵複製按鈕（顯示在頁面上）
                st.markdown("### 📋 一鍵複製總結內容")
                components.html(f"""
                    <textarea id="summary-text" style="width:100%; height:150px;">{plain_summary_for_copy}</textarea>
                    <button onclick="copyToClipboard()" style="margin-top:10px;">點我複製到剪貼簿</button>
                    <script>
                    function copyToClipboard() {{
                        var copyText = document.getElementById("summary-text");
                        copyText.select();
                        document.execCommand("copy");
                        console.log("✅ 已複製到剪貼簿！");
                    }}
                    </script>
                """, height=250)

                # 📸 生成並顯示圖片卡
                image_output_path = generate_summary_image(plain_summary_for_copy)
                st.image(image_output_path, caption="📸 分享用成分說明卡", use_column_width=True)

                with open(image_output_path, "rb") as file:
                    st.download_button(
                        label="⬇️ 下載圖片卡",
                        data=file,
                        file_name="summary_card.png",
                        mime="image/png"
                    )

            except Exception as e:
                st.error(f"✅ 成功回傳但解析或處理失敗：{e}")
                st.exception(e) # 顯示完整的錯誤堆疊，有助於除錯

        else:
            if response.status_code == 429:
                st.error("⚠️ 由於目前使用的API為免費版本，若同時有多人使用或使用過於頻繁，可能會遇到額度限制（Error 429）。如果出現錯誤，請稍後再試～")
            else:
                st.error(f"❌ 請求錯誤（{response.status_code}）")
            try:
                err = response.json()
            except Exception:
                err = {"raw_text": response.text}

            st.subheader("🔍 API 回傳錯誤 JSON")
            st.json(err)
            st.stop()
