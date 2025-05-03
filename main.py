import os, requests
from flask import Flask
from linebot import LineBotApi
from linebot.models import TextSendMessage
from datetime import datetime
from bs4 import BeautifulSoup
import pytz

app = Flask(__name__)
line_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
USER_ID = os.getenv("TARGET_USER_ID")
TZ = pytz.timezone("Asia/Tokyo")

def check_boatrace_and_notify():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    url = "https://www.boatrace.jp/owpc/pc/race/pay"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    has_race = bool(soup.select_one(".is-race"))
    msg = f"{today} の競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")
    line_api.push_message(USER_ID, TextSendMessage(text=msg))

# 健康確認用（ヘルスチェックはこちらを叩いてもらう）
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

# 通知専用エンドポイント
@app.route("/notify", methods=["GET"])
def notify():
    check_boatrace_and_notify()
    return "Notified", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))