"""
Bot Userbot — Sossou Kouamé Apollinaire
- Mode SETUP  : /connect dans le bot pour générer la session Telegram
- Mode USERBOT: Répond automatiquement depuis le vrai compte Telegram de Sossou
- Render.com  : Serveur HTTP port 10000 intégré pour le health-check
"""
import os
import re
import json
import time
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, date
from pathlib import Path
from groq import Groq

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Chargement config (credentials + paramètres) ────────────────────────────

CONFIG_FILE = "config.json"
SESSION_FILE = "session.txt"

DEFAULT_CONFIG = {
    "credentials": {
        "telegram_api_id": "",
        "telegram_api_hash": "",
        "bot_token": "",
        "groq_api_key": "",
        "telegram_session": "",
        "admin_id": "1190237801"
    },
    "daily_quota": 100,
    "quota_used_today": 0,
    "quota_date": str(date.today()),
    "delay_seconds": 30,
    "reply_delay_seconds": 5,
    "ai_model": "llama-3.3-70b-versatile",
    "auto_reply_enabled": True,
    "groq_api_key": "",
    "daily_program": "",
    "knowledge_base": [
        "Je m'appelle Sossou Kouamé Apollinaire, je suis développeur professionnel.",
        "Je propose des formations sur le jeu Baccara 1xbet : 90 dollars — Formation complète avec stratégies et techniques gagnantes.",
        "Je crée des bots Telegram personnalisés avec hébergement inclus : 30 dollars — Bot clé en main, hébergement pris en charge.",
        "Je propose des stratégies professionnelles pour les cartes enseignes Baccara : 50 dollars — Stratégie testée et efficace.",
        "Je suis expert en automatisation Telegram, développement de bots, et stratégies de jeu Baccara sur 1xbet.",
        "Mon numéro de contact WhatsApp : +2290195501564 — Les gens peuvent m'appeler ou m'écrire sur WhatsApp."
    ]
}


def load_config() -> dict:
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("quota_date") != str(date.today()):
            cfg["quota_used_today"] = 0
            cfg["quota_date"] = str(date.today())
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        if "credentials" not in cfg:
            cfg["credentials"] = DEFAULT_CONFIG["credentials"].copy()
        save_config(cfg)
        return cfg
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _get(cfg: dict, env_key: str, cfg_path: str, default: str = "") -> str:
    """Lit d'abord la variable d'env, sinon le config.json — pour Render.com."""
    return (
        os.environ.get(env_key)
        or cfg.get("credentials", {}).get(cfg_path)
        or default
    )


# ── Prompts IA ────────────────────────────────────────────────────────────────

def _time_context() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "matin"
    elif 12 <= hour < 14:
        return "midi"
    elif 14 <= hour < 18:
        return "après-midi"
    elif 18 <= hour < 22:
        return "soirée"
    else:
        return "nuit"


def _time_greeting() -> str:
    moment = _time_context()
    greetings = {
        "matin": "Bonjour",
        "midi": "Bonne journée",
        "après-midi": "Bon après-midi",
        "soirée": "Bonsoir",
        "nuit": "Bonsoir",
    }
    return greetings.get(moment, "Bonjour")


PROMPT_FIRST = """Tu es l'assistante virtuelle de Sossou Kouamé Apollinaire.

C'est le TOUT PREMIER message de cette personne. Présente-toi chaleureusement comme son assistante.

Commence par : "{greeting} ! 😊 Je suis l'assistante de Sossou Kouamé Apollinaire. Il est absent en ce moment, mais je suis là pour vous aider."

{program_block}

Services disponibles :
{knowledge_base}

Contact WhatsApp : +2290195501564

Règles :
- Parle à la 1ère personne en tant qu'assistante (pas comme si tu étais Sossou)
- Chaleureuse, polie, touche d'humour légère si approprié
- 2-3 phrases max pour ce message d'accueil
- Réponds dans la langue de l'interlocuteur"""

