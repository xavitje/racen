import asyncio
import websockets
import json


CLIENTS = set()

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
        # Speler verwijderen als de verbinding verbreekt
        CLIENTS.remove(websocket)

async def main():
    # Luister op poort 8080 (Render gebruikt de PORT environment variabele,
    # maar lokaal gebruiken we 8080 of de standaard poort)
    print("Server gestart...")
    async with websockets.serve(handler, "0.0.0.0", 8080):
        await asyncio.Future()
if __name__ == "__main__":
    asyncio.run(main())
