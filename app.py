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
    QuickReply,
    QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)
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

# ===== 歡迎訊息 =====
WELCOME_MESSAGE = """🔮 歡迎來到【玄天上師】命理殿堂

吾乃玄天上師，專為有緣人解惑指引。

━━━━━━━━━━━━━━━━
📖 使用方式：

⭐ 今日運勢（每日必看）
   → 今日運勢

🌟 直接提問（快速回覆）
   → 我最近財運如何？

🎴 塔羅占卜（抽牌互動）
   → 占卜 感情運勢

🖼️ 附圖回覆（較慢）
   → 要圖 事業運勢

❓ 查看說明 → 說明
━━━━━━━━━━━━━━━━

施主有何疑惑，儘管道來。"""

# ===== 使用說明 =====
HELP_MESSAGE = """📖 【玄天上師】使用說明

━━━━━━━━━━━━━━━━
⭐ 每日幸運指數（秒回！）
輸入「今日運勢」獲得：
• 今日幸運指數 ⭐⭐⭐⭐⭐
• 幸運數字 & 幸運顏色
• 每日開運小提醒

━━━━━━━━━━━━━━━━
🌟 一般問命（純文字，秒回）
直接輸入問題即可：
• 我最近運勢如何？
• 感情方面有什麼建議？

━━━━━━━━━━━━━━━━
🎴 塔羅牌占卜（抽牌互動）
輸入「占卜」+問題：
• 占卜 我的感情運
• 抽牌

━━━━━━━━━━━━━━━━
🖼️ 圖文模式（附 AI 繪圖）
輸入「要圖」+問題：
• 要圖 我的財運
⚠️ 需等待 15-20 秒

━━━━━━━━━━━━━━━━
祝施主心想事成 🙏"""

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

# 每日幸運指數 System Prompt
DAILY_FORTUNE_PROMPT = """你是一位神祕的命理大師「玄天上師」，現在要為使用者提供今日運勢。

請根據當下的時間能量，為使用者生成今日運勢。你必須回傳一個 JSON 格式，包含以下欄位：
1. "overall_stars": 整體運勢星數（1-5的整數）
2. "love_stars": 感情運星數（1-5的整數）
3. "wealth_stars": 財運星數（1-5的整數）
4. "work_stars": 事業運星數（1-5的整數）
5. "lucky_number": 幸運數字（1-99之間）
6. "lucky_color": 幸運顏色（繁體中文，如：金色、紫色、天藍色）
7. "lucky_direction": 幸運方位（如：東方、西南方）
8. "advice": 今日開運提醒（約50-80字，要有神祕感和智慧感，給予具體建議）
9. "warning": 今日注意事項（約20-30字，提醒要避免的事情）

範例輸出格式：
{
  "overall_stars": 4,
  "love_stars": 5,
  "wealth_stars": 3,
  "work_stars": 4,
  "lucky_number": 7,
  "lucky_color": "金色",
  "lucky_direction": "東方",
  "advice": "今日紫氣東來，適合主動出擊...",
  "warning": "避免與人爭執，退一步海闊天空"
}

請務必只回傳 JSON 格式，不要有其他文字。每次生成的內容都要不同，有變化。"""

# ===== 錯誤回覆訊息 =====
ERROR_MESSAGE = "🔮 天機訊號干擾中，請稍後再試。"

# ===== 使用者狀態儲存 =====
user_states = {}

# ===== 每日使用次數限制 =====
DAILY_FREE_LIMIT = 3  # 每日免費次數
user_usage = {}  # {user_id: {"date": "2024-02-01", "count": 3}}

def check_usage_limit(user_id: str) -> tuple:
    """
    檢查使用者是否超過每日限制
    Returns: (是否可用, 剩餘次數)
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in user_usage:
        user_usage[user_id] = {"date": today, "count": 0}
    
    user_data = user_usage[user_id]
    
    # 如果是新的一天，重置次數
    if user_data["date"] != today:
        user_usage[user_id] = {"date": today, "count": 0}
        user_data = user_usage[user_id]
    
    remaining = DAILY_FREE_LIMIT - user_data["count"]
    return (remaining > 0, remaining)

def increment_usage(user_id: str):
    """
    增加使用者的使用次數
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in user_usage:
        user_usage[user_id] = {"date": today, "count": 0}
    
    if user_usage[user_id]["date"] != today:
        user_usage[user_id] = {"date": today, "count": 0}
    
    user_usage[user_id]["count"] += 1

