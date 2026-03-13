# config.py — Variables d environnement préconfigurées
# À utiliser sur Render.com : ne pas partager publiquement
import os

TELEGRAM_API_ID     = int(os.environ.get("TELEGRAM_API_ID",    "29177661"))
TELEGRAM_API_HASH   = os.environ.get("TELEGRAM_API_HASH",      "a8639172fa8d35dbfd8ea46286d349ab")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN",     "7723846517:AAHPedKmAXPOlTC9XvwjUtBlvjZ01n-IozU")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY",           "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")
TELEGRAM_SESSION    = os.environ.get("TELEGRAM_SESSION",       "BAG9Nz0AhecsiqUh74LQiuScHZYsSrRJZj7Mcrm8EAOwZKG2dXxthPmz9A-rNou6sGyU5DpTURM6WXMMF5mSjv8R_utPWr1xmhQoLM9taB0u7y9KzxfWNSACOzOCieSL2kMrCZyUn-xM-1MFur_UlEz67qOo2wLhnK-GTVyWRSXiRbYALUbbxlPnsWiXB0NZubz48ESyF9L5d14dIPjB73t-WLq2ySm0MBjCHJH6BIXipjjJs4rXgZj8FAbtOm-0x4nndzu3uKqyq_4l-zx8eMpfu1T_QgOxkakdXc938cTd2WlJEOj6Xt6v8U3KqObjQQEo4c2ZqoxhXe_1ZNq9GfAPej9R4wAAAABG8ZZpAA")
ADMIN_ID            = int(os.environ.get("ADMIN_ID",           "1190237801"))
PORT                = int(os.environ.get("PORT",               "10000"))
PHONE_NUMBER        = "+22995501564"

