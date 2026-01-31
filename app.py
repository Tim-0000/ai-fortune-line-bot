# -*- coding: utf-8 -*-
"""
AI 命理大師 Line Bot
整合 OpenAI GPT + Replicate 圖片生成
支援塔羅牌占卜模式
"""

import os
import json
import re
import random
from flask import Flask, request, abort
from dotenv import load_dotenv

# Line Bot SDK
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    TemplateMessage,
    ButtonsTemplate,
    MessageAction,
    QuickReply,
    QuickReplyItem
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# OpenAI
from openai import OpenAI

# Replicate (圖片生成)
import replicate

# ===== 載入環境變數 =====
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# ===== 初始化 Flask 應用程式 =====
app = Flask(__name__)

# ===== 初始化 Line Bot =====
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ===== 初始化 OpenAI =====
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ===== 塔羅牌定義 =====
TAROT_CARDS = [
    "愚者", "魔術師", "女祭司", "皇后", "皇帝", "教皇", "戀人", "戰車",
    "力量", "隱者", "命運之輪", "正義", "倒吊人", "死神", "節制", "惡魔",
    "高塔", "星星", "月亮", "太陽", "審判", "世界"
]

# 設定命理大師的 System Prompt（一般模式）
MASTER_SYSTEM_PROMPT = """你是一位神祕且充滿智慧的命理大師，名為「玄天上師」。
你擅長用譬喻和溫暖的口吻為人解惑，語氣帶有古典韻味但不失親切。

當使用者詢問任何問題時，你必須回傳一個 JSON 格式的回應，包含兩個欄位：
1. "reply": 給使用者的繁體中文回覆（約100-150字），要有神祕感和智慧感
2. "image_prompt": 給 AI 繪圖用的英文提示詞，描述當下意境的畫面（約30-50字）

畫面風格請傾向神祕、東方玄學、賽博龐克風格的混合。

範例輸出格式：
{
  "reply": "施主問財運，老衲觀你近日星象，猶如春江水暖...",
  "image_prompt": "A mystical fortune teller surrounded by golden coins and tarot cards, cyberpunk oriental style, glowing neon lights, ethereal atmosphere"
}

請務必只回傳 JSON 格式，不要有其他文字。"""

# 塔羅牌解讀 System Prompt
TAROT_SYSTEM_PROMPT = """你是一位神祕的塔羅牌占卜師，名為「玄天上師」。
使用者抽到了一張塔羅牌，請根據牌面和他們的問題給予解讀。

你必須回傳一個 JSON 格式的回應，包含兩個欄位：
1. "reply": 給使用者的繁體中文塔羅牌解讀（約150-200字），要有神祕感，先描述牌的意義，再結合問題給予建議
2. "image_prompt": 給 AI 繪圖用的英文提示詞，描述這張塔羅牌的畫面（約30-50字），風格要神祕、東方玄學、賽博龐克混合

範例輸出格式：
{
  "reply": "你抽到了「命運之輪」，此牌象徵著命運的轉動...",
  "image_prompt": "A mystical Wheel of Fortune tarot card, glowing with golden light, cyberpunk oriental style, ethereal atmosphere"
}

請務必只回傳 JSON 格式，不要有其他文字。"""

# ===== 錯誤回覆訊息 =====
ERROR_MESSAGE = "🔮 天機訊號干擾中，請稍後再試。"

# ===== 使用者狀態儲存（簡易版，重啟會清空）=====
user_states = {}  # {user_id: {"mode": "tarot", "question": "...", "cards": [...]}}


