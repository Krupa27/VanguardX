import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/test-session"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Send a ping
        await websocket.send(json.dumps({"type": "ping"}))
        
        # Receive response
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())