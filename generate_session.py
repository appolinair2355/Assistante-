"""
Génération de session Telegram pour Sossou Kouamé Apollinaire.
Numéro pré-configuré : +22995501564

Usage : python generate_session.py
Quand le code arrive sur Telegram, tapez : aa<code>
Exemple : aa12345
"""
import os
import asyncio
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

PHONE_NUMBER = "+22995501564"

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

async def main():
    print("=" * 60)
    print("  Connexion au compte Telegram de Sossou Kouamé")
    print("=" * 60)
    print(f"  Numéro : {PHONE_NUMBER}")
    print("=" * 60)

    app = Client(
        ":memory:",
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True,
    )

    await app.connect()

    print("\n📤 Envoi du code de vérification...")
    sent = await app.send_code(PHONE_NUMBER)
    print("✅ Code envoyé sur Telegram !")
    print("\n👉 Tapez  aa  suivi du code reçu (ex: aa12345) puis Entrée :")

    raw = input(">>> ").strip()

    if raw.lower().startswith("aa"):
        code = raw[2:].strip()
    else:
        code = raw.strip()

    try:
        await app.sign_in(PHONE_NUMBER, sent.phone_code_hash, code)
    except SessionPasswordNeeded:
        print("\n🔐 Votre compte a un mot de passe 2FA. Entrez-le :")
        password = input("Mot de passe 2FA : ").strip()
        await app.check_password(password)

    session_string = await app.export_session_string()
    await app.disconnect()

    print("\n" + "=" * 60)
    print("✅ CONNEXION RÉUSSIE — SESSION GÉNÉRÉE !")
    print("=" * 60)
    print("\nAjoutez cette valeur dans vos secrets sous le nom :")
    print("  TELEGRAM_SESSION\n")
    print(session_string)
    print("\n" + "=" * 60)
    print("⚠️  Gardez cette session SECRÈTE.")
    print("  Elle fonctionne aussi sur Render.com dans les variables d'env.")
    print("=" * 60)

    with open("session.txt", "w") as f:
        f.write(session_string)
    print("\n💾 Session également sauvegardée dans : session.txt")

if __name__ == "__main__":
    asyncio.run(main())
