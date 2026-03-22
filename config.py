# config.py — Variables d environnement préconfigurées
# À utiliser sur Render.com : ne pas partager publiquement
import os

TELEGRAM_API_ID     = int(os.environ.get("TELEGRAM_API_ID",    "29177661"))
TELEGRAM_API_HASH   = os.environ.get("TELEGRAM_API_HASH",      "a8639172fa8d35dbfd8ea46286d349ab")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN",     "8442253971:AAEisYucgZ49Ej2b-mK9_6DhNrqh9WOc_XU")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY",           "")
TELEGRAM_SESSION    = os.environ.get("TELEGRAM_SESSION",       "")
ADMIN_ID            = int(os.environ.get("ADMIN_ID",           "1190237801"))
PORT                = int(os.environ.get("PORT",               "10000"))
PHONE_NUMBER        = "+22995501564"
