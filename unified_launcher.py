import asyncio
import threading
import uvicorn
import os
import sys
from dotenv import load_dotenv

# Add the current directory to sys.path so we can import from bot and backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(dotenv_path="bot/.env")

def run_backend():
    """Function to run the FastAPI backend using Uvicorn."""
    from backend.main import app
    # We use a fixed port 8000 for the backend
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

async def run_bot():
    """Function to run the Discord bot."""
    from bot.main import ServerOS
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not found in bot/.env")
        return
    
    bot = ServerOS()
    try:
        async with bot:
            await bot.start(token)
    except Exception as e:
        print(f"Bot Error: {e}")

async def main():
    # 1. Start the Backend in a separate thread
    # This allows the FastAPI server to run without blocking the asyncio loop
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    print("Backend started on http://0.0.0.0:8000")

    # 2. Start the Bot in the main event loop
    # We wait a few seconds to let the backend warm up
    await asyncio.sleep(5)
    print("Starting Discord Bot...")
    await run_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
