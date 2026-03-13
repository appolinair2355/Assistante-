# config.py — Variables preconfigurées pour Render.com
# ⚠️  NE PAS PARTAGER — contient vos clés privées
import os

TELEGRAM_API_ID     = int(os.environ.get("TELEGRAM_API_ID",    "29177661"))
TELEGRAM_API_HASH   = os.environ.get("TELEGRAM_API_HASH",      "a8639172fa8d35dbfd8ea46286d349ab")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN",     "7723846517:AAHPedKmAXPOlTC9XvwjUtBlvjZ01n-IozU")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY",           "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")
TELEGRAM_SESSION    = os.environ.get("TELEGRAM_SESSION",       "1BJWap1wBuyNQ-b1Ql8aEn2BBr6dNMeB4wMhzgCf7LQzDrJ7KuAqvPH0IxvbkBCvfI4bipPBTVT2dROJ58PDhqGQZAyube4OkbmFBaPRFPRTvUebN_SZH_3zoi3Ko76_y_HA4qHFsoKbgKfU-6NyqaEk8NVI5lHl4RRCsy6pm9oTngQa0pGZPTHuBNeGN4_CBo5VJfsRJH-tnh01Do2ACPGZDv_awqZrAv99ITL8FMCJrNy-cwCfTIZ_KX9vVGnqe-pklKhZ5_1zUTCKbio2czYz7XBAsDiXGgIacVcnARRfaGCJGBRomALXLg5BMLBlzqeFPaGT16wVTFOokGEGuJLIZUVGQfV0=")
ADMIN_ID            = int(os.environ.get("ADMIN_ID",           "1190237801"))
PORT                = int(os.environ.get("PORT",               "10000"))
PHONE_NUMBER        = "+22995501564"
