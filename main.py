import os, logging, requests
from flask import Flask
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError
from datetime import datetime
from bs4 import BeautifulSoup
import pytz

app = Flask(__name__)

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO)

# --- LINE 設定 ---
line_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
USER_ID   = os.getenv("TARGET_USER_ID")

# --- タイムゾーン ---
TZ = pytz.timezone("Asia/Tokyo")

# --- メイン処理 ---
def check_boatrace_and_notify():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    url   = "https://www.boatrace.jp/owpc/pc/race/pay"
    res   = requests.get(url, timeout=10)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    # 「福岡」がページテキストに含まれるか
    has_race = "福岡" in soup.get_text()

    msg = f"{today} の福岡競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")

    try:
        line_api.push_message(USER_ID, TextSendMessage(text=msg))
        app.logger.info("LINE push OK")
    except LineBotApiError as e:
        app.logger.error(f"LINE push failed {e.status_code}: {e.error.message}")

# --- ルート ---
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/notify", methods=["GET"])
def notify():
    check_boatrace_and_notify()
    return "Notified", 200

# --- ローカル実行用 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))