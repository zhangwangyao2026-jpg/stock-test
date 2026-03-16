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

TRAILING_STOP_PERCENT = 0.10  # 10% 移動止盈 (回落止盈)
MA_SUPPORT_GAP = 0.02         # 2% 季線支撐 (買入觀察區)
CHECK_INTERVAL = 60           # 輪詢間隔 (秒)

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
    try:
        time.sleep(1.2) 
        res = client.stock.historical.candles(
            symbol=symbol, timeframe='D',
            fields=['open', 'high', 'low', 'close', 'volume', 'turnover', 'change']
        )
        if not res or 'data' not in res: return None
        df = pd.DataFrame(res['data'])
        if not df.empty:
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
    send_telegram_msg("🚀 長線波段監控啟動\n(已整合建議買價與移動止盈點)")

    while True:
        now = get_tw_time()
        current_time_str = now.strftime("%H:%M")

        if current_time_str > "13:35":
            send_telegram_msg("🔔 今日台股已收盤，自動監控結束。")
            break

        if "09:00" <= current_time_str <= "13:35":
            print(f"\n--- [掃描輪次 {current_time_str}] ---")
            for symbol in WATCH_LIST:
                try:
                    if symbol not in price_memory:
                        ma60 = update_ma60_cache(client, symbol)
                        price_memory[symbol] = {"high": 0.0, "ma60": ma60, "alerted_ma": False}
                    
                    time.sleep(0.3) 
                    res = client.stock.intraday.quote(symbol=symbol)
                    price = res.get('lastPrice')
                    name = res.get('name', symbol)
                    change_pct = res.get('changePercent', 0)
                    
                    if not price: continue
                    data = price_memory[symbol]
                    
                    if price > data["high"]:
                        data["high"] = price

                    # 策略 A：移動止盈告警 (最高點回落)
                    if data["high"] > 0:
                        drop = (data["high"] - price) / data["high"]
                        if drop >= TRAILING_STOP_PERCENT:
                            msg = (f"⚠️ 止盈告警！\n"
                                   f"標的：{symbol} {name}\n"
                                   f"現價：{price} ({change_pct:+.2f}%)\n"
                                   f"最高價：{data['high']}\n"
                                   f"觸發止盈：{price} (回落 {drop:.1%})\n"
                                   f"建議出場：分批減碼或全數獲利")
                            send_telegram_msg(msg)
                            data["high"] = price * 1.5 

                    # 策略 B：季線支撐告警 (建議買入區)
                    if data["ma60"] and not data["alerted_ma"]:
                        dist = (price - data["ma60"]) / data["ma60"]
                        if 0 <= dist <= MA_SUPPORT_GAP:
                            # 建議止損設在季線下方 2%
                            stop_loss = round(data["ma60"] * 0.98, 2)
                            msg = (f"🛡️ 支撐買點觀察！\n"
                                   f"標的：{symbol} {name}\n"
                                   f"現價：{price} ({change_pct:+.2f}%)\n"
                                   f"建議買位：{price} (接近季線 {data['ma60']})\n"
                                   f"建議停損：{stop_loss} (季線 -2%)\n"
                                   f"距離支撐：{dist:.2%}")
                            send_telegram_msg(msg)
                            data["alerted_ma"] = True 

                    print(f"[{symbol} {name[:2]}] 現價: {price:>7} | 季線: {str(data['ma60']):>7}")

                except Exception as e:
                    continue
        else:
            time.sleep(600)
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_monitor()
