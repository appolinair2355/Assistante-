# Assista Kouamé — Bot Userbot Telegram Multi-IA

## Variables d'environnement requis sur Render/Railway

| Variable            | Description                          |
|---------------------|--------------------------------------|
| TELEGRAM_API_ID     | Votre API ID (my.telegram.org)      |
| TELEGRAM_API_HASH   | Votre API Hash (my.telegram.org)    |
| TELEGRAM_SESSION    | Session Telethon (générer via generate_session.py) |
| ADMIN_ID            | Votre ID Telegram numérique          |
| TELEGRAM_BOT_TOKEN  | Token du bot admin (optionnel)       |
| PORT                | Port HTTP healthcheck (défaut: 5000) |

## Étapes de déploiement

1. Générer la session : python generate_session.py (en local)
2. Copier la chaîne dans TELEGRAM_SESSION (variable d'env)
3. Déployer sur Render (render.yaml inclus)
4. Envoyer /menu à votre compte Telegram
5. Aller dans 🤖 Fournisseurs IA et ajouter vos clés API

## Fournisseurs IA (aucune clé pré-configurée)
- Groq (gratuit)  : console.groq.com
- Gemini (gratuit): aistudio.google.com  
- OpenAI          : platform.openai.com
- Anthropic       : console.anthropic.com
- Mistral         : console.mistral.ai

Le bot bascule automatiquement vers la clé suivante si une expire.
Plusieurs clés par fournisseur supportées.
