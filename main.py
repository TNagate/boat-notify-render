import os, logging, requests, time
from datetime import datetime
from bs4 import BeautifulSoup
import pytz

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from flask import Flask
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError

# ── Flask アプリ ───────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ── LINE 設定 ──────────────────────────────
line_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
USER_ID  = os.getenv("TARGET_USER_ID")

# ── タイムゾーン ───────────────────────────
TZ = pytz.timezone("Asia/Tokyo")

# ── 再試行付き requests セッション ─────────
def requests_retry_session(retries=3, backoff_factor=0.5,
                           status_forcelist=(500, 502, 504), session=None):
    session = session or requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries,
                  backoff_factor=backoff_factor,
                  status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session

# ── 競艇開催チェック ＋ LINE 通知 ──────────
def check_boatrace_and_notify():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    url   = "https://www.boatrace.jp/owpc/pc/race/racelist?jcd=22"  # 22 = 福岡

    try:
        res = requests_retry_session().get(url, timeout=20)
        res.raise_for_status()
    except Exception as e:
        app.logger.error(f"scraping failed: {type(e).__name__} {e}")
        return  # スクレイピング失敗時は通知しない

    soup = BeautifulSoup(res.text, "html.parser")
    # 開催中レースに .is-active が付く

has_race = bool(soup.select_one(".is-holding"))

    # --- 重複送信を 30 分抑止 ---
    cache_path = "/tmp/boat_cache.txt"
    msg_state  = "1" if has_race else "0"
    if os.path.exists(cache_path):
        last, ts = open(cache_path).read().split(",")
        if last == msg_state and (time.time() - float(ts) < 1800):
            return
    open(cache_path, "w").write(f"{msg_state},{time.time()}")

    # --- LINE 送信 ---
    msg = f"{today} の福岡競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")
    try:
        line_api.push_message(USER_ID, TextSendMessage(text=msg))
        app.logger.info("LINE push OK")
    except LineBotApiError as e:
        app.logger.error(f"LINE push failed {e.status_code}: {e.error.message}")

# ── ルート ────────────────────────────────
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/notify", methods=["GET"])
def notify():
    check_boatrace_and_notify()
    return "Notified", 200

# ── ローカル実行用 ─────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))