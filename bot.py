import pandas as pd
import time, os, threading
from flask import Flask
from marginpad import MarginPad

app = Flask(__name__)

# Récupération de la clé API depuis les variables d'environnement Render
API_KEY = os.environ.get("MARGINPAD_API_KEY")
mp = MarginPad(API_KEY)

# MarginPad fonctionne avec des paires comme BTC, ETH, SOL
cryptos = ['BTC', 'ETH', 'SOL']

def check_signal(symbol):
    try:
        print(f"Analyse de {symbol}...", flush=True)
        
        # Récupération du prix en direct (données publiques, pas besoin de clé pour ça)
        current_price = mp.price(symbol)
        
        # Pour calculer les SMA, on a besoin d'un historique.
        # MarginPad ne fournit pas directement de bougies OHLCV, 
        # on va donc simuler un historique simple en attendant.
        # (Note: Pour un backtest précis, on utiliserait l'outil de Verdroid,
        # ici on passe à l'exécution en direct)
        
        # --- STRATÉGIE SIMPLIFIÉE POUR LE TEST EN DIRECT ---
        # On va utiliser une logique de prix simple pour l'exemple.
        # Dans un vrai bot, on récupérerait les 200 dernières bougies via un autre fournisseur.
        # Pour l'instant, on va juste tester que l'ordre passe.
        
        # TEST FORCÉ pour valider la connexion
        signal_msg = f"🟢 [TEST] ACHAT de {symbol} à {current_price}$"
        try:
            # Ouverture d'une position virtuelle (papier)
            # On mise 100$ avec un levier de 1 (pas de levier pour simplifier)
            pos = mp.open(symbol, "long", margin_usd=100, leverage=1)
            signal_msg += f"\n✅ Position ouverte sur MarginPad ! ID: {pos.get('id')}"
        except Exception as e:
            signal_msg += f"\n❌ Erreur: {e}"
        return signal_msg

    except Exception as e:
        return f"Erreur sur {symbol}: {e}"

def bot_loop():
    while True:
        print(f"\n--- Analyse du {pd.Timestamp.now()} ---", flush=True)
        for crypto in cryptos:
            print(check_signal(crypto), flush=True)
        
        print("Attente de 1 heure...", flush=True)
        time.sleep(3600)

@app.route('/')
def home():
    return "Bot MarginPad en ligne !"

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
