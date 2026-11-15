import ccxt
import pandas as pd
import time, os, threading
from flask import Flask

app = Flask(__name__)

# 1. Binance Testnet : Uniquement pour exécuter les ordres fictifs
API_KEY = os.environ.get("BINANCE_API_KEY")
SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")
exchange_test = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'timeout': 30000,
})
exchange_test.set_sandbox_mode(True)

# 2. MEXC : Utilisé pour lire les vraies données de marché (accessible depuis un serveur US)
exchange_data = ccxt.mexc({
    'enableRateLimit': True,
    'timeout': 30000,
})

cryptos = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

def check_signal(symbol):
    try:
        print(f"Récupération des données pour {symbol}...", flush=True)
        
        # Récupération des bougies via MEXC
        ohlcv = exchange_data.fetch_ohlcv(symbol, timeframe='1d', limit=200)
        
        if not ohlcv or len(ohlcv) < 200:
            return f"❌ Pas assez de données pour {symbol}"

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        last = df.iloc[-1]
        price = last['close']
        
        # Logique de la stratégie validée
        if price > last['SMA_200'] and last['SMA_20'] > last['SMA_50']:
            signal_msg = f"🟢 ACHAT possible sur {symbol} à {price}$"
            try:
                # Passage de l'ordre sur le Testnet Binance
                order = exchange_test.create_market_buy_order(symbol, 0.001)
                signal_msg += f"\n✅ Ordre d'achat Testnet passé ! ID: {order.get('id')}"
            except Exception as e:
                signal_msg += f"\n❌ Erreur lors de l'ordre Testnet: {e}"
            return signal_msg
        elif price < last['SMA_200']:
            return f"🔴 ATTENTE sur {symbol} (Prix {price:.2f}$ sous SMA 200 à {last['SMA_200']:.2f}$)"
        else:
            return f"🟡 NEUTRE sur {symbol}"
            
    except Exception as e:
        return f"Erreur sur {symbol}: {e}"

def bot_loop():
    while True:
        print(f"\n--- Analyse du {pd.Timestamp.now()} ---", flush=True) 
        for crypto in cryptos:
            print(check_signal(crypto), flush=True)
        
        print("Attente de 1 heure avant la prochaine analyse...", flush=True)
        time.sleep(3600)

@app.route('/')
def home():
    return "Bot opérationnel (Données: MEXC, Ordres: Binance Testnet) et en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
