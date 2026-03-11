import os
import time
import requests
import datetime
import pandas as pd
from fugle_marketdata import RestClient

# --- 核心策略設定 ---
# 已整理您的所有觀察名單，並自動去重
WATCH_LIST = [
    "0050", "00980A", "2303", "2317", "1519", "2308", "2330", "2344", 
    "2449", "2454", "2618", "3037", "3665", "3711", "2313", "2337", 
    "2408", "3260", "3035", "3443", "3661", "5269", "4966", "5274", 
    "3529", "1503", "1513", "1514", "1504", "2603", "2609", "2615", 
    "2002", "1301", "1303", "6505", "1216", "3017", "3324", "2376", 
    "2377", "2382", "6669", "3653", "4526"
]

TRAILING_STOP_PERCENT = 0.10  # 移動止盈：從最高點回落 10% 警示
MA_SUPPORT_GAP = 0.02         # 均線支撐：靠近季線 2% 以內警示
CHECK_INTERVAL = 180          # 50檔名單建議每 3 分鐘輪詢一次，最安全且穩定

# --- 安全讀取環境變數 ---
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 記憶體：紀錄每檔股票的「近期最高價」與「MA60」
price_memory = {}

def send_telegram_msg(message):
    if not TG_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": message}, timeout=10)
    except: pass

def get_tw_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def update_ma60_cache(client, symbol):
    """取得過去 60 天資料並計算季線"""
    try:
        res = client.stock.historical.candles(symbol=symbol, fields=['close'])
        df = pd.DataFrame(res['data'])
        if len(df) >= 60:
            ma60 = df['close'].tail(60).mean()
            return round(ma60, 2)
    except Exception as e:
        print(f"無法計算 {symbol} 的 MA60: {e}")
    return None

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 錯誤：找不到 FUGLE_API_KEY")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    stock = client.stock
    
    print(f"🚀 全名單監控啟動，總數：{len(WATCH_LIST)} 檔")
    send_telegram_msg(f"✅ 雲端交易員已就位\n監控總數：{len(WATCH_LIST)} 檔\n策略：季線支撐 + 10%移動止盈")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        # 自動下班：13:35 結束
        if current_time_str > "13:35":
            print(f"🕒 現在 {current_time_str}，收盤下班。")
            break

        # 盤中執行：09:00 - 13:35
        if "09:00" <= current_time_str <= "13:35":
            for symbol in WATCH_LIST:
                try:
                    res = stock.intraday.quote(symbol=symbol)
                    price = res.get('lastPrice')
                    name = res.get('name', symbol)
                    
                    if not price: continue

                    # 初始化或更新緩存
                    if symbol not in price_memory:
                        ma60 = update_ma60_cache(client, symbol)
                        price_memory[symbol] = {"high": price, "ma60": ma60}
                    
                    data = price_memory[symbol]
                    
                    # 策略 A：更新最高價與移動止盈
                    if price > data["high"]:
                        data["high"] = price

                    drop_from_high = (data["high"] - price) / data["high"]
                    if drop_from_high >= TRAILING_STOP_PERCENT:
                        alert = f"⚠️ 移動止盈通知\n標的：{name}({symbol})\n現價：{price}\n高點：{data['high']}\n回落：{drop_from_high:.1%}"
                        send_telegram_msg(alert)
                        data["high"] = price * 1.5 # 暫時調高門檻避免重複噴訊息

                    # 策略 B：均線支撐偵測
                    if data["ma60"]:
                        dist_to_ma60 = (price - data["ma60"]) / data["ma60"]
                        if 0 <= dist_to_ma60 <= MA_SUPPORT_GAP:
                            alert = f"🛡️ 靠近支撐區\n標的：{name}({symbol})\n現價：{price}\n季線：{data['ma60']}\n距季線僅 {dist_to_ma60:.1%}\n長線好買點觀察中。"
                            send_telegram_msg(alert)
                            data["ma60"] = None # 發過就暫時清掉，免得一直吵

                    print(f"[{current_time_str}] {name:10}: {price:>8}")
                    time.sleep(1.2) # 稍微加長間隔，50檔跑一圈約 1 分鐘

                except Exception as e:
                    print(f"處理 {symbol} 時跳過: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()