PROMPT_RETURNING = """Tu es Sossou Kouamé Apollinaire. L'interlocuteur te re-écrit après plus d'1 heure d'absence.

Accueille-le de nouveau naturellement comme un humain le ferait, selon le moment de la journée ({moment}).

{time_specific}

{program_block}

Services :
{knowledge_base}

Contact WhatsApp : +2290195501564

Règles :
- Parle comme Sossou lui-même (1ère personne : je, mon, mes…)
- Naturel, humain, chaleureux — comme si tu avais été occupé et tu revenais
- Ne dis PAS que tu es un assistant, sauf si on te le demande
- 2-3 phrases max
- Réponds dans la langue de l'interlocuteur"""

PROMPT_ONGOING = """Tu es Sossou Kouamé Apollinaire. Tu réponds à ta place pendant ton absence.

{program_block}

Services et tarifs :
{knowledge_base}

Contact WhatsApp : +2290195501564

Règles importantes :
- Parle toujours à la 1ère personne (je, mon, mes…)
- Ne te présente PLUS, la personne te connaît déjà
- Réponds à TOUTES les questions, pas seulement le Baccara
- Si on demande ton numéro : "+2290195501564, tu peux aussi m'appeler sur WhatsApp"
- Si on demande si tu es un bot : "Non, c'est mon téléphone qui répond automatiquement quand je suis occupé 😄"
- Bref, clair, direct avec une touche d'humour légère 😄
- 2-4 phrases max
- Réponds dans la langue de l'interlocuteur"""


