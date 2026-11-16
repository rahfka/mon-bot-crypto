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

cryptos = [
    'BTC/USDC:USDC', 'ETH/USDC:USDC', 'SOL/USDC:USDC', 
    'BNB/USDC:USDC', 'XRP/USDC:USDC', 'ADA/USDC:USDC', 
    'AVAX/USDC:USDC', 'DOGE/USDC:USDC', 'LINK/USDC:USDC', 
    'DOT/USDC:USDC'
]

def check_signal(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=200)
        
        if not ohlcv or len(ohlcv) < 200:
            return f"❌ Pas assez de données pour {symbol}"

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        last = df.iloc[-1]
        price = last['close']
        
        positions = exchange.fetch_positions([symbol])
        open_position = None
        for pos in positions:
            if pos['contracts'] > 0:
                open_position = pos
                break

        # --- LOGIQUE DE TRADING AVEC TRAILING STOP ---
        if open_position:
            entry_price = open_position['entryPrice']
            
            # Calcul du Stop-Loss dynamique (Trailing par paliers)
            if price > entry_price * 1.10:
                stop_loss = entry_price * 1.05  # Sécurise 5% de profit
                sl_type = "Sécurisé +5%"
            elif price > entry_price * 1.05:
                stop_loss = entry_price         # Breakeven (sécurise le capital)
                sl_type = "Breakeven"
            else:
                stop_loss = entry_price * 0.95  # Stop-Loss initial
                sl_type = "Initial (-5%)"
            
            if price < stop_loss:
                print(f"🛑 STOP LOSS ({sl_type}) sur {symbol} à {price}$", flush=True)
                exchange.create_market_sell_order(symbol, open_position['contracts'])
                send_telegram_message(f"🛑 STOP LOSS ({sl_type}) sur {symbol} à {price}$")
                return f"Position fermée (SL {sl_type}) sur {symbol}"
                
            elif last['EMA_20'] < last['EMA_50']:
                print(f"🔴 VENTE TENDANCE sur {symbol} à {price}$", flush=True)
                exchange.create_market_sell_order(symbol, open_position['contracts'])
                send_telegram_message(f"🔴 VENTE sur {symbol} à {price}$")
                return f"Position fermée (Tendance) sur {symbol}"
            else:
                return f"🟡 Position en cours sur {symbol} (Achat: {entry_price}$, Actuel: {price}$, SL: {sl_type})"
                
        else:
            if price > last['EMA_200'] and last['EMA_20'] > last['EMA_50']:
                try:
                    balance = exchange.fetch_balance()
                    free_usdc = balance['USDC']['free']
                    
                    if free_usdc < 10:
                        return f"⚠️ Solde insuffisant ({free_usdc}$) pour trader {symbol}"

                    signal_msg = f"🟢 ACHAT sur {symbol} à {price:.2f}$"
                    
                    amount = 10 / price 
                    amount = float(exchange.amount_to_precision(symbol, amount))
                    
                    order = exchange.create_order(symbol, 'market', 'buy', amount)
                    signal_msg += f"\n✅ Position ouverte ! Taille: {amount} {symbol.split('/')[0]}"
                    send_telegram_message(signal_msg)
                    return signal_msg
                except Exception as e:
                    return f"❌ Erreur achat {symbol}: {e}"
            elif price < last['EMA_200']:
                return f"🔴 ATTENTE sur {symbol} (Sous EMA 200)"
            else:
                return f"🟡 NEUTRE sur {symbol}"
            
    except Exception as e:
        return f"Erreur sur {symbol}: {e}"

def bot_loop():
    while True:
        print(f"\n--- Analyse du {pd.Timestamp.now()} ---", flush=True) 
        for crypto in cryptos:
            print(check_signal(crypto), flush=True)
            time.sleep(2)
        
        print("Attente de 4 heures avant la prochaine analyse...", flush=True)
        time.sleep(14400)

@app.route('/')
def home():
    return "Bot Hyperliquid (Trailing Stop Activé) en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
