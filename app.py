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

━━━━ 熱門功能 ━━━━
⭐ 今日運勢 → 輸入「今日運勢」
🎰 抽籤詩 → 輸入「抽籤」
🎴 塔羅占卜 → 輸入「占卜」
🌙 解夢 → 輸入「解夢 夢境內容」

━━━━ 更多功能 ━━━━
♈ 星座運勢 → 輸入「牡羊座」
🐉 生肖運勢 → 輸入「屬龍」
💑 配對測試 → 輸入「配對」
📅 今日黃曆 → 輸入「黃曆」
🔢 數字占卜 → 輸入「數字 8」

❓ 完整說明 → 輸入「說明」
━━━━━━━━━━━━━━━━
施主有何疑惑，儘管道來。"""

# ===== 使用說明 =====
HELP_MESSAGE = """📖 【玄天上師】完整功能說明

━━━━ 每日必看 ━━━━
⭐ 今日運勢 → 「今日運勢」
📅 今日黃曆 → 「黃曆」
🎰 抽籤詩 → 「抽籤」

━━━━ 占卜問事 ━━━━
🎴 塔羅占卜 → 「占卜 問題」
🌙 周公解夢 → 「解夢 夢境」
🔢 數字占卜 → 「數字 幸運數字」
💑 速配測試 → 「配對 星座1 星座2」

━━━━ 星座生肖 ━━━━
♈ 星座運勢 → 直接輸入星座名
   例：「牡羊座」「獅子座」
🐉 生肖運勢 → 「屬X」
   例：「屬龍」「屬虎」

━━━━ 一般問答 ━━━━
🌟 直接提問 → 直接輸入問題
🖼️ 附圖回覆 → 「要圖 問題」
   ⚠️ 需等待 15-20 秒

━━━━━━━━━━━━━━━━
🆓 每日免費 3 次，明日重置
👑 VIP 無限使用

祝施主心想事成 🙏"""

# ===== 塔羅牌定義 =====
TAROT_CARDS = [
    "愚者", "魔術師", "女祭司", "皇后", "皇帝", "教皇", "戀人", "戰車",
    "力量", "隱者", "命運之輪", "正義", "倒吊人", "死神", "節制", "惡魔",
    "高塔", "星星", "月亮", "太陽", "審判", "世界"
]

# ===== 星座定義 =====
ZODIAC_SIGNS = [
    "牡羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", "處女座",
    "天秤座", "天蠍座", "射手座", "摩羯座", "水瓶座", "雙魚座"
]

# ===== 生肖定義 =====
CHINESE_ZODIAC = [
    "鼠", "牛", "虎", "兔", "龍", "蛇", "馬", "羊", "猴", "雞", "狗", "豬"
]

# ===== 籤詩定義（上上籤到下下籤）=====
FORTUNE_STICKS = [
    {"level": "上上籤", "poem": "龍飛鳳舞慶雲開，萬事如意福自來。貴人相助前程遠，心想事成不用猜。", "meaning": "大吉大利"},
    {"level": "上籤", "poem": "春風得意馬蹄輕，一日看盡長安花。機緣已到須把握，好運連連在眼前。", "meaning": "吉祥如意"},
    {"level": "中上籤", "poem": "雲開見月終有時，守得雲開見月明。耐心等待機緣到，水到渠成事可成。", "meaning": "穩中求進"},
    {"level": "中籤", "poem": "平穩安康度此生，不求大富但求寧。凡事隨緣莫強求，知足常樂是福音。", "meaning": "平安順遂"},
    {"level": "中下籤", "poem": "風雨飄搖路難行，前途未卜暫休征。靜待時機勿妄動，守成方是上上策。", "meaning": "宜靜不宜動"},
    {"level": "下籤", "poem": "烏雲蔽日暫無光，諸事不順心惶惶。退一步想海闊天，忍一時氣風平浪。", "meaning": "諸事小心"},
    {"level": "下下籤", "poem": "屋漏偏逢連夜雨，船遲又遇打頭風。暫避風頭求自保，待到雲開見日明。", "meaning": "謹慎行事"}
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

# 解夢 System Prompt
DREAM_PROMPT = """你是一位精通周公解夢的命理大師「玄天上師」。
使用者描述了他的夢境，請用玄學角度解析夢境含義。

回傳 JSON 格式：
{
  "dream_type": "夢境類型（如：吉夢、凶夢、警示夢、預兆夢）",
  "interpretation": "夢境解析（約100-150字），要有神祕感",
  "advice": "給使用者的建議（約30-50字）",
  "lucky_action": "化解或增運的行動建議"
}

