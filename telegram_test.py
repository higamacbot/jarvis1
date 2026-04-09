import asyncio
from telegram.ext import Application

TOKEN = "8698860518:AAEEDckZXlW68yJ4kfxSMix1Vb5x6drB-gI"

async def main():
    app = Application.builder().token(TOKEN).build()
    await app.initialize()
    bot = await app.bot.get_me()
    print(f"✅ Connected as @{bot.username}")

if __name__ == "__main__":
    asyncio.run(main())
