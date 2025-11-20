import asyncio
import os
import json
import websockets
import http

# Clients bijhouden
CLIENTS = set()

# Health check functie
async def process_request(path, request_headers):
    if request_headers.get('Upgrade', '').lower() != 'websocket':
        return (http.HTTPStatus.OK, [], b"")  # Sta HEAD/GET toe
    return None  # Echte WebSocket connectie

async def handler(websocket):
    CLIENTS.add(websocket)
    try:
        async for message in websocket:
            for client in CLIENTS:
                if client != websocket:
                    await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CLIENTS.remove(websocket)

async def main():
    # Gebruik de juiste poort variabel (Render: 'PORT')
    port = int(os.environ.get("PORT", 8080))
    print(f"Server luistert op poort {port}")
    async with websockets.serve(
        handler, "0.0.0.0", port, process_request=process_request
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