請務必只回傳 JSON 格式。"""

# 星座運勢 System Prompt
ZODIAC_PROMPT = """你是一位精通西洋占星的命理大師「玄天上師」。
請為指定星座提供今日運勢。

回傳 JSON 格式：
{
  "overall": 整體運勢星數(1-5),
  "love": 愛情運星數(1-5),
  "career": 事業運星數(1-5),
  "wealth": 財運星數(1-5),
  "lucky_number": 幸運數字,
  "lucky_color": "幸運顏色",
  "advice": "今日星座運勢建議（約80-100字），要有神祕占星感"
}

請務必只回傳 JSON 格式。"""

# 生肖運勢 System Prompt  
CHINESE_ZODIAC_PROMPT = """你是一位精通中國傳統命理的大師「玄天上師」。
請為指定生肖提供今日運勢。

回傳 JSON 格式：
{
  "overall": 整體運勢星數(1-5),
  "wealth": 財運星數(1-5),
  "love": 桃花運星數(1-5),
  "health": 健康運星數(1-5),
  "lucky_direction": "吉利方位",
  "lucky_time": "吉時",
  "advice": "今日生肖運勢建議（約80-100字），要有古典命理感"
}

請務必只回傳 JSON 格式。"""

# 黃曆 System Prompt
ALMANAC_PROMPT = """你是一位精通中國傳統黃曆的命理大師「玄天上師」。
請為今日提供黃曆資訊。

回傳 JSON 格式：
{
  "suitable": ["宜做的事情1", "宜做的事情2", "宜做的事情3"],
  "avoid": ["忌做的事情1", "忌做的事情2", "忌做的事情3"],
  "lucky_god_direction": "財神方位",
  "clash": "今日沖什麼生肖",
  "advice": "今日黃曆總評（約50-80字）"
}

請務必只回傳 JSON 格式。"""

# 配對測試 System Prompt
MATCH_PROMPT = """你是一位精通星座配對的命理大師「玄天上師」。
請分析兩個星座的速配指數。

回傳 JSON 格式：
{
  "match_score": 速配指數(1-100),
  "love_score": 愛情契合度(1-100),
  "friend_score": 友情契合度(1-100),
  "work_score": 工作契合度(1-100),
  "analysis": "配對分析（約100-150字），包含優點和需要注意的地方",
  "advice": "給這對組合的建議（約50字）"
}

請務必只回傳 JSON 格式。"""

# 數字占卜 System Prompt
NUMBER_PROMPT = """你是一位精通數字命理的大師「玄天上師」。
請根據使用者提供的數字進行占卜分析。

回傳 JSON 格式：
{
  "number_meaning": "這個數字的命理含義（約50字）",
  "energy": "數字能量屬性（如：陽剛、陰柔、中和）",
  "fortune": "這個數字帶來的運勢（約80-100字）",
  "advice": "使用這個數字的建議（約30-50字）",
  "lucky_day": "適合使用這個數字的日子"
}

