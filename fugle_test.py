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
MA_SUPPORT_GAP = 0.02          # 2% 季線支撐觀察區
CHECK_INTERVAL = 60            # 輪詢間隔 (秒)

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

def init_stock_data(client, symbol):
    """初始化季線數據與基本資料"""
    try:
        time.sleep(1.0) 
        res = client.stock.historical.candles(symbol=symbol, timeframe='D')
        if not res or 'data' not in res or len(res['data']) == 0:
            return None
        
        df = pd.DataFrame(res['data'])
        ma60_val = df['close'].tail(60).mean()
        
        ticker = client.stock.intraday.ticker(symbol=symbol)
        stock_name = ticker.get('name', symbol)
        
        return {
            "current_max": 0.0, 
            "ma60": round(ma60_val, 2), 
            "alerted_ma": False,
            "name": stock_name
        }
    except Exception as e:
        print(f"❌ {symbol} 初始化失敗: {e}")
        return None

def start_monitor():
    if not FUGLE_API_KEY:
        print("❌ 錯誤：找不到 FUGLE_API_KEY")
        return

    client = RestClient(api_key=FUGLE_API_KEY)
    send_telegram_msg("🚀 長線波段監控啟動 (sen-stock-test)")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        if current_time_str > "13:35":
            send_telegram_msg("🔔 長線波段監控今日台股監控結束。")
            break

        if "09:00" <= current_time_str <= "13:35":
            for symbol in WATCH_LIST:
                try:
                    if symbol not in price_memory:
                        data = init_stock_data(client, symbol)
                        if data: price_memory[symbol] = data
                        else: continue
                    
                    quote = client.stock.intraday.quote(symbol=symbol)
                    price = quote.get('lastPrice')
                    chg_pct = quote.get('changePercent', 0)
                    
                    if not price: continue
                    
                    stock_data = price_memory[symbol]
                    
                    # 更新波段最高價
                    if price > stock_data["current_max"]:
                        stock_data["current_max"] = price

                    # 策略 A：移動止盈
                    if stock_data["current_max"] > 0:
                        drop_ratio = (stock_data["current_max"] - price) / stock_data["current_max"]
                        if drop_ratio >= TRAILING_STOP_PERCENT:
                            msg = (f"⚠️ 止盈告警！\n"
                                   f"標的：{symbol} {stock_data['name']}\n"
                                   f"現價：{price} ({chg_pct:+.2f}%)\n"
                                   f"最高價：{stock_data['current_max']}\n"
                                   f"觸發條件：回落 {drop_ratio:.1%}")
                            send_telegram_msg(msg)
                            stock_data["current_max"] = price * 2 

                    # 策略 B：季線支撐
                    if stock_data["ma60"] > 0 and not stock_data["alerted_ma"]:
                        dist = (price - stock_data["ma60"]) / stock_data["ma60"]
                        if 0 <= dist <= MA_SUPPORT_GAP:
                            stop_loss = round(stock_data["ma60"] * 0.98, 2)
                            msg = (f"🛡️ 支撐買點觀察！\n"
                                   f"標的：{symbol} {stock_data['name']}\n"
                                   f"現價：{price} (接近季線 {stock_data['ma60']})\n"
                                   f"建議停損：{stop_loss} (季線 -2%)\n"
                                   f"距離：{dist:.2%}")
                            send_telegram_msg(msg)
                            stock_data["alerted_ma"] = True 

                    time.sleep(0.2)
                except:
                    continue
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()
