# How to Run the ServerOS Dashboard & Bot

## Prerequisites
- Python 3.8+
- Discord Bot Token (from Discord Developer Portal)

## Installation

1. **Clone/Extract the project**
2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   pip install -r bot/requirements.txt
   ```

## Configuration

1. **Environment Variables:**
   Set the following environment variable:
   - `DISCORD_TOKEN`: Your bot's token.

2. **Database:**
   The SQLite database `server_os.db` will be automatically created on the first run.

## Running the System

### Option 1: Unified Launcher (Recommended for Pydroid/Mobile)
If you are using Pydroid or want to run everything in one go:
1. Ensure your token is in `bot/.env`.
2. Run the following command from the root directory:
   ```bash
   python unified_launcher.py
   ```
This will start both the Backend and the Bot in a single process.

### Option 2: Separate Processes (Desktop/Servers)
1. **Start the Backend Server:**
   ```bash
   cd backend
   python main.py
   ```
2. **Start the Discord Bot:**
   ```bash
   cd bot
   python main.py
   ```

## Default Login
- **Username:** `admin`
- **Password:** `admin`

## Project Structure
- `frontend/`: Vanilla HTML/CSS/JS dashboard files.
- `backend/`: FastAPI server handling WebSockets and API.
- `bot/`: Discord bot files and cogs.
- `server_os.db`: Shared SQLite database.

## Replit + UptimeRobot (Optional)
To keep the system running 24/7 on Replit:
1. Upload the files to a Replit project.
2. Add your `DISCORD_TOKEN` to Replit Secrets.
3. Use a service like [UptimeRobot](https://uptimerobot.com/) to ping your Replit's public URL (the backend server address) every 5 minutes.