def ask_openai(user_message: str, system_prompt: str = MASTER_SYSTEM_PROMPT) -> dict:
    """
    呼叫 OpenAI GPT 生成回覆
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # 解析 JSON
        cleaned_text = re.sub(r'^```json\s*', '', response_text)
        cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
        
        result = json.loads(cleaned_text)
        return result
    
    except Exception as e:
        print(f"OpenAI 錯誤: {e}")
        return None


def generate_image(prompt: str) -> str:
    """
    使用 Replicate 呼叫 SDXL 模型生成圖片
    """
    try:
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
        
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "scheduler": "K_EULER",
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "negative_prompt": "ugly, blurry, low quality, distorted"
            }
        )
        
        if output and len(output) > 0:
            return str(output[0])
        return None
    
    except Exception as e:
        print(f"Replicate 錯誤: {e}")
        return None


def get_reply_mode(message: str) -> str:
    """
    判斷使用者要的回覆模式
    """
    message_lower = message.lower()
    
    # 塔羅牌模式
    if any(keyword in message for keyword in ["抽牌", "塔羅", "占卜", "抽籤", "抽卡"]):
        return "tarot"
    
    # 純文字模式
    if any(keyword in message for keyword in ["純文字", "快速", "文字就好", "不要圖"]):
        return "text_only"
    
    # 圖文模式
    if any(keyword in message for keyword in ["要圖", "圖文", "完整", "附圖"]):
        return "full"
    
    # 預設：純文字（較快）
    return "text_only"


def draw_three_cards() -> list:
    """
    抽三張不重複的塔羅牌
    """
    return random.sample(TAROT_CARDS, 3)


# ===== Line Webhook 端點 =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    app.logger.info(f"收到請求: {body}")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("簽章驗證失敗")
        abort(400)
    
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    """
    處理文字訊息事件
    """
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    app.logger.info(f"使用者 {user_id} 訊息: {user_message}")
    
    # 檢查是否在選牌階段
    if user_id in user_states and user_states[user_id].get("mode") == "selecting":
        handle_card_selection(event, user_id, user_message)
        return
    
    # 判斷回覆模式
    mode = get_reply_mode(user_message)
    
    if mode == "tarot":
        # 塔羅牌模式：顯示三張牌讓使用者選
        start_tarot_reading(event, user_id, user_message)
    elif mode == "text_only":
        # 純文字模式
        handle_text_only(event, user_message)
    else:
        # 完整圖文模式
        handle_full_mode(event, user_message)


def start_tarot_reading(event, user_id: str, question: str):
    """
    開始塔羅牌占卜：抽三張牌讓使用者選
    """
    # 抽三張牌
    cards = draw_three_cards()
    
    # 儲存使用者狀態
    # 移除關鍵字，保留問題本身
    clean_question = question
    for keyword in ["抽牌", "塔羅", "占卜", "抽籤", "抽卡"]:
        clean_question = clean_question.replace(keyword, "").strip()
    if not clean_question:
        clean_question = "我的運勢"
    
    user_states[user_id] = {
        "mode": "selecting",
        "question": clean_question,
        "cards": cards
    }
    
    # 建立選牌訊息
    reply_text = f"""🔮 塔羅牌占卜開始...

吾已為汝抽出三張命運之牌，請憑直覺選擇一張：

🃏 第一張牌
🃏 第二張牌  
🃏 第三張牌

請輸入「1」「2」或「3」選擇你的命運之牌。"""
    
    # 使用 Quick Reply 讓選擇更方便
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="🃏 第一張", text="1")),
        QuickReplyItem(action=MessageAction(label="🃏 第二張", text="2")),
        QuickReplyItem(action=MessageAction(label="🃏 第三張", text="3")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text, quick_reply=quick_reply)]
            )
        )


def handle_card_selection(event, user_id: str, selection: str):
    """
    處理使用者選牌
    """
    state = user_states.get(user_id)
    if not state:
        reply_simple(event, "請先輸入「占卜」開始抽牌。")
        return
    
    # 解析選擇
    try:
        choice = int(selection) - 1
        if choice < 0 or choice > 2:
            raise ValueError()
    except:
        reply_simple(event, "請輸入 1、2 或 3 來選擇牌。")
        return
    
    # 取得選中的牌
    selected_card = state["cards"][choice]
    question = state["question"]
    
    # 清除使用者狀態
    del user_states[user_id]
    
    # 呼叫 AI 解讀塔羅牌
    prompt = f"使用者的問題是：「{question}」\n抽到的塔羅牌是：「{selected_card}」\n請給予塔羅牌解讀。"
    
    ai_result = ask_openai(prompt, TAROT_SYSTEM_PROMPT)
    
    if ai_result is None:
        reply_simple(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    image_prompt = ai_result.get("image_prompt", "")
    
    # 加上牌面資訊
    full_reply = f"🎴 你選擇了第 {choice + 1} 張牌\n\n✨ 【{selected_card}】✨\n\n{text_reply}"
    
    # 生成圖片
    image_url = None
    if image_prompt:
        image_url = generate_image(image_prompt)
    
    reply_user(event.reply_token, full_reply, image_url)


def handle_text_only(event, user_message: str):
    """
    純文字模式（快速回覆）
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_simple(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    
    # 加上提示
    text_reply += "\n\n💡 想要附圖請說「要圖」，想抽塔羅牌請說「占卜」"
    
    reply_simple(event, text_reply)


def handle_full_mode(event, user_message: str):
    """
    完整圖文模式
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_simple(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    image_prompt = ai_result.get("image_prompt", "")
    
    image_url = None
    if image_prompt:
        image_url = generate_image(image_prompt)
    
    reply_user(event.reply_token, text_reply, image_url)


def reply_simple(event, text: str):
    """
    簡單文字回覆
    """
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)]
            )
        )


def reply_user(reply_token: str, text: str, image_url: str = None):
    """
    回傳訊息給 Line 使用者（支援圖片）
    """
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        
        messages = [TextMessage(text=text)]
        
        if image_url:
            messages.append(
                ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url
                )
            )
        
        try:
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
        except Exception as e:
            app.logger.error(f"回覆訊息失敗: {e}")


# ===== 健康檢查端點 =====
@app.route("/", methods=["GET"])
def health_check():
    return "🔮 AI 命理大師運行中..."


# ===== 啟動應用程式 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
