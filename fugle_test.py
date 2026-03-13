import os
import time
import requests
import datetime
import pandas as pd
from fugle_marketdata import RestClient

# --- 核心策略設定 ---
WATCH_LIST = [
    "0050", "00980A", "2303", "2317", "1519", "2308", "2330", "2344", 
    "2449", "2454", "2618", "3037", "3665", "3711", "2313", "2337", 
    "2408", "3260", "3035", "3443", "3661", "5269", "4966", "5274", 
    "3529", "1503", "1513", "1514", "1504", "2603", "2609", "2615", 
    "2002", "1301", "1303", "6505", "1216", "3017", "3324", "2376", 
    "2377", "2382", "6669", "3653", "4526"
]

TRAILING_STOP_PERCENT = 0.10  # 移動止盈
MA_SUPPORT_GAP = 0.02         # 均線支撐
CHECK_INTERVAL = 60           # 輪詢間隔

FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    """取得資料並計算季線，加入延遲避開 429 頻率限制"""
    try:
        # 強制延遲 1.1 秒，確保不超過 API 每秒請求上限
        time.sleep(1.1) 
        res = client.stock.historical.candles(symbol=symbol, timeframe='D')
        if not res or 'data' not in res or len(res['data']) == 0:
            return None
            
        df = pd.DataFrame(res['data'])
        if len(df) >= 60:
            ma60 = df['close'].tail(60).mean()
            return round(ma60, 2)
    except Exception as e:
        print(f"⚠️ {symbol} MA60 初始化失敗: {e}")
    return None

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 錯誤：找不到 FUGLE_API_KEY")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    send_telegram_msg(f"✅ 長線監控啟動\n(已加入限流保護，避開 429 錯誤)")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        if current_time_str > "13:35":
            send_telegram_msg("🔔 收盤時間到，監控停止。")
            break

        if "09:00" <= current_time_str <= "13:35":
            print(f"\n--- [掃描輪次 {current_time_str}] ---")
            for symbol in WATCH_LIST:
                try:
                    # 1. 檢查是否需要初始化 MA60
                    if symbol not in price_memory:
                        print(f"正在初始化 {symbol} 季線數據...")
                        ma60 = update_ma60_cache(client, symbol)
                        price_memory[symbol] = {"high": 0.0, "ma60": ma60, "alerted_ma": False}
                    
                    # 2. 取得即時報價 (同樣小幅延遲保護)
                    time.sleep(0.2) 
                    res = client.stock.intraday.quote(symbol=symbol)
                    price = res.get('lastPrice')
                    name = res.get('name', symbol)
                    
                    if not price: continue
                    
                    data = price_memory[symbol]
                    
                    # 更新最高價與移動止盈邏輯
                    if price > data["high"]:
                        data["high"] = price

                    drop = (data["high"] - price) / data["high"] if data["high"] > 0 else 0
                    if drop >= TRAILING_STOP_PERCENT:
                        send_telegram_msg(f"⚠️ 止盈告警: {name}({symbol})\n現價: {price}\n高點回落: {drop:.1%}")
                        data["high"] = price * 1.5 # 暫時調高避免洗板

                    # 季線支撐邏輯
                    if data["ma60"] and not data["alerted_ma"]:
                        dist = (price - data["ma60"]) / data["ma60"]
                        if 0 <= dist <= MA_SUPPORT_GAP:
                            send_telegram_msg(f"🛡️ 支撐告警: {name}({symbol})\n現價: {price}\n季線支撐: {data['ma60']}")
                            data["alerted_ma"] = True 

                    print(f"[{symbol}] 現價: {price:>7} | 季線: {str(data['ma60']):>7}")

                except Exception as e:
                    print(f"處理 {symbol} 時發生異常: {e}")
                    continue
        else:
            print(f"非開盤時間 ({current_time_str})，靜候中...")
            time.sleep(300)
            continue

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()