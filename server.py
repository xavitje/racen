import asyncio
import os
import json
import websockets
import http

# Set om alle clientverbindingen bij te houden
CLIENTS = set()

# Health check ondersteunen (HEAD/GET zonder upgrade header)
async def process_request(path, request_headers):
    if request_headers.get('Upgrade', '').lower() != 'websocket':
        return (http.HTTPStatus.OK, [], b"")  # Reageer “leeg” op HEAD/GET zonder websocket
    return None  # Dit is een echte websocket-connectie

async def handler(websocket):
    # Nieuw aangesloten client toevoegen
    CLIENTS.add(websocket)
    try:
        async for message in websocket:
            # Ontvangen data doorsturen naar andere clients (behalve jezelf)
            for client in CLIENTS:
                if client != websocket:
                    await client.send(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Client verwijderen als de verbinding sluit
        CLIENTS.remove(websocket)

async def main():
    # Render gebruikt environment variable "PORT", anders standaard 8080 lokaal
    port = int(os.environ.get("PORT", 8080))
    print(f"Luistert op poort {port}")
    async with websockets.serve(
            handler, "0.0.0.0", port, process_request=process_request
    ):
        await asyncio.Future()  # Blijf eeuwig draaien

if __name__ == "__main__":
    asyncio.run(main())