# 超過限制的提示訊息
LIMIT_MESSAGE = """⚠️ 今日免費次數已用完

施主今日的 3 次免費問卜已使用完畢。

🌙 明日子時（00:00）將重置次數

━━━━━━━━━━━━━━━━
💎 想要無限使用？

未來將開放 VIP 訂閱方案，
敬請期待！

━━━━━━━━━━━━━━━━
📌 免費功能仍可使用：
• 查看說明 → 輸入「說明」
"""


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
    # 說明/幫助
    if any(keyword in message for keyword in ["說明", "幫助", "help", "指令", "怎麼用"]):
        return "help"
    
    # 每日幸運指數
    if any(keyword in message for keyword in ["今日運勢", "今天運勢", "每日運勢", "今日", "今天運氣", "幸運指數"]):
        return "daily_fortune"
    
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


def get_daily_fortune() -> dict:
    """
    呼叫 OpenAI 生成每日幸運指數
    """
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y年%m月%d日")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DAILY_FORTUNE_PROMPT},
                {"role": "user", "content": f"請為今天（{today}）生成運勢"}
            ],
            temperature=0.9,
            max_tokens=400
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # 解析 JSON
        cleaned_text = re.sub(r'^```json\s*', '', response_text)
        cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
        
        result = json.loads(cleaned_text)
        return result
    
    except Exception as e:
        print(f"每日運勢錯誤: {e}")
        return None


def format_stars(count: int) -> str:
    """
    將數字轉換成星星符號
    """
    return "⭐" * count + "☆" * (5 - count)


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


# ===== 歡迎訊息（加入好友時觸發）=====
@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """
    當使用者加入好友時，發送歡迎訊息
    """
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=WELCOME_MESSAGE)]
            )
        )


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
    
    # 免費功能（不計次數）
    if mode == "help":
        reply_with_quick_actions(event, HELP_MESSAGE)
        return
    
    # 付費功能（檢查次數限制）
    can_use, remaining = check_usage_limit(user_id)
    
    if not can_use:
        # 超過限制，顯示提示
        reply_with_quick_actions(event, LIMIT_MESSAGE)
        return
    
    # 執行功能並增加使用次數
    if mode == "daily_fortune":
        increment_usage(user_id)
        handle_daily_fortune(event, remaining - 1)
    elif mode == "tarot":
        increment_usage(user_id)
        start_tarot_reading(event, user_id, user_message, remaining - 1)
    elif mode == "text_only":
        increment_usage(user_id)
        handle_text_only(event, user_message, remaining - 1)
    else:
        increment_usage(user_id)
        handle_full_mode(event, user_message, remaining - 1)


def handle_daily_fortune(event, remaining: int = 0):
    """
    處理每日幸運指數
    """
    from datetime import datetime
    today = datetime.now().strftime("%m/%d")
    
    fortune = get_daily_fortune()
    
    if fortune is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    # 格式化回覆
    reply_text = f"""🌅 【{today} 今日運勢】

━━━━ 運勢指數 ━━━━
✨ 整體運勢：{format_stars(fortune.get('overall_stars', 3))}
💕 感情運勢：{format_stars(fortune.get('love_stars', 3))}
💰 財運指數：{format_stars(fortune.get('wealth_stars', 3))}
💼 事業運勢：{format_stars(fortune.get('work_stars', 3))}

━━━━ 幸運密碼 ━━━━
🔢 幸運數字：{fortune.get('lucky_number', 7)}
🎨 幸運顏色：{fortune.get('lucky_color', '金色')}
🧭 幸運方位：{fortune.get('lucky_direction', '東方')}

━━━━ 今日提醒 ━━━━
💡 {fortune.get('advice', '今日宜靜心養氣，待機而動。')}

⚠️ {fortune.get('warning', '避免衝動行事')}

━━━━━━━━━━━━━━━━
📊 今日剩餘免費次數：{remaining} 次"""
    
    # 加上快速操作按鈕
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="🎴 塔羅占卜", text="占卜")),
        QuickReplyItem(action=MessageAction(label="💰 問財運", text="我的財運如何？")),
        QuickReplyItem(action=MessageAction(label="💕 問感情", text="我的感情運如何？")),
        QuickReplyItem(action=MessageAction(label="💼 問事業", text="我的事業運如何？")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text, quick_reply=quick_reply)]
            )
        )


