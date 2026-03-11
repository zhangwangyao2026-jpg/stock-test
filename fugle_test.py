import os
import time
import requests
import datetime
import pandas as pd
from fugle_marketdata import RestClient

# --- 核心策略設定 ---
# 填入您的觀察名單 (建議先放核心持股，名單太長建議分批)
WATCH_LIST = [
    "2330", "2317", "2454", "2303", "2308", "0050", "1519", "3017", 
    "2382", "3665", "2618", "2603", "3711", "3037", "2313", "1503"
]

TRAILING_STOP_PERCENT = 0.10  # 移動止盈：從最高點回落 10% 警示
MA_SUPPORT_GAP = 0.02         # 均線支撐：靠近季線 2% 以內警示
CHECK_INTERVAL = 60           # 多檔監控建議每 60 秒輪詢一次，避免觸發 API 限制

# --- 安全讀取環境變數 ---
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 記憶體：紀錄每檔股票的「近期最高價」與「MA60」
price_memory = {} # 格式: {"2330": {"high": 1000.0, "ma60": 950.0}}

def send_telegram_msg(message):
    if not TG_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": message})
    except: pass

def get_tw_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def update_ma60_cache(client, symbol):
    """取得過去 60 天資料並計算季線"""
    try:
        # 抓取最近 100 天的日 K 線確保資料充足
        end_date = get_tw_time().strftime("%Y-%m-%d")
        res = client.stock.historical.candles(symbol=symbol, fields=['close'])
        df = pd.DataFrame(res['data'])
        if len(df) >= 60:
            ma60 = df['close'].tail(60).mean()
            return round(ma60, 2)
    except Exception as e:
        print(f"計算 {symbol} MA60 失敗: {e}")
    return None

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 找不到 FUGLE_API_KEY")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    stock = client.stock
    
    print(f"🚀 中長線波段監控啟動，監控數量：{len(WATCH_LIST)}")
    send_telegram_msg(f"✅ 雲端交易員上線：監控清單共 {len(WATCH_LIST)} 檔標的")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        # 自動下班：13:35 結束
        if current_time_str > "13:35":
            print("🕒 已過收盤時間，程式下班。")
            break

        # 盤中執行：09:00 - 13:35
        if "09:00" <= current_time_str <= "13:35":
            for symbol in WATCH_LIST:
                try:
                    # 1. 抓取即時報價
                    res = stock.intraday.quote(symbol=symbol)
                    price = res.get('lastPrice')
                    name = res.get('name', symbol)
                    if not price: continue

                    # 2. 初始化或更新記憶體資料
                    if symbol not in price_memory:
                        ma60 = update_ma60_cache(client, symbol)
                        price_memory[symbol] = {"high": price, "ma60": ma60}
                    
                    data = price_memory[symbol]
                    
                    # 更新最高價 (移動止盈用)
                    if price > data["high"]:
                        data["high"] = price

                    # 3. 判斷策略 A：移動止盈 (從高點回落 10%)
                    drop_from_high = (data["high"] - price) / data["high"]
                    if drop_from_high >= TRAILING_STOP_PERCENT:
                        alert = f"⚠️ 移動止盈警報！\n標的：{name}({symbol})\n現價：{price}\n近期高點：{data['high']}\n已回落：{drop_from_high:.1%}\n建議檢查趨勢是否轉弱。"
                        send_telegram_msg(alert)
                        # 防止洗板，發送後調高最高價門檻
                        data["high"] = price * 1.5 

                    # 4. 判斷策略 B：均線支撐 (靠近季線 2% 內)
                    if data["ma60"]:
                        dist_to_ma60 = (price - data["ma60"]) / data["ma60"]
                        if 0 <= dist_to_ma60 <= MA_SUPPORT_GAP:
                            alert = f"🛡️ 支撐點觀察中\n標的：{name}({symbol})\n現價：{price}\n季線(MA60)：{data['ma60']}\n目前僅高於季線 {dist_to_ma60:.1%}\n長線分批佈署機會點！"
                            send_telegram_msg(alert)
                            # 防止洗板，暫時清除 ma60 紀錄
                            data["ma60"] = None 

                    print(f"[{current_time_str}] {name:8}: {price:>8} | 距高點: -{drop_from_high:.1%}")
                    time.sleep(1) # 每檔股票間隔 1 秒，避免 API 超載

                except Exception as e:
                    print(f"監控 {symbol} 時發生錯誤: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()