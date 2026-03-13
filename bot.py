"""
Bot Userbot — Sossou Kouamé Apollinaire
Bibliothèque : Telethon (compatible Python 3.12 / 3.14)
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

# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG_FILE  = "config.json"
SESSION_FILE = "session.txt"

DEFAULT_CONFIG = {
    "credentials": {
        "telegram_api_id":   "",
        "telegram_api_hash": "",
        "bot_token":         "",
        "groq_api_key":      "",
        "telegram_session":  "",
        "admin_id":          "1190237801"
    },
    "daily_quota":        100,
    "quota_used_today":   0,
    "quota_date":         str(date.today()),
    "delay_seconds":      30,
    "reply_delay_seconds": 5,
    "ai_model":           "llama-3.3-70b-versatile",
    "auto_reply_enabled": True,
    "groq_api_key":       "",
    "daily_program":      "",
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
    """Lit d'abord la variable d'env, sinon config.json — pour Render.com."""
    return (
        os.environ.get(env_key)
        or cfg.get("credentials", {}).get(cfg_path)
        or default
    )


# ─── Prompts IA ───────────────────────────────────────────────────────────────

SESSION_TIMEOUT = 3600  # 1h d'inactivité → re-salutation

def _time_context() -> str:
    h = datetime.now().hour
    if 5  <= h < 12: return "matin"
    if 12 <= h < 14: return "midi"
    if 14 <= h < 18: return "après-midi"
    if 18 <= h < 22: return "soirée"
    return "nuit"

def _time_greeting() -> str:
    return {"matin": "Bonjour", "midi": "Bonne journée",
            "après-midi": "Bon après-midi", "soirée": "Bonsoir",
            "nuit": "Bonsoir"}.get(_time_context(), "Bonjour")

PROMPT_FIRST = """Tu es l'assistante virtuelle de Sossou Kouamé Apollinaire.
C'est le TOUT PREMIER message de cette personne. Présente-toi comme son assistante.
Commence par : "{greeting} ! 😊 Je suis l'assistante de Sossou Kouamé Apollinaire. Il est absent en ce moment, mais je suis là pour vous aider."
{program_block}
Services : {knowledge_base}
Contact WhatsApp : +2290195501564
Règles : 1ère personne (assistante), chaleureuse, 2-3 phrases max, langue de l'interlocuteur."""

PROMPT_RETURNING = """Tu es Sossou Kouamé Apollinaire. L'interlocuteur revient après +1h.
Accueille-le de nouveau naturellement selon le moment ({moment}).
{time_specific}
{program_block}
Services : {knowledge_base}
Contact WhatsApp : +2290195501564
Règles : 1ère personne (je, mon…), naturel, humain, 2-3 phrases max, langue de l'interlocuteur."""

PROMPT_ONGOING = """Tu es Sossou Kouamé Apollinaire. Tu réponds à ta place pendant ton absence.
{program_block}
Services et tarifs : {knowledge_base}
Contact WhatsApp : +2290195501564
Règles : 1ère personne, ne te présente PLUS, réponds à TOUTES les questions, si on demande le numéro donne +2290195501564,
si on demande si tu es un bot : "Non, c'est mon téléphone qui répond automatiquement 😄",
bref, clair, 2-4 phrases, langue de l'interlocuteur."""

def build_prompt(contact_type: str, config: dict) -> str:
    kb       = "\n".join(f"- {item}" for item in config["knowledge_base"])
    program  = config.get("daily_program", "").strip()
    prog_blk = f"Programme du jour : {program}" if program else ""
    moment   = _time_context()
    time_map = {
        "matin":      "Demande comment s'est passée sa nuit, s'il est bien reposé.",
        "midi":       "Demande s'il a bien mangé. S'il dit oui → bonne digestion 😄",
        "après-midi": "Demande comment se passe sa journée.",
        "soirée":     "Demande comment s'est passée sa journée.",
        "nuit":       "Souhaite-lui une bonne nuit si c'est tard.",
    }
    if contact_type == "first":
        return PROMPT_FIRST.format(greeting=_time_greeting(), program_block=prog_blk, knowledge_base=kb)
    if contact_type == "returning":
        return PROMPT_RETURNING.format(moment=moment, time_specific=time_map.get(moment, ""),
                                       program_block=prog_blk, knowledge_base=kb)
    return PROMPT_ONGOING.format(program_block=prog_blk, knowledge_base=kb)


