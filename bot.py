import ccxt
import pandas as pd
import time, os, threading, requests
from flask import Flask

app = Flask(__name__)

HL_PRIVATE_KEY = os.environ.get("HYPERLIQUID_PRIVATE_KEY")
HL_WALLET_ADDRESS = os.environ.get("HYPERLIQUID_WALLET_ADDRESS")

exchange = ccxt.hyperliquid({
    'privateKey': HL_PRIVATE_KEY,
    'walletAddress': HL_WALLET_ADDRESS,
    'enableRateLimit': True,
    'timeout': 30000,
})

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        except Exception as e:
            print(f"Erreur Telegram: {e}", flush=True)

cryptos = ['BTC/USDC:USDC', 'ETH/USDC:USDC']

def check_signal(symbol):
    try:
        print(f"Analyse de {symbol} (Timeframe 4h)...", flush=True)
        # On passe en 4h pour cette stratégie
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=200)
        
        if not ohlcv or len(ohlcv) < 200:
            return f"❌ Pas assez de données pour {symbol}"

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calcul des EMA (Moyennes Mobiles Exponentielles)
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        last = df.iloc[-1]
        price = last['close']
        
        # Récupération des positions ouvertes
        positions = exchange.fetch_positions([symbol])
        open_position = None
        for pos in positions:
            if pos['contracts'] > 0:
                open_position = pos
                break

        # --- LOGIQUE DE TRADING ---
        if open_position:
            # On a une position ouverte
            entry_price = open_position['entryPrice']
            stop_loss = entry_price * 0.95 # Stop loss à 5%
            
            if price < stop_loss:
                print(f"🛑 STOP LOSS atteint sur {symbol} à {price}$ (Achat à {entry_price}$)", flush=True)
                exchange.create_market_sell_order(symbol, open_position['contracts'])
                send_telegram_message(f"🛑 STOP LOSS sur {symbol} à {price}$")
                return f"Position fermée (SL) sur {symbol}"
                
            elif last['EMA_20'] < last['EMA_50']:
                print(f"🔴 SIGNAL DE VENTE sur {symbol} à {price}$ (Croisement baissier)", flush=True)
                exchange.create_market_sell_order(symbol, open_position['contracts'])
                send_telegram_message(f"🔴 VENTE sur {symbol} à {price}$")
                return f"Position fermée sur {symbol}"
            else:
                return f"🟡 Position en cours sur {symbol} (Achat: {entry_price}$, Actuel: {price}$)"
                
        else:
            # Pas de position ouverte, on cherche un signal d'achat
            if price > last['EMA_200'] and last['EMA_20'] > last['EMA_50']:
                signal_msg = f"🟢 ACHAT possible sur {symbol} à {price:.2f}$"
                try:
                    # Calcul de la taille de la position pour ~10$ (sans levier)
                    markets = exchange.load_markets()
                    amount = 10 / price # Taille pour environ 10$
                    amount = float(exchange.amount_to_precision(symbol, amount))
                    
                    order = exchange.create_order(symbol, 'market', 'buy', amount)
                    signal_msg += f"\n✅ Position ouverte ! Taille: {amount} {symbol.split('/')[0]}"
                    send_telegram_message(signal_msg)
                except Exception as e:
                    signal_msg += f"\n❌ Erreur Hyperliquid: {e}"
                return signal_msg
            elif price < last['EMA_200']:
                return f"🔴 ATTENTE sur {symbol} (Prix sous EMA 200)"
            else:
                return f"🟡 NEUTRE sur {symbol}"
            
    except Exception as e:
        return f"Erreur sur {symbol}: {e}"

def bot_loop():
    while True:
        print(f"\n--- Analyse du {pd.Timestamp.now()} ---", flush=True) 
        for crypto in cryptos:
            print(check_signal(crypto), flush=True)
        
        print("Attente de 4 heures avant la prochaine analyse...", flush=True)
        time.sleep(14400) # 4 heures en secondes

@app.route('/')
def home():
    return "Bot Hyperliquid (Stratégie 4h EMA 20/50) en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