請務必只回傳 JSON 格式。"""

# ===== 錯誤回覆訊息 =====
ERROR_MESSAGE = "🔮 天機訊號干擾中，請稍後再試。"

# ===== 使用者狀態儲存 =====
user_states = {}

# ===== 每日使用次數限制 =====
DAILY_FREE_LIMIT = 3  # 每日免費次數
user_usage = {}  # {user_id: {"date": "2024-02-01", "count": 3}}

# ===== VIP 白名單（無限使用）=====
VIP_USERS = [
    "Udeaa0f5c895dab6687136227a44e0c0a",  # 管理員
]

def check_usage_limit(user_id: str) -> tuple:
    """
    檢查使用者是否超過每日限制
    Returns: (是否可用, 剩餘次數, 是否VIP)
    """
    # VIP 用戶無限使用
    if user_id in VIP_USERS:
        return (True, 999, True)
    
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
    return (remaining > 0, remaining, False)

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

━━━━━━━━━━━━━━━━
💰 加購方案

💎 單次加購：$10 / 次
🌟 VIP 無限：$199 / 月

━━━━━━━━━━━━━━━━
📱 付款方式

請私訊管理員購買：
👉 [付款連結或聯絡方式]

付款後請提供您的 Line 名稱，
我們將於 24 小時內開通。

━━━━━━━━━━━━━━━━
🌙 或等待明日 00:00 重置免費次數

📌 輸入「說明」查看免費功能
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


def get_reply_mode(message: str) -> tuple:
    """
    判斷使用者要的回覆模式
    Returns: (mode, extra_data)
    """
    # 說明/幫助
    if any(keyword in message for keyword in ["說明", "幫助", "help", "指令", "怎麼用"]):
        return ("help", None)
    
    # 每日幸運指數
    if any(keyword in message for keyword in ["今日運勢", "今天運勢", "每日運勢", "今天運氣", "幸運指數"]):
        return ("daily_fortune", None)
    
    # 抽籤詩
    if any(keyword in message for keyword in ["抽籤", "求籤", "籤詩", "抽個籤"]):
        return ("fortune_stick", None)
    
    # 黃曆
    if any(keyword in message for keyword in ["黃曆", "黃歷", "宜忌", "今日宜"]):
        return ("almanac", None)
    
    # 解夢
    if "解夢" in message:
        dream_content = message.replace("解夢", "").strip()
        return ("dream", dream_content if dream_content else None)
    
    # 配對測試
    if any(keyword in message for keyword in ["配對", "速配", "合不合"]):
        return ("match", message)
    
    # 數字占卜
    if "數字" in message:
        # 嘗試提取數字
        numbers = re.findall(r'\d+', message)
        return ("number", numbers[0] if numbers else None)
    
    # 星座運勢
    for sign in ZODIAC_SIGNS:
        if sign in message:
            return ("zodiac", sign)
    
    # 生肖運勢
    for zodiac in CHINESE_ZODIAC:
        if f"屬{zodiac}" in message or zodiac == message:
            return ("chinese_zodiac", zodiac)
    
    # 塔羅牌模式
    if any(keyword in message for keyword in ["抽牌", "塔羅", "占卜", "抽卡"]):
        return ("tarot", message)
    
    # 圖文模式
    if any(keyword in message for keyword in ["要圖", "圖文", "完整", "附圖"]):
        return ("full", message)
    
    # 預設：純文字（較快）
    return ("text_only", message)


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


def ask_ai_simple(prompt: str, system_prompt: str) -> dict:
    """
    通用 AI 呼叫函數
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        cleaned_text = re.sub(r'^```json\s*', '', response_text)
        cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
        
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI 錯誤: {e}")
        return None


def get_remaining_text(remaining: int, is_vip: bool) -> str:
    """
    取得剩餘次數文字
    """
    if is_vip:
        return "\n\n━━━━━━━━━━━━━━━━\n👑 VIP 無限使用中"
    else:
        return f"\n\n━━━━━━━━━━━━━━━━\n📊 今日剩餘免費次數：{remaining} 次"


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
    mode, extra_data = get_reply_mode(user_message)
    
    # 免費功能（不計次數）
    if mode == "help":
        reply_with_quick_actions(event, HELP_MESSAGE)
        return
    
    # 付費功能（檢查次數限制）
    can_use, remaining, is_vip = check_usage_limit(user_id)
    
    if not can_use:
        # 超過限制，顯示提示
        reply_with_quick_actions(event, LIMIT_MESSAGE)
        return
    
    # VIP 用戶不計次數，一般用戶增加次數
    if not is_vip:
        increment_usage(user_id)
        remaining = remaining - 1
    
    # 執行功能
    if mode == "daily_fortune":
        handle_daily_fortune(event, remaining, is_vip)
    elif mode == "fortune_stick":
        handle_fortune_stick(event, remaining, is_vip)
    elif mode == "almanac":
        handle_almanac(event, remaining, is_vip)
    elif mode == "dream":
        handle_dream(event, extra_data, remaining, is_vip)
    elif mode == "zodiac":
        handle_zodiac(event, extra_data, remaining, is_vip)
    elif mode == "chinese_zodiac":
        handle_chinese_zodiac(event, extra_data, remaining, is_vip)
    elif mode == "match":
        handle_match(event, extra_data, remaining, is_vip)
    elif mode == "number":
        handle_number(event, extra_data, remaining, is_vip)
    elif mode == "tarot":
        start_tarot_reading(event, user_id, user_message, remaining, is_vip)
    elif mode == "full":
        handle_full_mode(event, user_message, remaining, is_vip)
    else:
        handle_text_only(event, user_message, remaining, is_vip)


def handle_daily_fortune(event, remaining: int = 0, is_vip: bool = False):
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

⚠️ {fortune.get('warning', '避免衝動行事')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    
    # 加上快速操作按鈕
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="🎰 抽籤", text="抽籤")),
        QuickReplyItem(action=MessageAction(label="🎴 塔羅", text="占卜")),
        QuickReplyItem(action=MessageAction(label="📅 黃曆", text="黃曆")),
        QuickReplyItem(action=MessageAction(label="🌙 解夢", text="解夢 ")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text, quick_reply=quick_reply)]
            )
        )


