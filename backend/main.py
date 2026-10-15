import os
import json
import logging
import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from backend.database import DatabaseManager

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backend")

app = FastAPI(title="ServerOS Control Panel API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State ---
DB_PATH = "server_os.db"
db = DatabaseManager(DB_PATH)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- Models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class CogToggleRequest(BaseModel):
    guild_id: int
    cog_name: str
    enabled: bool

# --- Lifecycle ---
@app.on_event("startup")
async def startup():
    await db.initialise()

# --- Auth ---
@app.post("/api/login")
async def login(req: LoginRequest):
    user = await db.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "success", "token": "dummy-token-for-now", "username": user['username']}

# --- API Routes ---
@app.get("/api/guilds")
async def get_guilds():
    return await db.get_all_guilds()

@app.get("/api/guilds/{guild_id}/cogs")
async def get_guild_cogs(guild_id: int):
    return await db.get_cog_states(guild_id)

@app.post("/api/guilds/cogs/toggle")
async def toggle_cog(req: CogToggleRequest):
    await db.set_cog_state(req.guild_id, req.cog_name, req.enabled)
    # Notify bot via WebSocket or shared state
    await manager.broadcast({
        "type": "cog_update",
        "guild_id": req.guild_id,
        "cog_name": req.cog_name,
        "enabled": req.enabled
    })
    return {"status": "success"}

@app.get("/api/stats/global")
async def get_global_stats():
    return await db.get_global_stats()

# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle incoming messages from Frontend or Bot
            if message.get("type") == "bot_log":
                # Broadcast log to all dashboard clients
                await manager.broadcast(message)
            elif message.get("type") == "terminal_command":
                # Forward command to bot
                await manager.broadcast(message)
            elif message.get("type") == "bot_status":
                await manager.broadcast(message)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
