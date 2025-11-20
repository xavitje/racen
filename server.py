import asyncio
import os
import json
import websockets
import http

CLIENTS = set()

# Accepteer GET en HEAD voor Render health checks
async def process_request(path, request_headers):
    method = request_headers.get(':method', None)
    upgrade = request_headers.get('Upgrade', '').lower()
    # Als het geen echte websocket handshake is (geen "Upgrade: websocket"), geef 200 OK response
    if upgrade != 'websocket':
        # HEAD of gewone HTTP-request
        return (
            http.HTTPStatus.OK, 
            [('Content-Type', 'text/plain')], 
            b"WebSocket server running (health check response)"
        )
    # Anders: niks doen, handshake gaat door
    return None

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
    port = int(os.environ.get("PORT", 8080))
    print(f"Server luistert op poort {port}")
    async with websockets.serve(
        handler, "0.0.0.0", port, process_request=process_request
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
