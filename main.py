import os, logging, requests, time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# …（省略）

def requests_retry_session(
        retries=3,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 504),
        session=None):
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

def check_boatrace_and_notify():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    url = "https://www.boatrace.jp/owpc/pc/race/pay"

    try:
        res = requests_retry_session().get(url, timeout=30)
        res.raise_for_status()
    except Exception as e:
        app.logger.error(f"scraping failed: {type(e).__name__} {e}")
        return  # エラー時は何も送らない

    soup = BeautifulSoup(res.text, "html.parser")
    has_race = "福岡" in soup.get_text()

    # 直近30分以内に同じメッセージを送ったか簡易キャッシュ
    cache_path = "/tmp/boat_cache.txt"
    msg_state = "1" if has_race else "0"
    last = ""
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            last, ts = f.read().split(",")
            if last == msg_state and (time.time() - float(ts) < 1800):
                return  # 重複送信を回避
    with open(cache_path, "w") as f:
        f.write(f"{msg_state},{time.time()}")

    msg = f"{today} の福岡競艇：" + ("開催あり 🎉" if has_race else "開催なし ❌")
    try:
        line_api.push_message(USER_ID, TextSendMessage(text=msg))
        app.logger.info("LINE push OK")
    except LineBotApiError as e:
        app.logger.error(f"LINE push failed {e.status_code}: {e.error.message}")