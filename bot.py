import ccxt
import pandas as pd
import time, os, threading, requests
from flask import Flask

app = Flask(__name__)

# 1. Connexion à Hyperliquid
HL_PRIVATE_KEY = os.environ.get("HYPERLIQUID_PRIVATE_KEY")
HL_WALLET_ADDRESS = os.environ.get("HYPERLIQUID_WALLET_ADDRESS")

exchange = ccxt.hyperliquid({
    'privateKey': HL_PRIVATE_KEY,
    'walletAddress': HL_WALLET_ADDRESS,
    'enableRateLimit': True,
    'timeout': 30000,
})

# 2. Configuration Telegram
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

cryptos = ['BTC/USDC:USDC', 'ETH/USDC:USDC', 'SOL/USDC:USDC']

def check_signal(symbol):
    try:
        print(f"Analyse de {symbol}...", flush=True)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1d', limit=200)
        
        if not ohlcv or len(ohlcv) < 200:
            return f"❌ Pas assez de données pour {symbol}"

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        last = df.iloc[-1]
        price = last['close']
        
        if price > last['SMA_200'] and last['SMA_20'] > last['SMA_50']:
            signal_msg = f"🟢 ACHAT possible sur {symbol} à {price:.2f}$"
            try:
                # --- GESTION DU LEVIER ET DE LA TAILLE MINIMALE ---
                # On récupère le solde pour calculer la taille
                balance = exchange.fetch_balance()
                free_usdc = balance['USDC']['free']
                
                # Hyperliquid exige une position minimale de 10$
                # On utilise un levier de 2x pour que la position soit assez grande
                leverage = 2
                exchange.set_leverage(leverage, symbol)
                
                # Calcul de la taille de la position (en actifs)
                # On mise tout le solde disponible avec le levier
                position_value = free_usdc * leverage
                amount = position_value / price
                
                # Récupération du prix médian pour l'ordre au marché
                markets = exchange.load_markets()
                mid_price = markets[symbol]['info']['midPx']
                
                order = exchange.create_order(
                    symbol, 
                    'market', 
                    'buy', 
                    amount, 
                    price=mid_price
                )
                signal_msg += f"\n✅ Position ouverte sur Hyperliquid ! Levier: {leverage}x"
                send_telegram_message(signal_msg)
            except Exception as e:
                signal_msg += f"\n❌ Erreur Hyperliquid: {e}"
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
    return "Bot Hyperliquid (RÉEL) en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
