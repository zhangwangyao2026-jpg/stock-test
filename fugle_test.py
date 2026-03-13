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

TRAILING_STOP_PERCENT = 0.10  # 10% 移動止盈
MA_SUPPORT_GAP = 0.02         # 2% 季線支撐
CHECK_INTERVAL = 60           # 輪詢間隔 (秒)

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
    """計算季線：補齊必填欄位並增加延遲避開限制"""
    try:
        # 強制延遲 1.2 秒，確保每秒不超過一個請求，解決 429 錯誤
        time.sleep(1.2) 
        
        # 修正點：補齊所有必填欄位，解決 400 錯誤與 None 顯示問題
        res = client.stock.historical.candles(
            symbol=symbol, 
            timeframe='D',
            fields=['open', 'high', 'low', 'close', 'volume', 'turnover', 'change']
        )
        if not res or 'data' not in res or not res['data']:
            print(f"⚠️ {symbol} 抓取歷史數據失敗")
            return None
            
        df = pd.DataFrame(res['data'])
        if not df.empty:
            # 即使不足 60 天也計算平均，避免顯示 None
            ma_period = min(len(df), 60)
            ma_val = df['close'].tail(ma_period).mean()
            return round(ma_val, 2)
    except Exception as e:
        print(f"❌ {symbol} 季線計算異常: {e}")
    return None

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 錯誤：找不到 FUGLE_API_KEY")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    send_telegram_msg("🚀 長線監控已修復啟動\n(修正：API 欄位與季線計算優化)")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        # 13:35 結束當日監控
        if current_time_str > "13:35":
            send_telegram_msg("🔔 今日盤中監控結束。")
            break

        # 盤中執行時間
        if "09:00" <= current_time_str <= "13:35":
            print(f"\n--- [掃描輪次 {current_time_str}] ---")
            for symbol in WATCH_LIST:
                try:
                    # 1. 初始化該檔股票的數據 (MA60)
                    if symbol not in price_memory:
                        print(f"正在初始化 {symbol} 數據...")
                        ma60 = update_ma60_cache(client, symbol)
                        price_memory[symbol] = {"high": 0.0, "ma60": ma60, "alerted_ma": False}
                    
                    # 2. 取得即時報價
                    time.sleep(0.3) 
                    res = client.stock.intraday.quote(symbol=symbol)
                    price = res.get('lastPrice')
                    name = res.get('name', symbol)
                    
                    if not price: continue
                    
                    data = price_memory[symbol]
                    
                    # 3. 策略判斷：更新最高價
                    if price > data["high"]:
                        data["high"] = price

                    # 策略 A：10% 移動止盈
                    if data["high"] > 0:
                        drop = (data["high"] - price) / data["high"]
                        if drop >= TRAILING_STOP_PERCENT:
                            send_telegram_msg(f"⚠️ 止盈告警: {name}({symbol})\n現價: {price}\n最高: {data['high']}\n回落: {drop:.1%}")
                            data["high"] = price * 1.5 # 調高門檻避免同一天洗板

                    # 策略 B：2% 季線支撐
                    if data["ma60"] and not data["alerted_ma"]:
                        dist = (price - data["ma60"]) / data["ma60"]
                        if 0 <= dist <= MA_SUPPORT_GAP:
                            send_telegram_msg(f"🛡️ 支撐告警: {name}({symbol})\n現價: {price}\n季線: {data['ma60']}")
                            data["alerted_ma"] = True 

                    print(f"[{symbol}] 現價: {price:>7} | 季線: {str(data['ma60']):>7}")

                except Exception as e:
                    print(f"處理 {symbol} 異常: {e}")
                    continue
        else:
            print(f"等待開盤中 ({current_time_str})...")
            time.sleep(300)
            continue

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()