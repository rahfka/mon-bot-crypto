import ccxt, pandas as pd, time, os, threading
from flask import Flask

app = Flask(__name__)
exchange = ccxt.binance()
cryptos = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

def check_signal(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1d', limit=200)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        last = df.iloc[-1]
        price = last['close']
        if price > last['SMA_200'] and last['SMA_20'] > last['SMA_50']:
            return f"🟢 ACHAT possible sur {symbol} à {price}$"
        elif price < last['SMA_200']:
            return f"🔴 ATTENTE sur {symbol} (Prix sous SMA 200)"
        else:
            return f"🟡 NEUTRE sur {symbol} (Pas de croisement)"
    except Exception as e:
        return f"Erreur sur {symbol}: {e}"

def bot_loop():
    while True:
        print(f"\n--- Analyse du {pd.Timestamp.now()} ---")
        for crypto in cryptos:
            print(check_signal(crypto))
        time.sleep(3600)

@app.route('/')
def home():
    return "Bot en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
