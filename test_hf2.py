import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from huggingface_hub import AsyncInferenceClient
hf_client = AsyncInferenceClient(token=os.getenv("HUGGINGFACE_API_KEY"))
async def main():
    try:
        res = await hf_client.chat_completion(model="meta-llama/Meta-Llama-3-8B-Instruct", messages=[{"role":"user","content":"hello"}])
        print("Success:", res)
    except Exception as e:
        print("Error:", type(e), e)
asyncio.run(main())