def handle_fortune_stick(event, remaining: int = 0, is_vip: bool = False):
    """
    抽籤詩功能
    """
    # 隨機抽一支籤
    stick = random.choice(FORTUNE_STICKS)
    
    reply_text = f"""🎰 【籤詩結果】

━━━━━━━━━━━━━━━━
📜 {stick['level']}

「{stick['poem']}」

━━━━━━━━━━━━━━━━
🔮 籤意：{stick['meaning']}

💡 此籤主{stick['meaning']}，
施主宜順應天時，把握當下。"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_almanac(event, remaining: int = 0, is_vip: bool = False):
    """
    今日黃曆
    """
    from datetime import datetime
    today = datetime.now().strftime("%m月%d日")
    
    result = ask_ai_simple(f"請提供今天（{today}）的黃曆", ALMANAC_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    suitable = "、".join(result.get('suitable', ['諸事皆宜']))
    avoid = "、".join(result.get('avoid', ['無']))
    
    reply_text = f"""📅 【{today} 黃曆】

━━━━ 今日宜 ━━━━
✅ {suitable}

━━━━ 今日忌 ━━━━
❌ {avoid}

━━━━ 吉神方位 ━━━━
💰 財神：{result.get('lucky_god_direction', '東方')}
⚠️ 沖：{result.get('clash', '雞')}

