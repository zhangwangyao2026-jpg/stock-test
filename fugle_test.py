import os
import time
import requests
import datetime
from fugle_marketdata import RestClient

# --- 設定區 ---
STOCK_SYMBOL = "2330"    
TARGET_PRICE = 1950.0    # 💡 測試建議：先設一個比現價高的數字，確保它會觸發警報
STOP_TIME = "13:35"      
CHECK_INTERVAL = 10      

# --- 讀取環境變數 ---
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    """傳送訊息並印出除錯資訊"""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("❌ 錯誤：找不到 Telegram Secrets 設定。")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message}
    
    try:
        response = requests.post(url, json=payload)
        # 💡 這行非常重要，它會告訴我們 Telegram 的真實反應
        if response.status_code == 200:
            print("✅ Telegram 訊息發送成功！")
        else:
            print(f"❌ Telegram 發送失敗。狀態碼：{response.status_code}")
            print(f"❌ 錯誤原因：{response.text}")
    except Exception as e:
        print(f"❌ 網路連線異常：{e}")

def get_tw_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 錯誤：找不到 FUGLE_API_KEY。")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    stock = client.stock
    
    print(f"🚀 雲端監控啟動：{STOCK_SYMBOL}")
    print(f"📢 目前設定目標價：{TARGET_PRICE} (低於此價會發通知)")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        # 自動下班邏輯 (測試時可以先把這段註解掉，或是確認現在時間)
        if current_time_str > STOP_TIME:
            print(f"🕒 現在 {current_time_str}，收盤休息。")
            # 為了測試，我們先讓它印出最後一筆就結束
            # break 

        try:
            res = stock.intraday.quote(symbol=STOCK_SYMBOL)
            current_price = res.get('lastPrice')
            
            if current_price:
                print(f"【{current_time_str}】即時價格: {current_price}")
                
                # 測試觸發條件
                if current_price <= TARGET_PRICE:
                    msg = f"🔔 股價警報！\n標的：{STOCK_SYMBOL}\n現價：{current_price}\n低於目標：{TARGET_PRICE}"
                    send_telegram_msg(msg)
                    # 為了避免洗板，發送後可以考慮 break 或增加間隔
            
        except Exception as e:
            print(f"抓取資料失敗: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()