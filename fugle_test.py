import os  # 務必匯入這個系統套件
from fugle_marketdata import RestClient
import time

# 改成從環境變數讀取，如果抓不到就變成 None
api_key = os.getenv("FUGLE_API_KEY")

if not api_key:
    print("錯誤：找不到 API Key，請檢查環境變數設定。")
    exit()

client = RestClient(api_key=api_key)
stock = client.stock

# 設定您的目標警示價位
target_price = 1930.0 

print(f"正在監控台積電 (2330)... 目標警示價位：{target_price}")

while True:
    try:
        res = stock.intraday.quote(symbol="2330")
        price = res.get('lastPrice')
        
        if price:
            print(f"【即時監控】目前價格：{price}")
            
            # 加入判斷邏輯
            if price <= target_price:
                print(f"！！！【警報】價格跌破 {target_price}，現在是 {price} ！！！")
                # 這裡以後可以加入傳送 Telegram 或 Line 通知的功能
        
    except Exception as e:
        print(f"資料讀取中... ({e})")
    
    time.sleep(10)