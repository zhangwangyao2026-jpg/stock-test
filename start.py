import yfinance as yf

# 設定台積電的代號 (台股要在代號後面加上 .TW)
stock_id = "2330.TW"

# 抓取數據
print(f"正在抓取 {stock_id} 的資料...")
stock = yf.Ticker(stock_id)

# 取得最新的股價資訊
data = stock.history(period="1d")

if not data.empty:
    current_price = data['Close'].iloc[-1]
    print("=" * 30)
    print(f"股票代號: {stock_id}")
    print(f"目前成交價: {current_price:.2f}")
    print("=" * 30)
else:
    print("找不到股票資料，請檢查網路或代號是否正確。")