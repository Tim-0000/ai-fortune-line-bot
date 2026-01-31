# -*- coding: utf-8 -*-
"""
AI 命理大師 Line Bot
整合 OpenAI GPT + Replicate 圖片生成
"""

import os
import json
import re
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
    ImageMessage
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

# 設定命理大師的 System Prompt
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

# ===== 錯誤回覆訊息 =====
ERROR_MESSAGE = "🔮 天機訊號干擾中，請稍後再試。"


def ask_openai(user_message: str) -> dict:
    """
    呼叫 OpenAI GPT 生成命理回覆與圖片提示詞
    
    Args:
        user_message: 使用者的問題
    
    Returns:
        dict: 包含 reply (中文回覆) 和 image_prompt (英文提示詞)
    """
    try:
        # 發送訊息給 OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # 嘗試解析 JSON（處理可能的 markdown 格式）
        # 移除可能的 ```json 和 ``` 標記
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
    
    Args:
        prompt: 英文圖片提示詞
    
    Returns:
        str: 生成的圖片 URL，失敗則回傳 None
    """
    try:
        # 設定 Replicate API Token
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
        
        # 呼叫 SDXL 模型生成圖片
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
        
        # output 是一個列表，取第一張圖片的 URL
        if output and len(output) > 0:
            return output[0]
        return None
    
    except Exception as e:
        print(f"Replicate 錯誤: {e}")
        return None


# ===== Line Webhook 端點 =====
@app.route("/callback", methods=["POST"])
def callback():
    """
    Line Webhook 回呼端點
    驗證簽章並處理訊息事件
    """
    # 取得 X-Line-Signature 標頭
    signature = request.headers.get("X-Line-Signature", "")
    
    # 取得請求內容
    body = request.get_data(as_text=True)
    app.logger.info(f"收到請求: {body}")
    
    # 驗證簽章並處理事件
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
    1. 接收使用者訊息
    2. 呼叫 OpenAI 生成回覆和圖片提示詞
    3. 呼叫 Replicate 生成圖片
    4. 回傳文字 + 圖片給使用者
    """
    # 取得使用者傳送的文字
    user_message = event.message.text
    app.logger.info(f"使用者訊息: {user_message}")
    
    # 呼叫 OpenAI 取得回覆
    ai_result = ask_openai(user_message)
    
    # 如果 OpenAI 失敗，回傳錯誤訊息
    if ai_result is None:
        reply_user(event.reply_token, ERROR_MESSAGE, None)
        return
    
    # 取得文字回覆和圖片提示詞
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    image_prompt = ai_result.get("image_prompt", "")
    
    app.logger.info(f"AI 回覆: {text_reply}")
    app.logger.info(f"圖片提示詞: {image_prompt}")
    
    # 呼叫 Replicate 生成圖片
    image_url = None
    if image_prompt:
        image_url = generate_image(image_prompt)
        app.logger.info(f"生成圖片 URL: {image_url}")
    
    # 回傳訊息給使用者
    reply_user(event.reply_token, text_reply, image_url)


def reply_user(reply_token: str, text: str, image_url: str = None):
    """
    回傳訊息給 Line 使用者
    
    Args:
        reply_token: Line 回覆 token
        text: 文字訊息
        image_url: 圖片 URL（可選）
    """
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        
        # 準備訊息列表
        messages = [TextMessage(text=text)]
        
        # 如果有圖片 URL，加入圖片訊息
        if image_url:
            messages.append(
                ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url
                )
            )
        
        # 發送回覆
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
    """
    健康檢查端點，用於確認服務運行狀態
    """
    return "🔮 AI 命理大師運行中..."


# ===== 啟動應用程式 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
