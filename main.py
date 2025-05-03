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
#  Flask アプリ
# ────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ────────────────────────────────────────
#  LINE 設定
# ────────────────────────────────────────
line_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
USER_ID = os.getenv("TARGET_USER_ID")

# ────────────────────────────────────────
#  タイムゾーン
# ────────────────────────────────────────
TZ = pytz.timezone("Asia/Tokyo")

# ────────────────────────────────────────
#  requests 再試行ヘルパ
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
#  メイン処理
# ────────────────────────────────────────
def check_boatrace_and_notify() -> None:
    now = datetime.now(TZ)
    today_human = now.strftime("%Y-%m-%d")       # 2025-05-03
    hd_param = now.strftime("%Y%m%d")            # 20250503

    # 22 = 福岡場コード ＋ 開催日パラメータ
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?jcd=22&hd={hd_param}"

    try:
        res = requests_retry_session().get(url, timeout=20)
        res.raise_for_status()
    except Exception as e:
        app.logger.error(f"scraping failed: {type(e).__name__} {e}")
        return  # スクレイピング失敗時は通知しない

    soup = BeautifulSoup(res.text, "html.parser")
    # 開催中なら .is-holding が存在
    has_race = bool(soup.select_one(".is-holding"))

    # ── 重複送信抑止（30 分同じ状態ならスキップ）
    cache_path = "/tmp/boat_cache.txt"
    msg_state = "1" if has_race else "0"
    if os.path.exists(cache_path):
        last, ts = open(cache_path).read().split(",")
        if last == msg_state and (time.time() - float(ts) < 1800):
            return
    with open(cache_path, "w") as f:
        f.write(f"{msg_state},{time.time()}")

    # ── LINE 送信
    msg = f"{today_human} の福岡競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")
    try:
        line_api.push_message(USER_ID, TextSendMessage(text=msg))
        app.logger.info("LINE push OK")
    except LineBotApiError as e:
        app.logger.error(f"LINE push failed {e.status_code}: {e.error.message}")

# ────────────────────────────────────────
#  ルーティング
# ────────────────────────────────────────
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/notify", methods=["GET"])
def notify():
    check_boatrace_and_notify()
    return "Notified", 200

# ────────────────────────────────────────
#  ローカル実行用
# ────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))