def reply_with_quick_actions(event, text: str):
    """
    回覆訊息並附上快速操作按鈕
    """
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="⭐ 今日運勢", text="今日運勢")),
        QuickReplyItem(action=MessageAction(label="🎴 塔羅占卜", text="占卜")),
        QuickReplyItem(action=MessageAction(label="💰 問財運", text="我的財運如何？")),
        QuickReplyItem(action=MessageAction(label="💕 問感情", text="我的感情運如何？")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text, quick_reply=quick_reply)]
            )
        )


def start_tarot_reading(event, user_id: str, question: str, remaining: int = 0):
    """
    開始塔羅牌占卜：抽三張牌讓使用者選
    """
    cards = draw_three_cards()
    
    # 清理問題
    clean_question = question
    for keyword in ["抽牌", "塔羅", "占卜", "抽籤", "抽卡"]:
        clean_question = clean_question.replace(keyword, "").strip()
    if not clean_question:
        clean_question = "我的運勢"
    
    user_states[user_id] = {
        "mode": "selecting",
        "question": clean_question,
        "cards": cards,
        "remaining": remaining
    }
    
    reply_text = f"""🔮 塔羅牌占卜開始...

吾已為汝抽出三張命運之牌，
請閉眼深呼吸，憑直覺選擇：

  🃏        🃏        🃏
第一張    第二張    第三張

請選擇你的命運之牌 ⬇️

📊 今日剩餘免費次數：{remaining} 次"""
    
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
        reply_with_quick_actions(event, "請先輸入「占卜」開始抽牌。")
        return
    
    try:
        choice = int(selection) - 1
        if choice < 0 or choice > 2:
            raise ValueError()
    except:
        # 如果輸入不是 1-3，給予提示
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
                    messages=[TextMessage(text="請點選下方按鈕選擇牌 ⬇️", quick_reply=quick_reply)]
                )
            )
        return
    
    selected_card = state["cards"][choice]
    question = state["question"]
    
    del user_states[user_id]
    
    # AI 解讀
    prompt = f"使用者的問題是：「{question}」\n抽到的塔羅牌是：「{selected_card}」\n請給予塔羅牌解讀。"
    ai_result = ask_openai(prompt, TAROT_SYSTEM_PROMPT)
    
    if ai_result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    image_prompt = ai_result.get("image_prompt", "")
    
    full_reply = f"""🎴 你選擇了第 {choice + 1} 張牌

✨ 【{selected_card}】✨

{text_reply}

━━━━━━━━━━━━━━━━
🔮 想再次占卜請輸入「占卜」"""
    
    image_url = None
    if image_prompt:
        image_url = generate_image(image_prompt)
    
    reply_user(event.reply_token, full_reply, image_url)


def handle_text_only(event, user_message: str, remaining: int = 0):
    """
    純文字模式（快速回覆）
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    text_reply += f"\n\n━━━━━━━━━━━━━━━━\n📊 今日剩餘免費次數：{remaining} 次"
    
    # 加上快速操作
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="⭐ 今日運勢", text="今日運勢")),
        QuickReplyItem(action=MessageAction(label="🎴 塔羅占卜", text="占卜")),
        QuickReplyItem(action=MessageAction(label="🖼️ 附圖回覆", text=f"要圖 {user_message}")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text_reply, quick_reply=quick_reply)]
            )
        )


def handle_full_mode(event, user_message: str, remaining: int = 0):
    """
    完整圖文模式
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    text_reply += f"\n\n━━━━━━━━━━━━━━━━\n📊 今日剩餘免費次數：{remaining} 次"
    
    image_prompt = ai_result.get("image_prompt", "")
    
    image_url = None
    if image_prompt:
        image_url = generate_image(image_prompt)
    
    reply_user(event.reply_token, text_reply, image_url)


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
