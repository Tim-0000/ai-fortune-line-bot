# 🔮 AI 命理大師 Line Bot

一個整合 Gemini AI + Replicate 圖片生成的神祕命理 Line Bot。

## 功能特色

- 使用 **Gemini 1.5 Flash** 生成神祕風格的命理回覆
- 使用 **Replicate SDXL** 生成對應意境的圖片
- 一次回傳文字 + 圖片，帶來完整體驗

## 專案結構

```
Line/
├── app.py              # 主程式
├── requirements.txt    # Python 依賴套件
├── .env               # 環境變數（請勿上傳 Git）
├── Procfile           # Render 部署設定
└── README.md          # 說明文件
```

## 環境變數設定

在 `.env` 檔案中填入以下 API 金鑰：

| 變數名稱 | 來源 |
|---------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | [Line Developers Console](https://developers.line.biz/) |
| `LINE_CHANNEL_SECRET` | [Line Developers Console](https://developers.line.biz/) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) |
| `REPLICATE_API_TOKEN` | [Replicate](https://replicate.com/account/api-tokens) |

## 本機測試

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 啟動服務
python app.py

# 3. 使用 ngrok 建立公開網址（另開終端機）
ngrok http 5000
```

將 ngrok 產生的 HTTPS 網址設定到 Line Developers Console 的 Webhook URL：
```
https://xxxx.ngrok.io/callback
```

## 部署到 Render

### 步驟 1：準備程式碼

將專案上傳到 GitHub（記得將 `.env` 加入 `.gitignore`）。

### 步驟 2：建立 Render 服務

1. 前往 [Render Dashboard](https://dashboard.render.com/)
2. 點選 **New** → **Web Service**
3. 連結你的 GitHub Repo
4. 設定：
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### 步驟 3：設定環境變數

在 Render 的 **Environment** 區塊加入：
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `GEMINI_API_KEY`
- `REPLICATE_API_TOKEN`

### 步驟 4：設定 Line Webhook

部署完成後，將 Render 提供的網址設定到 Line Developers Console：
```
https://你的服務名稱.onrender.com/callback
```

## 使用方式

加入 Line Bot 好友後，直接傳送問題即可：

- 「我最近財運如何？」
- 「感情方面有什麼建議？」
- 「今年事業運勢怎麼樣？」

Bot 會回傳神祕的命理解答 + 一張對應意境的圖片。

## 注意事項

- Replicate 需要付費帳號才能穩定使用
- 圖片生成需要約 10-20 秒，請耐心等待
- Line 的 Reply Token 有效期限為 30 秒

## 授權

MIT License
