import os
import logging
import time
from datetime import datetime

import pytz
import requests
from bs4 import BeautifulSoup
from flask import Flask
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ────────────────────────────────────────
#  Flask app
# ────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ────────────────────────────────────────
#  LINE credentials
# ────────────────────────────────────────
line_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
USER_ID = os.getenv("TARGET_USER_ID")

# ────────────────────────────────────────
#  Timezone
# ────────────────────────────────────────
TZ = pytz.timezone("Asia/Tokyo")

# ────────────────────────────────────────
#  Retry‑enabled requests session
# ────────────────────────────────────────
def requests_retry_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (500, 502, 504),
    session: requests.Session | None = None,
) -> requests.Session:
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session

# ────────────────────────────────────────
#  Helper: detect '福岡' in text or attributes
# ────────────────────────────────────────
def has_fukuoka(soup: BeautifulSoup) -> bool:
    """ページのテキスト or src/alt/title 属性に '福岡' を含むか"""
    # テキストノード
    if soup.find(string=lambda t: "福岡" in t):
        return True
    # src・alt・title 属性
    if soup.select_one('[src*="福岡"], [alt*="福岡"], [title*="福岡"]'):
        return True
    return False

# ────────────────────────────────────────
#  Main logic
# ────────────────────────────────────────
def check_boatrace_and_notify() -> None:
    today_human = datetime.now(TZ).strftime("%Y-%m-%d")   # 2025‑05‑03
    url = "https://www.boatrace.jp/owpc/pc/race/pay"

    try:
        res = requests_retry_session().get(url, timeout=30)
        res.raise_for_status()
    except Exception as e:
        app.logger.error(f"scraping failed: {type(e).__name__} {e}")
        return

    soup = BeautifulSoup(res.text, "html.parser")
    has_race = has_fukuoka(soup)

    # ── 30 分以内の重複送信を抑止 ──
    cache_path = "/tmp/boat_cache.txt"
    msg_state = "1" if has_race else "0"
    if os.path.exists(cache_path):
        last, ts = open(cache_path).read().split(",")
        if last == msg_state and (time.time() - float(ts) < 1800):
            return
    with open(cache_path, "w") as f:
        f.write(f"{msg_state},{time.time()}")

    # ── LINE 送信 ──
    msg = f"{today_human} の福岡競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")
    try:
        line_api.push_message(USER_ID, TextSendMessage(text=msg))
        app.logger.info("LINE push OK")
    except LineBotApiError as e:
        app.logger.error(f"LINE push failed {e.status_code}: {e.error.message}")

# ────────────────────────────────────────
#  Routes
# ────────────────────────────────────────
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/notify", methods=["GET"])
def notify():
    check_boatrace_and_notify()
    return "Notified", 200

# ────────────────────────────────────────
#  Local run
# ────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))