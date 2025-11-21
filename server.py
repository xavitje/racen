
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
import asyncio
import random

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_states = {}
        self.game_active = False
        self.start_time = 0
        self.countdown_active = False
        self.player_colors = [
            (255, 0, 0),    # Rood
            (0, 100, 255),  # Blauw
            (0, 255, 0),    # Groen
            (255, 255, 0),  # Geel
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyaan
            (255, 128, 0),  # Oranje
            (128, 0, 255)   # Paars
        ]
        self.used_colors = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Geef speler unieke kleur
        available_colors = [c for c in self.player_colors if c not in self.used_colors]
        if not available_colors:
            # Als alle kleuren gebruikt zijn, neem random kleur
            player_color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        else:
            player_color = available_colors[0]
        self.used_colors.append(player_color)
        
        # Wijs ID en kleur toe
        self.player_states[websocket] = {
            "id": str(id(websocket)),
            "ready": False,
            "finished": False,
            "time": None,
            "x": 0, "y": 0, "z": 0, "lap": 1,
            "color": player_color
        }
        
        # Stuur welkomstbericht met player ID en kleur
        await websocket.send_json({
            "type": "welcome",
            "id": self.player_states[websocket]["id"],
            "color": player_color
        })
        
        await self.send_lobby_update()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.player_states:
            # Verwijder kleur uit gebruikt lijst
            removed_color = self.player_states[websocket].get("color")
            if removed_color in self.used_colors:
                self.used_colors.remove(removed_color)
            del self.player_states[websocket]
        
        # Als er NIEMAND meer is, reset de game state
        if len(self.active_connections) == 0:
            self.game_active = False
            print("Resetting game state (no players left)")
        
        if not self.game_active:
            asyncio.create_task(self.send_lobby_update())
            asyncio.create_task(self.check_start_game())

    async def broadcast(self, message: dict, exclude_sender: WebSocket = None):
        for connection in self.active_connections:
            if connection != exclude_sender:
                try:
                    await connection.send_json(message)
                except:
                    pass

    async def send_lobby_update(self):
        players_info = []
        for ws, state in self.player_states.items():
            players_info.append({
                "id": state["id"],
                "ready": state["ready"],
                "color": state["color"]
            })
        await self.broadcast({
            "type": "lobby_update",
            "players": players_info,
            "game_active": self.game_active
        })

    async def handle_message(self, websocket: WebSocket, data: dict):
        msg_type = data.get("type")
        
        if msg_type == "ready":
            self.player_states[websocket]["ready"] = True
            await self.send_lobby_update()
            await self.check_start_game()
        
        elif msg_type == "update_position":
            state = self.player_states[websocket]
            state["x"] = data.get("x", 0)
            state["z"] = data.get("z", 0)
            state["lap"] = data.get("lap", 1)
            
            # Broadcast naar anderen met kleur
            await self.broadcast({
                "type": "player_update",
                "id": state["id"],
                "x": state["x"],
                "z": state["z"],
                "lap": state["lap"],
                "color": state.get("color", (255, 0, 0))
            }, exclude_sender=websocket)
        
        elif msg_type == "finish":
            if not self.player_states[websocket]["finished"]:
                self.player_states[websocket]["finished"] = True
                finish_time = time.time() - self.start_time
                self.player_states[websocket]["time"] = finish_time
                
                await self.broadcast({
                    "type": "player_finished",
                    "id": self.player_states[websocket]["id"],
                    "time": finish_time
                })
                
                await self.check_game_over()

    # server.py

    async def check_start_game(self):
        if len(self.active_connections) > 0:
            if len(self.active_connections) < 1:
                return 

            all_ready = all(s["ready"] for s in self.player_states.values())
            
            if all_ready and not self.game_active and not self.countdown_active:
                self.countdown_active = True
                print("Starting 3 second countdown...")
                
                for i in range(3, 0, -1):
                    await self.broadcast({"type": "countdown", "value": i})
                    await asyncio.sleep(1)
                
                print("STARTING GAME NOW!")
                self.game_active = True
                self.start_time = time.time()
                await self.broadcast({"type": "game_start"})
                self.countdown_active = False

    async def check_game_over(self):
        all_finished = all(s["finished"] for s in self.player_states.values())
        if all_finished:
            self.game_active = False
            results = []
            for ws, state in self.player_states.items():
                results.append({"id": state["id"], "time": state["time"]})
            results.sort(key=lambda x: x["time"] if x["time"] else 9999)
            
            await self.broadcast({"type": "game_over", "results": results})

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(websocket)

@app.get("/")
def health():
    return {"status": "ok"}