# ─── Serveur HTTP — Render.com health-check ───────────────────────────────────

def start_health_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - Bot Sossou actif")
        def log_message(self, *args): pass

    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Health-check HTTP sur le port {port}")


# ══════════════════════════════════════════════════════════════════════════════
#  MODE SETUP — génération de session Telethon
# ══════════════════════════════════════════════════════════════════════════════

def run_setup_bot(BOT_TOKEN: str, API_ID: int, API_HASH: str, OWNER_ID: int, PHONE_NUMBER: str):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError

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
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            result = await client.send_code_request(phone)
            auth_sessions[update.effective_user.id] = {
                "client": client,
                "phone": phone,
                "phone_code_hash": result.phone_code_hash,
                "awaiting_2fa": False,
            }
            await update.message.reply_text(
                "✅ *Code envoyé sur Telegram !*\n\nTapez `aa` suivi du code reçu\nEx: `aa12345`",
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
        state  = auth_sessions[user_id]
        client = state["client"]
        try:
            await client.sign_in(state["phone"], code=code, phone_code_hash=state["phone_code_hash"])
        except SessionPasswordNeededError:
            state["awaiting_2fa"] = True
            await update.message.reply_text("🔐 2FA requis. Tapez : `pass <mot_de_passe>`", parse_mode="Markdown")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur code : {e}")
            return
        await _finish_auth(client, update, user_id)

    async def handle_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = auth_sessions.get(user_id, {})
        if not state.get("awaiting_2fa"):
            return
        text = (update.message.text or "").strip()
        if not text.lower().startswith("pass "):
            return
        try:
            await state["client"].sign_in(password=text[5:].strip())
            await _finish_auth(state["client"], update, user_id)
        except Exception as e:
            await update.message.reply_text(f"❌ Mot de passe incorrect : {e}")

    async def _finish_auth(client, update, user_id):
        session_string = client.session.save()
        await client.disconnect()
        auth_sessions.pop(user_id, None)
        with open(SESSION_FILE, "w") as f:
            f.write(session_string)
        logger.info("✅ Session Telethon générée → session.txt")
        await update.message.reply_text(
            "✅ *CONNEXION RÉUSSIE !*\n\n"
            "Ajoutez dans les secrets Replit ou config.json :\n"
            "`TELEGRAM_SESSION` / `credentials.telegram_session`\n\n"
            f"`{session_string}`",
            parse_mode="Markdown"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^pass "), handle_pass))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^aa"),    handle_aa_code))
    logger.info("Bot setup prêt. Envoyez /connect.")
    app.run_polling(drop_pending_updates=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MODE USERBOT — Telethon
# ══════════════════════════════════════════════════════════════════════════════

def run_userbot(API_ID: int, API_HASH: str, BOT_TOKEN: str, GROQ_API_KEY: str,
                SESSION_STRING: str, OWNER_ID: int):
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    async def _main():
        config      = load_config()
        active_key  = config.get("groq_api_key") or GROQ_API_KEY
        groq_holder = [Groq(api_key=active_key)]

        conversation_history: dict[int, list]  = {}
        pending_tasks:        dict[int, asyncio.Task] = {}
        known_users:          set  = set()
        last_user_message:    dict[int, float] = {}
        stopped_chats:        set  = set()
        program_state = {"waiting": False}

        # ── IA ────────────────────────────────────────────────────────────────

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
                return ("Je suis absent. Mon assistant a atteint son quota journalier. "
                        "Laissez votre message, je vous réponds très bientôt ! 🙏")
            history = conversation_history.setdefault(user_id, [])
            history.append({"role": "user", "content": text})
            if len(history) > 20:
                conversation_history[user_id] = history[-20:]
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

        # ── Notification admin ────────────────────────────────────────────────

        async def notify_admin(user):
            import urllib.request, json as _j
            name     = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
            username = f"@{user.username}" if getattr(user, 'username', None) else f"ID: {user.id}"
            text = (f"🔔 Nouveau message reçu !\n\n"
                    f"👤 {name} ({username})\n🆔 ID: {user.id}\n\n"
                    f"Mon assistant va répondre dans {config['delay_seconds']}s si tu ne réponds pas.\n\n"
                    f"Tape /stop pour prendre le contrôle de ce chat.")
            loop = asyncio.get_event_loop()
            def _send():
                try:
                    payload = _j.dumps({"chat_id": OWNER_ID, "text": text}).encode()
                    req = urllib.request.Request(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data=payload, headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(req, timeout=10): pass
                except Exception as e:
                    logger.warning(f"Notif admin échouée: {e}")
            await loop.run_in_executor(None, _send)

        # ── Tâche de réponse auto ─────────────────────────────────────────────

        async def auto_reply_task(client, chat_id: int, user_id: int, text: str, contact_type: str):
            try:
                wait = config["delay_seconds"] if contact_type in ("first", "returning") \
                       else config.get("reply_delay_seconds", 5)
                await asyncio.sleep(wait)
                if not config.get("auto_reply_enabled", True):
                    return
                if chat_id in stopped_chats:
                    return
                reply = await get_ai_reply(user_id, text, contact_type)
                await client.send_message(chat_id, reply)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Erreur auto-reply: {e}")

        # ── Client Telethon ───────────────────────────────────────────────────

        try:
            client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session non autorisée")
        except Exception as e:
            logger.error(f"❌ Session invalide ou expirée : {e}")
            logger.error("➡️  Générez une nouvelle session Telethon via /connect dans le bot setup.")
            return

        # ── Handler : messages entrants ───────────────────────────────────────

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def on_incoming(event):
            if not config.get("auto_reply_enabled", True):
                return
            sender = await event.get_sender()
            if not sender or getattr(sender, "bot", False):
                return

            chat_id  = event.chat_id
            user_id  = sender.id
            now      = time.time()

            first_contact = user_id not in known_users
            last_time     = last_user_message.get(user_id, 0)
            is_returning  = (not first_contact) and ((now - last_time) > SESSION_TIMEOUT)
            last_user_message[user_id] = now

            if first_contact:
                contact_type = "first"
                known_users.add(user_id)
                conversation_history.pop(user_id, None)
                try:
                    await notify_admin(sender)
                except Exception as e:
                    logger.warning(f"Notif admin échouée: {e}")
            elif is_returning:
                contact_type = "returning"
                conversation_history.pop(user_id, None)
                logger.info(f"↩️ {getattr(sender, 'first_name', user_id)} revient après {int(now - last_time)}s")
            else:
                contact_type = "ongoing"

            t = pending_tasks.get(chat_id)
            if t and not t.done():
                t.cancel()

            text_in = event.text or ""
            pending_tasks[chat_id] = asyncio.create_task(
                auto_reply_task(client, chat_id, user_id, text_in, contact_type)
            )
            wait = config["delay_seconds"] if contact_type in ("first", "returning") \
                   else config.get("reply_delay_seconds", 5)
            logger.info(f"📨 {getattr(sender, 'first_name', user_id)} ({chat_id}) [{contact_type}] → auto dans {wait}s")

        # ── Handler : messages sortants ───────────────────────────────────────

        @client.on(events.NewMessage(outgoing=True, func=lambda e: e.is_private))
        async def on_outgoing(event):
            text = event.text or ""
            if text.startswith("/"):
                return
            # Capturer programme en attente
            if program_state["waiting"] and text:
                program_state["waiting"] = False
                config["daily_program"] = text.strip()
                save_config(config)
                await client.send_message(event.chat_id,
                    f"✅ Programme enregistré !\n\n📅 {config['daily_program']}")
                return
            # Annuler la réponse auto (admin a répondu manuellement)
            chat_id = event.chat_id
            t = pending_tasks.get(chat_id)
            if t and not t.done():
                t.cancel()
                logger.info(f"✋ Auto-réponse annulée pour {chat_id}")

        # ── Commandes admin ───────────────────────────────────────────────────

        def _args(event) -> list[str]:
            return (event.text or "").strip().split()[1:]

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/program(\s|$)"))
        async def cmd_program(event):
            args = _args(event)
            if args:
                config["daily_program"] = " ".join(args)
                save_config(config)
                await event.respond(f"✅ Programme enregistré :\n📅 {config['daily_program']}")
            else:
                program_state["waiting"] = True
                current = config.get("daily_program", "")
                msg = "📅 Quel est votre programme pour aujourd'hui ?\n_(Tapez-le dans le prochain message)_"
                if current:
                    msg += f"\n\nActuel : _{current}_"
                await event.respond(msg)

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/clearprogram(\s|$)"))
        async def cmd_clearprogram(event):
            config["daily_program"] = ""
            save_config(config)
            await event.respond("✅ Programme effacé.")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/stop(\s|$)"))
        async def cmd_stop(event):
            args = _args(event)
            if args and args[0].lstrip("-").isdigit():
                cid = int(args[0])
                stopped_chats.add(cid)
                await event.respond(f"🛑 Auto-réponse arrêtée pour `{cid}`")
            else:
                config["auto_reply_enabled"] = False
                save_config(config)
                await event.respond("🛑 Auto-réponse globale désactivée.\nTape `/resume` pour réactiver.")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/resume(\s|$)"))
        async def cmd_resume(event):
            args = _args(event)
            if args and args[0].lstrip("-").isdigit():
                cid = int(args[0])
                stopped_chats.discard(cid)
                await event.respond(f"✅ Auto-réponse réactivée pour `{cid}`")
            else:
                config["auto_reply_enabled"] = True
                save_config(config)
                stopped_chats.clear()
                await event.respond(f"✅ Auto-réponse globale réactivée. Délai : {config['delay_seconds']}s")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/setdelay(\s|$)"))
        async def cmd_setdelay(event):
            args = _args(event)
            if not args or not args[0].isdigit():
                await event.respond(
                    f"❌ Usage : `/setdelay <secondes>`\n\n"
                    f"Délai absence actuel : {config['delay_seconds']}s\n"
                    f"Délai réponse en cours : {config.get('reply_delay_seconds', 5)}s")
                return
            config["delay_seconds"] = int(args[0])
            save_config(config)
            await event.respond(
                f"✅ Délai d'absence : **{config['delay_seconds']}s**\n"
                f"_(Délai réponse en cours : {config.get('reply_delay_seconds', 5)}s)_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/setreplydelay(\s|$)"))
        async def cmd_setreplydelay(event):
            args = _args(event)
            if not args or not args[0].isdigit():
                await event.respond(
                    f"❌ Usage : `/setreplydelay <secondes>`\n\n"
                    f"Délai réponse (conversation) : {config.get('reply_delay_seconds', 5)}s\n"
                    f"Délai absence (1er msg) : {config['delay_seconds']}s")
                return
            config["reply_delay_seconds"] = int(args[0])
            save_config(config)
            await event.respond(
                f"✅ Délai réponse (conversation) : **{config['reply_delay_seconds']}s**\n"
                f"_(Délai absence : {config['delay_seconds']}s)_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/setquota(\s|$)"))
        async def cmd_setquota(event):
            args = _args(event)
            if not args or not args[0].isdigit():
                await event.respond(
                    f"❌ Usage : `/setquota <n>`\n\n"
                    f"Quota : {config['daily_quota']}/jour\n"
                    f"Utilisé : {config['quota_used_today']}")
                return
            config["daily_quota"] = int(args[0])
            save_config(config)
            await event.respond(f"✅ Quota : **{config['daily_quota']} appels/jour**")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/setmodel(\s|$)"))
        async def cmd_setmodel(event):
            parts = (event.text or "").strip().split(maxsplit=1)
            if len(parts) < 2:
                await event.respond(
                    f"❌ Usage : `/setmodel <modèle>`\n\nActuel : `{config['ai_model']}`\n\n"
                    "**Modèles Groq :**\n• `llama-3.3-70b-versatile`\n"
                    "• `llama-3.1-8b-instant`\n• `mixtral-8x7b-32768`\n• `gemma2-9b-it`")
                return
            config["ai_model"] = parts[1].strip()
            save_config(config)
            await event.respond(f"✅ Modèle : **{config['ai_model']}**")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/setapi(\s|$)"))
        async def cmd_setapi(event):
            parts = (event.text or "").strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                current = config.get("groq_api_key") or GROQ_API_KEY
                masked  = current[:8] + "..." + current[-4:] if len(current) > 12 else "***"
                await event.respond(
                    f"❌ Usage : `/setapi <clé_groq>`\n\nClé actuelle : `{masked}`\nhttps://console.groq.com/keys")
                return
            new_key = parts[1].strip()
            try:
                tc = Groq(api_key=new_key)
                tc.chat.completions.create(model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": "test"}], max_tokens=5)
            except Exception as e:
                await event.respond(f"❌ Clé invalide :\n`{e}`")
                return
            config["groq_api_key"] = new_key
            config["credentials"]["groq_api_key"] = new_key
            save_config(config)
            groq_holder[0] = Groq(api_key=new_key)
            masked = new_key[:8] + "..." + new_key[-4:]
            await event.respond(f"✅ Clé API Groq mise à jour : `{masked}`")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/addinfo(\s|$)"))
        async def cmd_addinfo(event):
            text = (event.text or "").strip()
            info = text[len("/addinfo"):].strip()
            if not info:
                await event.respond("❌ Usage : `/addinfo <information>`")
                return
            config["knowledge_base"].append(info)
            save_config(config)
            await event.respond(f"✅ Info ajoutée ({len(config['knowledge_base'])} total) :\n_{info}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/removeinfo(\s|$)"))
        async def cmd_removeinfo(event):
            args = _args(event)
            if not args or not args[0].isdigit():
                listing = "\n".join(f"{i+1}. {it}" for i, it in enumerate(config["knowledge_base"]))
                await event.respond(f"❌ Usage : `/removeinfo <n>`\n\n**Base :**\n{listing}")
                return
            idx = int(args[0]) - 1
            if not (0 <= idx < len(config["knowledge_base"])):
                await event.respond(f"❌ Numéro invalide (1 à {len(config['knowledge_base'])})")
                return
            removed = config["knowledge_base"].pop(idx)
            save_config(config)
            await event.respond(f"✅ Supprimé :\n_{removed}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/stats(\s|$)"))
        async def cmd_stats(event):
            used    = config["quota_used_today"]
            total   = config["daily_quota"]
            pct     = int((used / total) * 100) if total > 0 else 0
            status  = "✅ Active" if config.get("auto_reply_enabled", True) else "🛑 Arrêtée"
            pending = sum(1 for t in pending_tasks.values() if not t.done())
            kb      = "\n".join(f"  {i+1}. {it}" for i, it in enumerate(config["knowledge_base"]))
            ck      = config.get("groq_api_key") or GROQ_API_KEY
            masked  = ck[:8] + "..." + ck[-4:] if len(ck) > 12 else "***"
            program = config.get("daily_program") or "_(aucun)_"
            await event.respond(
                f"📊 **Bot Sossou Kouamé — Stats**\n\n"
                f"🔄 Auto-réponse : {status}\n"
                f"🤖 Modèle IA : `{config['ai_model']}`\n"
                f"🔑 Clé Groq : `{masked}`\n"
                f"📈 Quota : {used}/{total} ({pct}%)\n"
                f"⏱ Délai absence : {config['delay_seconds']}s\n"
                f"⚡ Délai réponse : {config.get('reply_delay_seconds', 5)}s\n"
                f"⏳ En attente : {pending}\n"
                f"👥 Contacts connus : {len(known_users)}\n"
                f"📅 Programme : {program}\n\n"
                f"📚 Base ({len(config['knowledge_base'])} entrées) :\n{kb}")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/help(\s|$)"))
        async def cmd_help(event):
            await event.respond(
                "🛠 **Commandes Admin**\n\n"
                "📊 `/stats` — Tout voir\n\n"
                "🛑 `/stop` — Désactiver l'auto-réponse\n"
                "✅ `/resume` — Réactiver l'auto-réponse\n\n"
                "📅 `/program` — Définir le programme du jour\n"
                "🗑 `/clearprogram` — Effacer le programme\n\n"
                "⏱ `/setdelay 30` — Délai absence (1er message)\n"
                "⚡ `/setreplydelay 5` — Délai réponse (conversation)\n"
                "🔢 `/setquota 200` — Quota appels IA/jour\n"
                "🧠 `/setmodel <modèle>` — Modèle IA\n"
                "🔑 `/setapi <clé>` — Clé API Groq\n\n"
                "➕ `/addinfo <texte>` — Ajouter une info\n"
                "➖ `/removeinfo <n>` — Supprimer une info\n")

        logger.info("═══════════════════════════════════════════════")
        logger.info("  MODE USERBOT (Telethon) — Sossou Kouamé")
        logger.info(f"  Modèle : {config['ai_model']}")
        logger.info(f"  Délai absence : {config['delay_seconds']}s | Réponse : {config.get('reply_delay_seconds',5)}s")
        logger.info(f"  Quota : {config['daily_quota']}/jour")
        logger.info("═══════════════════════════════════════════════")

        await client.run_until_disconnected()

    asyncio.run(_main())