def build_prompt(contact_type: str, config: dict) -> str:
    kb = "\n".join(f"- {item}" for item in config["knowledge_base"])
    program = config.get("daily_program", "").strip()
    greeting = _time_greeting()
    moment = _time_context()

    program_block = (
        f"Programme du jour de Sossou : {program}" if program
        else "Aucun programme spécifique aujourd'hui."
    )

    time_hints = {
        "matin": "Le matin : demande comment s'est passée sa nuit, s'il est bien reposé.",
        "midi": "C'est l'heure du déjeuner : demande-lui s'il a bien mangé. S'il dit oui, souhaite-lui une bonne digestion 😄",
        "après-midi": "L'après-midi : demande comment se passe sa journée.",
        "soirée": "C'est le soir : demande comment s'est passée sa journée.",
        "nuit": "C'est la nuit : demande s'il est encore debout, souhaite-lui une bonne nuit si c'est tard.",
    }
    time_specific = time_hints.get(moment, "")

    if contact_type == "first":
        return PROMPT_FIRST.format(
            greeting=greeting,
            program_block=program_block,
            knowledge_base=kb
        )
    elif contact_type == "returning":
        return PROMPT_RETURNING.format(
            moment=moment,
            time_specific=time_specific,
            program_block=program_block,
            knowledge_base=kb
        )
    else:
        return PROMPT_ONGOING.format(
            program_block=program_block,
            knowledge_base=kb
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SERVEUR HTTP — Render.com health-check (port 10000)
# ══════════════════════════════════════════════════════════════════════════════

def start_health_server(port: int = 10000):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - Bot Sossou actif")
        def log_message(self, *args):
            pass

    port = int(os.environ.get("PORT", port))
    server = HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Health-check HTTP démarré sur le port {port}")


# ══════════════════════════════════════════════════════════════════════════════
#  MODE SETUP
# ══════════════════════════════════════════════════════════════════════════════

def run_setup_bot(BOT_TOKEN: str, API_ID: int, API_HASH: str, OWNER_ID: int, PHONE_NUMBER: str):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from pyrogram import Client as PyroClient
    from pyrogram.errors import SessionPasswordNeeded

    logger.info("=== MODE SETUP — Envoyez /connect dans le bot ===")
    auth_sessions: dict = {}

    async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("❌ Accès refusé.")
            return
        phone = PHONE_NUMBER
        if context.args:
            raw = context.args[0].strip()
            phone = raw if raw.startswith("+") else "+" + raw
        await update.message.reply_text(f"📤 Envoi du code au *{phone}*...", parse_mode="Markdown")
        try:
            client = PyroClient(":memory:", api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await client.connect()
            sent = await client.send_code(phone)
            auth_sessions[update.effective_user.id] = {
                "client": client, "phone": phone,
                "phone_code_hash": sent.phone_code_hash, "awaiting_2fa": False,
            }
            await update.message.reply_text(
                "✅ *Code envoyé sur Telegram !*\n\nTapez `aa` suivi du code\nEx: `aa12345`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur : {e}")

    async def handle_aa_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in auth_sessions:
            return
        text = (update.message.text or "").strip()
        if not text.lower().startswith("aa"):
            return
        code = text[2:].strip()
        if not code:
            await update.message.reply_text("❌ Code vide. Tapez : `aa12345`", parse_mode="Markdown")
            return
        state = auth_sessions[user_id]
        client: PyroClient = state["client"]
        try:
            await client.sign_in(state["phone"], state["phone_code_hash"], code)
        except SessionPasswordNeeded:
            await update.message.reply_text("🔐 2FA requis. Tapez : `pass <mot_de_passe>`", parse_mode="Markdown")
            auth_sessions[user_id]["awaiting_2fa"] = True
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur : {e}")
            return
        await _finish_auth(client, update, user_id, auth_sessions)

    async def handle_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = auth_sessions.get(user_id, {})
        if not state.get("awaiting_2fa"):
            return
        text = (update.message.text or "").strip()
        if not text.lower().startswith("pass "):
            return
        try:
            await state["client"].check_password(text[5:].strip())
            await _finish_auth(state["client"], update, user_id, auth_sessions)
        except Exception as e:
            await update.message.reply_text(f"❌ Mot de passe incorrect : {e}")

    async def _finish_auth(client, update, user_id, auth_sessions):
        session_string = await client.export_session_string()
        await client.disconnect()
        del auth_sessions[user_id]
        with open(SESSION_FILE, "w") as f:
            f.write(session_string)
        logger.info("✅ Session générée → session.txt")
        await update.message.reply_text(
            "✅ *CONNEXION RÉUSSIE !*\n\n"
            "Ajoutez cette valeur dans les secrets Replit ou config.json :\n"
            "`credentials.telegram_session`\n\n"
            f"`{session_string}`",
            parse_mode="Markdown"
        )

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            return
        await update.message.reply_text(
            "🛠 *Mode Setup*\n\n`/connect` — Connecter\nPuis : `aa<code>`",
            parse_mode="Markdown"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^pass "), handle_pass))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^aa"), handle_aa_code))
    logger.info("Bot setup démarré. Envoyez /connect dans le bot.")
    app.run_polling(drop_pending_updates=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MODE USERBOT
# ══════════════════════════════════════════════════════════════════════════════

SESSION_TIMEOUT = 3600  # 1 heure d'inactivité → re-saluer

def run_userbot(API_ID: int, API_HASH: str, BOT_TOKEN: str, GROQ_API_KEY: str,
                SESSION_STRING: str, OWNER_ID: int):
    from pyrogram import Client, filters as f
    from pyrogram.types import Message

    config = load_config()
    active_key = config.get("groq_api_key") or GROQ_API_KEY
    groq_holder = [Groq(api_key=active_key)]

    conversation_history: dict[int, list] = {}
    pending_tasks: dict[int, asyncio.Task] = {}
    known_users: set = set()
    last_user_message: dict[int, float] = {}
    stopped_chats: set = set()
    program_state = {"waiting": False}

    # ── IA ────────────────────────────────────────────────────────────────────

    def check_quota() -> bool:
        today = str(date.today())
        if config.get("quota_date") != today:
            config["quota_used_today"] = 0
            config["quota_date"] = today
        if config["quota_used_today"] >= config["daily_quota"]:
            return False
        config["quota_used_today"] += 1
        save_config(config)
        return True

    async def get_ai_reply(user_id: int, text: str, contact_type: str) -> str:
        if not check_quota():
            return (
                "Je suis absent en ce moment. Mon assistant a atteint son quota journalier. "
                "Laissez votre message, je vous réponds très bientôt ! 🙏"
            )
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        conversation_history[user_id].append({"role": "user", "content": text})
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]
        try:
            resp = groq_holder[0].chat.completions.create(
                model=config["ai_model"],
                messages=[{"role": "system", "content": build_prompt(contact_type, config)}]
                         + conversation_history[user_id],
                max_tokens=400,
                temperature=0.80,
            )
            reply = resp.choices[0].message.content.strip()
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            logger.info(f"IA [{contact_type}] → {user_id} | quota {config['quota_used_today']}/{config['daily_quota']}")
            return reply
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return "Je suis momentanément indisponible. Laissez votre message, je vous réponds dès que possible. 🙏"

    # ── Notification admin ────────────────────────────────────────────────────

    async def notify_admin(user):
        import urllib.request
        import json as _json
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        text = (
            f"🔔 Nouveau message reçu !\n\n"
            f"👤 {name} ({username})\n"
            f"🆔 ID: {user.id}\n\n"
            f"Mon assistant va répondre dans {config['delay_seconds']}s si tu ne réponds pas.\n\n"
            f"Tape /stop pour prendre le contrôle de ce chat."
        )
        loop = asyncio.get_event_loop()
        def _send():
            try:
                payload = _json.dumps({"chat_id": OWNER_ID, "text": text}).encode()
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10):
                    pass
            except Exception as e:
                logger.warning(f"Notif admin échouée: {e}")
        await loop.run_in_executor(None, _send)

    # ── Tâche de réponse auto ─────────────────────────────────────────────────

    async def auto_reply_task(client, message: Message, contact_type: str):
        try:
            # 1er ou nouveau contact → délai d'absence (admin a le temps de répondre lui-même)
            # Conversation en cours → délai court (bot déjà actif, répond vite)
            if contact_type in ("first", "returning"):
                wait = config["delay_seconds"]
            else:
                wait = config.get("reply_delay_seconds", 5)
            await asyncio.sleep(wait)
            if not config.get("auto_reply_enabled", True):
                return
            if message.chat.id in stopped_chats:
                return
            text = message.text or message.caption or f"[{message.media}]"
            reply = await get_ai_reply(message.from_user.id, text, contact_type)
            await message.reply(reply)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erreur auto-reply: {e}")

    def is_command(text: str | None) -> bool:
        return bool(text and re.match(r"^/\w+", text.strip()))

    # ── Client Pyrogram ───────────────────────────────────────────────────────

    app = Client("sossou_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

    # ── Handler : messages entrants ───────────────────────────────────────────

    @app.on_message(f.private & f.incoming & ~f.me, group=0)
    async def on_incoming(client: Client, message: Message):
        if not config.get("auto_reply_enabled", True):
            return
        user = message.from_user
        if not user or user.is_bot:
            return

        chat_id = message.chat.id
        now = time.time()
        first_contact = user.id not in known_users
        last_time = last_user_message.get(user.id, 0)
        is_returning = (not first_contact) and ((now - last_time) > SESSION_TIMEOUT)
        last_user_message[user.id] = now

        # Déterminer le type de contact pour le prompt
        if first_contact:
            contact_type = "first"
            known_users.add(user.id)
            # Vider l'historique (nouveau contact)
            conversation_history.pop(user.id, None)
            try:
                await notify_admin(user)
            except Exception as e:
                logger.warning(f"Notif admin échouée (non bloquant): {e}")
        elif is_returning:
            contact_type = "returning"
            # Réinitialiser l'historique pour la nouvelle session
            conversation_history.pop(user.id, None)
            logger.info(f"↩️ {user.first_name} revient après {int(now - last_time)}s")
        else:
            contact_type = "ongoing"

        t = pending_tasks.get(chat_id)
        if t and not t.done():
            t.cancel()

        pending_tasks[chat_id] = asyncio.create_task(
            auto_reply_task(client, message, contact_type)
        )
        actual_wait = config["delay_seconds"] if contact_type in ("first", "returning") else config.get("reply_delay_seconds", 5)
        logger.info(f"📨 {user.first_name} ({chat_id}) [{contact_type}] → auto dans {actual_wait}s")

    # ── Handler : messages sortants (admin répond manuellement) ──────────────

    @app.on_message(f.private & f.outgoing & f.me, group=1)
    async def on_outgoing(client: Client, message: Message):
        text = message.text or ""
        if is_command(text):
            return

        # Capturer la réponse au programme si en attente
        if program_state["waiting"]:
            program_state["waiting"] = False
            config["daily_program"] = text.strip()
            save_config(config)
            await message.reply(
                f"✅ Programme enregistré !\n\n"
                f"📅 *{config['daily_program']}*\n\n"
                f"L'assistante l'utilisera dans ses réponses.",
            )
            return

        chat_id = message.chat.id
        t = pending_tasks.get(chat_id)
        if t and not t.done():
            t.cancel()
            logger.info(f"✋ Auto-réponse annulée pour {chat_id} (tu as répondu)")

    # ── Commandes admin ───────────────────────────────────────────────────────

    async def _parse_cmd(message: Message) -> tuple[str, list[str]]:
        parts = (message.text or "").strip().split()
        cmd = parts[0].lstrip("/").lower() if parts else ""
        return cmd, parts[1:]

    @app.on_message(f.me & f.regex(r"^/program(\s|$)"), group=-1)
    async def cmd_program(client: Client, message: Message):
        parts = (message.text or "").strip().split(maxsplit=1)
        if len(parts) >= 2 and parts[1].strip():
            config["daily_program"] = parts[1].strip()
            save_config(config)
            await message.reply(f"✅ Programme enregistré :\n📅 *{config['daily_program']}*")
        else:
            current = config.get("daily_program", "")
            program_state["waiting"] = True
            msg = "📅 Quel est votre programme pour aujourd'hui ?\n\n_(Tapez votre programme dans le prochain message)_"
            if current:
                msg += f"\n\nProgramme actuel : _{current}_"
            await message.reply(msg)

    @app.on_message(f.me & f.regex(r"^/clearprogram(\s|$)"), group=-1)
    async def cmd_clearprogram(client: Client, message: Message):
        config["daily_program"] = ""
        save_config(config)
        await message.reply("✅ Programme effacé. L'assistante ne mentionnera plus de programme.")

    @app.on_message(f.me & f.regex(r"^/stop(\s|$)"), group=-1)
    async def cmd_stop(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if args and args[0].lstrip("-").isdigit():
            cid = int(args[0])
            stopped_chats.add(cid)
            await message.reply(f"🛑 Auto-réponse arrêtée pour le chat `{cid}`")
        else:
            config["auto_reply_enabled"] = False
            save_config(config)
            await message.reply("🛑 Auto-réponse globale désactivée.\n\nEnvoie `/resume` pour réactiver.")

    @app.on_message(f.me & f.regex(r"^/resume(\s|$)"), group=-1)
    async def cmd_resume(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if args and args[0].lstrip("-").isdigit():
            cid = int(args[0])
            stopped_chats.discard(cid)
            await message.reply(f"✅ Auto-réponse réactivée pour le chat `{cid}`")
        else:
            config["auto_reply_enabled"] = True
            save_config(config)
            stopped_chats.clear()
            await message.reply(f"✅ Auto-réponse globale réactivée.\n\nDélai : {config['delay_seconds']}s.")

    @app.on_message(f.me & f.regex(r"^/setdelay(\s|$)"), group=-1)
    async def cmd_setdelay(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if not args or not args[0].isdigit():
            await message.reply(f"❌ Usage : `/setdelay <secondes>`\n\nDélai actuel : {config['delay_seconds']}s")
            return
        config["delay_seconds"] = int(args[0])
        save_config(config)
        await message.reply(
            f"✅ Délai d'absence mis à jour : **{config['delay_seconds']}s**\n\n"
            f"_(Délai de réponse conversation en cours : {config.get('reply_delay_seconds', 5)}s)_"
        )

    @app.on_message(f.me & f.regex(r"^/setreplydelay(\s|$)"), group=-1)
    async def cmd_setreplydelay(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if not args or not args[0].isdigit():
            await message.reply(
                f"❌ Usage : `/setreplydelay <secondes>`\n\n"
                f"Délai de réponse actuel (conversation en cours) : {config.get('reply_delay_seconds', 5)}s\n"
                f"Délai d'absence (1er/nouveau message) : {config['delay_seconds']}s"
            )
            return
        config["reply_delay_seconds"] = int(args[0])
        save_config(config)
        await message.reply(
            f"✅ Délai de réponse mis à jour : **{config['reply_delay_seconds']}s** (conversation en cours)\n\n"
            f"_(Délai d'absence 1er message : {config['delay_seconds']}s)_"
        )

    @app.on_message(f.me & f.regex(r"^/setquota(\s|$)"), group=-1)
    async def cmd_setquota(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if not args or not args[0].isdigit():
            await message.reply(
                f"❌ Usage : `/setquota <nombre>`\n\n"
                f"Quota actuel : {config['daily_quota']}/jour\n"
                f"Utilisé aujourd'hui : {config['quota_used_today']}"
            )
            return
        config["daily_quota"] = int(args[0])
        save_config(config)
        await message.reply(f"✅ Quota : **{config['daily_quota']} appels/jour**")

    @app.on_message(f.me & f.regex(r"^/setmodel(\s|$)"), group=-1)
    async def cmd_setmodel(client: Client, message: Message):
        parts = (message.text or "").strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(
                f"❌ Usage : `/setmodel <modèle>`\n\nModèle actuel : `{config['ai_model']}`\n\n"
                "**Modèles Groq :**\n"
                "• `llama-3.3-70b-versatile` — Recommandé\n"
                "• `llama-3.1-8b-instant` — Ultra rapide\n"
                "• `mixtral-8x7b-32768` — Contexte long\n"
                "• `gemma2-9b-it` — Léger"
            )
            return
        config["ai_model"] = parts[1].strip()
        save_config(config)
        await message.reply(f"✅ Modèle : **{config['ai_model']}**")

    @app.on_message(f.me & f.regex(r"^/setapi(\s|$)"), group=-1)
    async def cmd_setapi(client: Client, message: Message):
        parts = (message.text or "").strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            current = config.get("groq_api_key") or GROQ_API_KEY
            masked = current[:8] + "..." + current[-4:] if len(current) > 12 else "***"
            await message.reply(
                f"❌ Usage : `/setapi <clé_groq>`\n\nClé actuelle : `{masked}`\n\nhttps://console.groq.com/keys"
            )
            return
        new_key = parts[1].strip()
        try:
            test_client = Groq(api_key=new_key)
            test_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
        except Exception as e:
            await message.reply(f"❌ Clé invalide :\n`{e}`")
            return
        config["groq_api_key"] = new_key
        config["credentials"]["groq_api_key"] = new_key
        save_config(config)
        groq_holder[0] = Groq(api_key=new_key)
        masked = new_key[:8] + "..." + new_key[-4:]
        await message.reply(f"✅ Clé API Groq mise à jour : `{masked}`")

    @app.on_message(f.me & f.regex(r"^/addinfo(\s|$)"), group=-1)
    async def cmd_addinfo(client: Client, message: Message):
        text = (message.text or "").strip()
        info = text[len("/addinfo"):].strip()
        if not info:
            await message.reply("❌ Usage : `/addinfo <information>`")
            return
        config["knowledge_base"].append(info)
        save_config(config)
        await message.reply(f"✅ Info ajoutée ({len(config['knowledge_base'])} total) :\n_{info}_")

    @app.on_message(f.me & f.regex(r"^/removeinfo(\s|$)"), group=-1)
    async def cmd_removeinfo(client: Client, message: Message):
        _, args = await _parse_cmd(message)
        if not args or not args[0].isdigit():
            listing = "\n".join(f"{i+1}. {it}" for i, it in enumerate(config["knowledge_base"]))
            await message.reply(f"❌ Usage : `/removeinfo <n>`\n\n**Base actuelle :**\n{listing}")
            return
        idx = int(args[0]) - 1
        if not (0 <= idx < len(config["knowledge_base"])):
            await message.reply(f"❌ Numéro invalide (1 à {len(config['knowledge_base'])})")
            return
        removed = config["knowledge_base"].pop(idx)
        save_config(config)
        await message.reply(f"✅ Supprimé :\n_{removed}_")

    @app.on_message(f.me & f.regex(r"^/stats(\s|$)"), group=-1)
    async def cmd_stats(client: Client, message: Message):
        used = config["quota_used_today"]
        total = config["daily_quota"]
        pct = int((used / total) * 100) if total > 0 else 0
        status = "✅ Active" if config.get("auto_reply_enabled", True) else "🛑 Arrêtée"
        pending = sum(1 for t in pending_tasks.values() if not t.done())
        kb = "\n".join(f"  {i+1}. {it}" for i, it in enumerate(config["knowledge_base"]))
        current_key = config.get("groq_api_key") or GROQ_API_KEY
        masked_key = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
        program = config.get("daily_program") or "_(aucun programme défini)_"
        await message.reply(
            f"📊 **Bot Sossou Kouamé — Stats**\n\n"
            f"🔄 Auto-réponse : {status}\n"
            f"🤖 Modèle IA : `{config['ai_model']}`\n"
            f"🔑 Clé Groq : `{masked_key}`\n"
            f"📈 Quota : {used}/{total} ({pct}%) aujourd'hui\n"
            f"⏱ Délai absence (1er msg) : {config['delay_seconds']}s\n"
            f"⚡ Délai réponse (en cours) : {config.get('reply_delay_seconds', 5)}s\n"
            f"⏳ Réponses en attente : {pending}\n"
            f"👥 Contacts connus : {len(known_users)}\n"
            f"📅 Programme du jour : {program}\n\n"
            f"📚 Base de connaissances ({len(config['knowledge_base'])} entrées) :\n{kb}"
        )

    @app.on_message(f.me & f.regex(r"^/help(\s|$)"), group=-1)
    async def cmd_help(client: Client, message: Message):
        await message.reply(
            "🛠 **Commandes Admin**\n\n"
            "📊 `/stats` — Tout voir\n\n"
            "🛑 `/stop` — Désactiver l'auto-réponse\n"
            "✅ `/resume` — Réactiver l'auto-réponse\n\n"
            "📅 `/program` — Définir le programme du jour\n"
            "🗑 `/clearprogram` — Effacer le programme\n\n"
            "⏱ `/setdelay 30` — Délai d'absence (1er message, en secondes)\n"
            "⚡ `/setreplydelay 5` — Délai de réponse (conversation en cours)\n"
            "🔢 `/setquota 200` — Quota appels IA/jour\n"
            "🧠 `/setmodel llama-3.3-70b-versatile` — Modèle IA\n"
            "🔑 `/setapi <clé>` — Changer la clé API Groq\n\n"
            "➕ `/addinfo <texte>` — Ajouter une info\n"
            "➖ `/removeinfo <n>` — Supprimer une info\n"
        )

    logger.info("═══════════════════════════════════════════════")
    logger.info("  MODE USERBOT — Sossou Kouamé Apollinaire")
    logger.info(f"  Modèle : {config['ai_model']}")
    logger.info(f"  Délai  : {config['delay_seconds']}s | Quota : {config['daily_quota']}/jour")
    logger.info(f"  Session inactivité : {SESSION_TIMEOUT//60} min → re-salutation")
    logger.info("  Commandes admin : /help dans n'importe quel chat")
    logger.info("═══════════════════════════════════════════════")
    app.run()


# ══════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cfg = load_config()

    PHONE_NUMBER   = "+22995501564"
    OWNER_ID       = int(_get(cfg, "ADMIN_ID",            "admin_id",          "1190237801"))
    API_ID         = int(_get(cfg, "TELEGRAM_API_ID",     "telegram_api_id",   "0") or "0")
    API_HASH       = _get(cfg, "TELEGRAM_API_HASH",       "telegram_api_hash",  "")
    BOT_TOKEN      = _get(cfg, "TELEGRAM_BOT_TOKEN",      "bot_token",          "")
    GROQ_API_KEY   = _get(cfg, "GROQ_API_KEY",            "groq_api_key",       "")
    SESSION_STRING = _get(cfg, "TELEGRAM_SESSION",        "telegram_session",   "")

    if not API_ID or not API_HASH:
        raise ValueError("TELEGRAM_API_ID et TELEGRAM_API_HASH sont requis (env ou config.json).")

    # Démarrer le serveur HTTP (Render.com health-check)
    start_health_server()

    if SESSION_STRING:
        logger.info("✅ Session trouvée → Mode USERBOT")
        run_userbot(API_ID, API_HASH, BOT_TOKEN, GROQ_API_KEY, SESSION_STRING, OWNER_ID)
    elif BOT_TOKEN:
        logger.info("ℹ️  Mode SETUP → envoyez /connect dans le bot")
        run_setup_bot(BOT_TOKEN, API_ID, API_HASH, OWNER_ID, PHONE_NUMBER)
    else:
        raise ValueError("Il faut TELEGRAM_SESSION (userbot) ou TELEGRAM_BOT_TOKEN (setup).")
