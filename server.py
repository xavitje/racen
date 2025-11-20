from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
import asyncio

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_states = {} # {websocket: {"id": x, "ready": False, "finished": False, "time": 0}}
        self.game_active = False
        self.start_time = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Wijs tijdelijk ID toe
        self.player_states[websocket] = {"id": str(id(websocket)), "ready": False, "finished": False, "time": None}
        await self.send_lobby_update()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if websocket in self.player_states:
            del self.player_states[websocket]
        # Als iemand weggaat tijdens lobby, update de rest
        if not self.game_active:
             asyncio.create_task(self.send_lobby_update())

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

    async def send_lobby_update(self):
        # Stuur lijst met wie ready is naar iedereen
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
            # Stuur positie door naar anderen
            await self.broadcast({
                "type": "player_update",
                "id": self.player_states[websocket]["id"],
                "x": data["x"],
                "y": data["y"],
                "lap": data["lap"],
                "color": data.get("color")
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
        # Start alleen als >1 speler en IEDEREEN ready is
        if len(self.active_connections) > 0: # Voor testen mag 1 ook, normaal > 1
            all_ready = all(s["ready"] for s in self.player_states.values())
            if all_ready and not self.game_active:
                self.game_active = True
                self.start_time = time.time()
                # Aftellen kan client-side, wij sturen 'GO'
                await self.broadcast({"type": "game_start"})

    async def check_game_over(self):
        all_finished = all(s["finished"] for s in self.player_states.values())
        if all_finished:
            self.game_active = False
            # Stuur eindstand
            results = []
            for ws, state in self.player_states.items():
                results.append({"id": state["id"], "time": state["time"]})
            # Sorteer op tijd
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

@app.get("/")
def health():
    return {"status": "ok"}