# ══════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cfg = load_config()

    PHONE_NUMBER   = "+22995501564"
    OWNER_ID       = int(_get(cfg, "ADMIN_ID",           "admin_id",          "1190237801"))
    API_ID         = int(_get(cfg, "TELEGRAM_API_ID",    "telegram_api_id",   "0") or "0")
    API_HASH       = _get(cfg, "TELEGRAM_API_HASH",      "telegram_api_hash",  "")
    BOT_TOKEN      = _get(cfg, "TELEGRAM_BOT_TOKEN",     "bot_token",          "")
    GROQ_API_KEY   = _get(cfg, "GROQ_API_KEY",           "groq_api_key",       "")
    SESSION_STRING = _get(cfg, "TELEGRAM_SESSION",       "telegram_session",   "").strip()

    # Fallback : lire session.txt si le secret est absent ou invalide
    if not SESSION_STRING:
        if os.path.exists("session.txt"):
            SESSION_STRING = open("session.txt").read().strip()
            if SESSION_STRING:
                logger.info("📄 Session chargée depuis session.txt")
    else:
        # Vérifier rapidement que c'est bien une session Telethon (commence par '1')
        try:
            from telethon.sessions import StringSession as _SS
            _SS(SESSION_STRING)
        except Exception:
            logger.warning("⚠️  Secret TELEGRAM_SESSION invalide, tentative sur session.txt …")
            if os.path.exists("session.txt"):
                SESSION_STRING = open("session.txt").read().strip()
                logger.info("📄 Session de remplacement chargée depuis session.txt")
            else:
                SESSION_STRING = ""

    if not API_ID or not API_HASH:
        raise ValueError("TELEGRAM_API_ID et TELEGRAM_API_HASH requis.")

    start_health_server()

    if SESSION_STRING:
        logger.info("✅ Session trouvée → Mode USERBOT (Telethon)")
        run_userbot(API_ID, API_HASH, BOT_TOKEN, GROQ_API_KEY, SESSION_STRING, OWNER_ID)
        # Si run_userbot retourne (session invalide/expirée) → mode SETUP
        logger.warning("⚠️  Session invalide ou expirée → bascule en mode SETUP")

    if BOT_TOKEN:
        logger.info("ℹ️  Mode SETUP → Envoyez /connect dans le bot pour générer une nouvelle session Telethon")
        run_setup_bot(BOT_TOKEN, API_ID, API_HASH, OWNER_ID, PHONE_NUMBER)
    else:
        raise ValueError("TELEGRAM_SESSION (valide) ou TELEGRAM_BOT_TOKEN requis.")
