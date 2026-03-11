import os
import time
import requests
from fugle_marketdata import RestClient

# --- 設定區 ---
STOCK_SYMBOL = "2330"    # 想要監控的股票代碼
TARGET_PRICE = 1930.0    # 您的警示目標價
CHECK_INTERVAL = 10      # 每隔幾秒檢查一次

# --- 安全讀取環境變數 ---
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    """傳送訊息到您的 Telegram 手機 App"""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("尚未設定 Telegram Secrets，訊息僅會印在螢幕上。")
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram 傳送失敗: {e}")

def start_monitor():
    if not FUGLE_API_KEY:
        print("錯誤：找不到 FUGLE_API_KEY。請檢查 GitHub Secrets 或環境變數設定。")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    stock = client.stock
    
    print(f"🚀 雲端監控啟動：{STOCK_SYMBOL} | 目標價：{TARGET_PRICE}")
    print("按 Ctrl+C 可停止監控")

    while True:
        try:
            # 抓取即時報價
            res = stock.intraday.quote(symbol=STOCK_SYMBOL)
            current_price = res.get('lastPrice')
            stock_name = res.get('name', STOCK_SYMBOL)

            if current_price:
                print(f"【{stock_name}】目前價格: {current_price}")
                
                # 警報邏輯：您可以自行修改為價格低於 (<=) 或 高於 (>=)
                if current_price <= TARGET_PRICE:
                    alert_msg = f"🔔 股價警報！\n股票：{stock_name}({STOCK_SYMBOL})\n目前價格：{current_price}\n已跌破設定的 {TARGET_PRICE}！"
                    print(alert_msg)
                    send_telegram_msg(alert_msg)
            
        except Exception as e:
            print(f"連線稍忙或資料更新中... ({e})")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()