import asyncio
import os
from anthropic import AsyncAnthropic

async def test():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    client = AsyncAnthropic(api_key=api_key)
    
    models = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-2.1"
    ]
    
    for model in models:
        try:
            print(f"Trying {model}...")
            response = await client.messages.create(
                max_tokens=10,
                messages=[{"role": "user", "content": "hello"}],
                model=model
            )
            print(f"SUCCESS: {model}")
            break
        except Exception as e:
            print(f"FAILED {model}: {str(e)}")

asyncio.run(test())
