from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
import asyncio

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_states = {} 
        self.game_active = False
        self.start_time = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Wijs tijdelijk ID toe en default state
        self.player_states[websocket] = {
            "id": str(id(websocket)), 
            "ready": False, 
            "finished": False, 
            "time": None,
            "x": 0, "y": 0, "z": 0, "lap": 1, "color": (255,0,0) # Defaults
        }
        await self.send_lobby_update()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.player_states:
            del self.player_states[websocket]
        if not self.game_active:
             asyncio.create_task(self.send_lobby_update())

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass # Negeer verbroken verbindingen tijdens broadcast

    async def send_lobby_update(self):
        players_info = []
        for ws, state in self.player_states.items():
            players_info.append({"id": state["id"], "ready": state["ready"]})
        
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
            # Update server state met wat we ontvangen (gebruik .get() voor veiligheid)
            state = self.player_states[websocket]
            state["x"] = data.get("x", 0)
            state["z"] = data.get("z", 0) # Pseudo 3D gebruikt Z ipv Y
            state["lap"] = data.get("lap", 1)
            # Als client kleur stuurt, update die ook
            if "color" in data: state["color"] = data["color"]

            # Broadcast naar anderen
            await self.broadcast({
                "type": "player_update",
                "id": state["id"],
                "x": state["x"],
                "z": state["z"], # Stuur Z door!
                "lap": state["lap"],
                "color": state.get("color")
            })

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

    async def check_start_game(self):
        if len(self.active_connections) > 0: 
            all_ready = all(s["ready"] for s in self.player_states.values())
            if all_ready and not self.game_active:
                self.game_active = True
                self.start_time = time.time()
                await self.broadcast({"type": "game_start"})

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
