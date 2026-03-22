# config.py — Credentials du bot
import os

TELEGRAM_API_ID    = int(os.environ.get("TELEGRAM_API_ID", "29177661"))
TELEGRAM_API_HASH  = os.environ.get("TELEGRAM_API_HASH", "a8639172fa8d35dbfd8ea46286d349ab")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
ADMIN_ID           = int(os.environ.get("ADMIN_ID", "1190237801"))
PORT               = int(os.environ.get("PORT", "10000"))
PHONE_NUMBER       = os.environ.get("PHONE_NUMBER", "+22995501564")
TELEGRAM_SESSION   = os.environ.get("TELEGRAM_SESSION", "")
