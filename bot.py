import ccxt
import pandas as pd
import time, os, threading, requests
from flask import Flask
from marginpad import MarginPad

app = Flask(__name__)

# 1. Connexion à MarginPad (Ordres)
MP_API_KEY = os.environ.get("MARGINPAD_API_KEY")
mp = MarginPad(MP_API_KEY)

# 2. Connexion à MEXC (Données historiques)
exchange_data = ccxt.mexc({
    'enableRateLimit': True,
    'timeout': 30000,
})

# 3. Configuration Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
            print("📬 Message Telegram envoyé !", flush=True)
        except Exception as e:
            print(f"Erreur Telegram: {e}", flush=True)

cryptos = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

def check_signal(symbol):
    try:
        print(f"Analyse de {symbol}...", flush=True)
        # On récupère 200 bougies depuis MEXC
        ohlcv = exchange_data.fetch_ohlcv(symbol, timeframe='1d', limit=200)
        
        if not ohlcv or len(ohlcv) < 200:
            return f"❌ Pas assez de données pour {symbol}"

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calcul des moyennes mobiles
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        last = df.iloc[-1]
        price = last['close']
        
        # --- STRATÉGIE RÉELLE ---
        if price > last['SMA_200'] and last['SMA_20'] > last['SMA_50']:
            signal_msg = f"🟢 ACHAT possible sur {symbol} à {price:.2f}$"
            try:
                # On enlève le /USDT pour MarginPad
                symbol_mp = symbol.split('/')[0]
                
                # On ouvre une position fictive
                pos = mp.open(symbol_mp, "long", margin_usd=100, leverage=1)
                signal_msg += f"\n✅ Position ouverte sur MarginPad !"
                send_telegram_message(signal_msg)
            except Exception as e:
                signal_msg += f"\n❌ Erreur MarginPad: {e}"
            return signal_msg
        # -------------------------
            
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
    return "Bot opérationnel (MarginPad + Telegram) et en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
