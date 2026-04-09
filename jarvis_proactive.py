import os, asyncio
from telegram.ext import Application
from alpaca.trading.client import TradingClient

# Config
TOKEN = "8698860518:AAEEDckZXlW68yJ4kfxSMix1Vb5x6drB-gI"
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

async def main():
    print("🚀 [M4 CORE] Activating Jarvis Intelligence...")
    
    try:
        # Initialize Telegram
        app = Application.builder().token(TOKEN).build()
        await app.initialize()
        
        # Initialize Alpaca
        client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
        acct = client.get_account()
        
        # Send a "System Online" message
        msg = f"🛡️ Jarvis Dashboard Online\nEquity: ${float(acct.equity):,.2f}\nStatus: Monitoring Market..."
        
        # Note: You'll need your Chat ID to send a message. 
        # For now, let's just verify the connection works.
        bot_info = await app.bot.get_me()
        print(f"✅ Connected to Telegram as: @{bot_info.username}")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