━━━━ 黃曆總評 ━━━━
📝 {result.get('advice', '今日平順，諸事可為。')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_dream(event, dream_content: str, remaining: int = 0, is_vip: bool = False):
    """
    解夢功能
    """
    if not dream_content:
        reply_with_quick_actions(event, "🌙 請告訴我你的夢境內容\n\n例如：解夢 我夢到在飛")
        return
    
    result = ask_ai_simple(f"夢境內容：{dream_content}", DREAM_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    reply_text = f"""🌙 【周公解夢】

━━━━ 夢境類型 ━━━━
🏷️ {result.get('dream_type', '預兆夢')}

━━━━ 夢境解析 ━━━━
🔮 {result.get('interpretation', '此夢意涵深遠...')}

━━━━ 大師建議 ━━━━
💡 {result.get('advice', '順其自然，靜觀其變。')}

✨ 開運行動：{result.get('lucky_action', '多行善事')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_zodiac(event, sign: str, remaining: int = 0, is_vip: bool = False):
    """
    星座運勢
    """
    from datetime import datetime
    today = datetime.now().strftime("%m/%d")
    
    result = ask_ai_simple(f"請提供{sign}今日運勢", ZODIAC_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    reply_text = f"""♈ 【{sign} {today} 運勢】

━━━━ 運勢指數 ━━━━
✨ 整體運勢：{format_stars(result.get('overall', 3))}
💕 愛情運勢：{format_stars(result.get('love', 3))}
💼 事業運勢：{format_stars(result.get('career', 3))}
💰 財運指數：{format_stars(result.get('wealth', 3))}

━━━━ 幸運密碼 ━━━━
🔢 幸運數字：{result.get('lucky_number', 7)}
🎨 幸運顏色：{result.get('lucky_color', '金色')}

━━━━ 今日提醒 ━━━━
💡 {result.get('advice', '今日運勢平穩。')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_chinese_zodiac(event, zodiac: str, remaining: int = 0, is_vip: bool = False):
    """
    生肖運勢
    """
    from datetime import datetime
    today = datetime.now().strftime("%m/%d")
    
    result = ask_ai_simple(f"請提供生肖{zodiac}今日運勢", CHINESE_ZODIAC_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    reply_text = f"""🐉 【生肖{zodiac} {today} 運勢】

━━━━ 運勢指數 ━━━━
✨ 整體運勢：{format_stars(result.get('overall', 3))}
💰 財運指數：{format_stars(result.get('wealth', 3))}
💕 桃花運勢：{format_stars(result.get('love', 3))}
💪 健康運勢：{format_stars(result.get('health', 3))}

━━━━ 吉利方位 ━━━━
🧭 吉方：{result.get('lucky_direction', '東方')}
⏰ 吉時：{result.get('lucky_time', '午時')}

━━━━ 今日提醒 ━━━━
💡 {result.get('advice', '今日運勢平穩。')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_match(event, message: str, remaining: int = 0, is_vip: bool = False):
    """
    配對測試
    """
    # 嘗試從訊息中提取兩個星座
    found_signs = []
    for sign in ZODIAC_SIGNS:
        if sign in message:
            found_signs.append(sign)
    
    if len(found_signs) < 2:
        reply_text = """💑 【星座配對測試】

請輸入兩個星座，例如：
• 配對 牡羊座 天秤座
• 獅子座配雙子座"""
        reply_with_quick_actions(event, reply_text)
        return
    
    sign1, sign2 = found_signs[0], found_signs[1]
    
    result = ask_ai_simple(f"請分析{sign1}和{sign2}的速配指數", MATCH_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    match_score = result.get('match_score', 75)
    
    # 根據分數給予評價
    if match_score >= 90:
        rating = "天作之合 💕"
    elif match_score >= 75:
        rating = "相當契合 💗"
    elif match_score >= 60:
        rating = "小有默契 💓"
    elif match_score >= 40:
        rating = "需要磨合 💔"
    else:
        rating = "挑戰重重 🖤"
    
    reply_text = f"""💑 【{sign1} ✕ {sign2} 配對分析】

━━━━ 速配指數 ━━━━
💘 總體速配：{match_score}分 {rating}
💕 愛情契合：{result.get('love_score', 70)}分
🤝 友情契合：{result.get('friend_score', 70)}分
💼 工作契合：{result.get('work_score', 70)}分

━━━━ 配對分析 ━━━━
📝 {result.get('analysis', '這對組合...')}

━━━━ 相處建議 ━━━━
💡 {result.get('advice', '互相尊重是關鍵。')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def handle_number(event, number: str, remaining: int = 0, is_vip: bool = False):
    """
    數字占卜
    """
    if not number:
        reply_text = """🔢 【數字占卜】

請提供一個數字，例如：
• 數字 7
• 數字 88
• 數字 168"""
        reply_with_quick_actions(event, reply_text)
        return
    
    result = ask_ai_simple(f"請分析數字 {number} 的命理含義", NUMBER_PROMPT)
    
    if result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    reply_text = f"""🔢 【數字 {number} 命理解析】

━━━━ 數字含義 ━━━━
📖 {result.get('number_meaning', '這個數字...')}

━━━━ 能量屬性 ━━━━
⚡ {result.get('energy', '中和')}

━━━━ 運勢分析 ━━━━
🔮 {result.get('fortune', '此數帶來...')}

━━━━ 使用建議 ━━━━
💡 {result.get('advice', '可多使用此數字。')}
📅 適用日：{result.get('lucky_day', '每日皆可')}"""
    
    reply_text += get_remaining_text(remaining, is_vip)
    reply_with_quick_actions(event, reply_text)


def reply_with_quick_actions(event, text: str):
    """
    回覆訊息並附上快速操作按鈕
    """
    quick_reply = QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="⭐ 今日運勢", text="今日運勢")),
        QuickReplyItem(action=MessageAction(label="🎰 抽籤", text="抽籤")),
        QuickReplyItem(action=MessageAction(label="🎴 塔羅", text="占卜")),
        QuickReplyItem(action=MessageAction(label="📅 黃曆", text="黃曆")),
    ])
    
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text, quick_reply=quick_reply)]
            )
        )


def start_tarot_reading(event, user_id: str, question: str, remaining: int = 0, is_vip: bool = False):
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
        "remaining": remaining,
        "is_vip": is_vip
    }
    
    reply_text = """🔮 塔羅牌占卜開始...

吾已為汝抽出三張命運之牌，
請閉眼深呼吸，憑直覺選擇：

  🃏        🃏        🃏
第一張    第二張    第三張

請選擇你的命運之牌 ⬇️"""
    
    if is_vip:
        reply_text += "\n\n👑 VIP 無限使用中"
    else:
        reply_text += f"\n\n📊 今日剩餘免費次數：{remaining} 次"
    
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


def handle_text_only(event, user_message: str, remaining: int = 0, is_vip: bool = False):
    """
    純文字模式（快速回覆）
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    
    if is_vip:
        text_reply += "\n\n━━━━━━━━━━━━━━━━\n👑 VIP 無限使用中"
    else:
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


def handle_full_mode(event, user_message: str, remaining: int = 0, is_vip: bool = False):
    """
    完整圖文模式
    """
    ai_result = ask_openai(user_message)
    
    if ai_result is None:
        reply_with_quick_actions(event, ERROR_MESSAGE)
        return
    
    text_reply = ai_result.get("reply", ERROR_MESSAGE)
    
    if is_vip:
        text_reply += "\n\n━━━━━━━━━━━━━━━━\n👑 VIP 無限使用中"
    else:
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
