import os
import time
import requests
import datetime
from fugle_marketdata import RestClient

# --- 設定區 ---
STOCK_SYMBOL = "2330"    # 監控代碼
TARGET_PRICE = 1930.0    # 警示目標價
CHECK_INTERVAL = 10      # 每 10 秒檢查一次
STOP_TIME = "13:35"      # 自動下班時間 (台灣時間)

# --- 安全讀取環境變數 ---
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    """傳送訊息到 Telegram"""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("尚未設定 Telegram Secrets。")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram 傳送失敗: {e}")

def get_tw_time():
    """獲取台灣時間 (UTC+8)"""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def start_monitor():
    if not FUGLE_API_KEY:
        print("錯誤：找不到 FUGLE_API_KEY。")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    stock = client.stock
    
    print(f"🚀 雲端監控啟動：{STOCK_SYMBOL} | 目標價：{TARGET_PRICE}")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        # 1. 自動下班邏輯：超過收盤時間就結束程式
        if current_time_str > STOP_TIME:
            print(f"🕒 現在時間 {current_time_str}，已過收盤時間，程式自動下班。")
            break

        # 2. 開盤等待邏輯：如果還沒到 09:00 (例如 Actions 提早跑了)
        if current_time_str < "09:00":
            print(f"😴 還沒開盤 (目前 {current_time_str})，休息中...")
            time.sleep(60) # 每分鐘檢查一次即可
            continue

        try:
            # 3. 執行監控
            res = stock.intraday.quote(symbol=STOCK_SYMBOL)
            current_price = res.get('lastPrice')
            stock_name = res.get('name', STOCK_SYMBOL)

            if current_price:
                print(f"【{current_time_str} | {stock_name}】價格: {current_price}")
                
                if current_price <= TARGET_PRICE:
                    alert_msg = f"🔔 股價警報！\n股票：{stock_name}\n目前價格：{current_price}\n低於設定值 {TARGET_PRICE}"
                    send_telegram_msg(alert_msg)
            
        except Exception as e:
            print(f"資料更新中或 API 忙碌... ({e})")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()