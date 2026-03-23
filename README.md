# Assista Kouamé — Bot Userbot Telegram Multi-IA

## Variables d'environnement à configurer sur Render

| Variable              | Description                                         |
|-----------------------|-----------------------------------------------------|
| TELEGRAM_API_ID       | API ID (my.telegram.org)                           |
| TELEGRAM_API_HASH     | API Hash (my.telegram.org)                         |
| TELEGRAM_SESSION      | Session Telethon (generate_session.py)             |
| ADMIN_ID              | Ton ID Telegram en chiffres (@userinfobot)         |
| TELEGRAM_BOT_TOKEN    | Token bot admin — optionnel                        |
| PORT                  | Port healthcheck (défaut: 5000)                    |

## Commandes Render
- Build : pip install -r requirements.txt
- Start : python main.py

## Ajouter les clés IA
Après démarrage : envoyer /menu sur Telegram → 🤖 Fournisseurs IA
