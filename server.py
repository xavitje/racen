from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os

app = FastAPI()

clients = set()

@app.get("/")
def health():
    # Render doet GET/HEAD op root – nu krijg je 200 OK
    return {"health": "OK"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast naar andere clients
            for client in clients:
                if client != websocket:
                    await client.send_text(data)
    except WebSocketDisconnect:
        clients.remove(websocket)

# Gebruik deze in Render als startcommando:
# uvicorn server:app --host 0.0.0.0 --port $PORT
