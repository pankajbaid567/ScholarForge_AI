import sys
import asyncio
from src.database.session import SessionLocal
from src.api.routes.chat import chat_stream, ChatRequest

async def test():
    db = SessionLocal()
    req = ChatRequest(session_id="c138f51a-7b32-4752-95f7-873b759600a9", message="hello", stream=True)
    try:
        res = await chat_stream(req, db=db)
        print("Success:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
