import asyncio
import os
from anthropic import AsyncAnthropic

async def check_models():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    print(f"Using API Key: {api_key[:10]}...")
    client = AsyncAnthropic(api_key=api_key)
    
    models = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229"
    ]
    
    for model in models:
        try:
            print(f"Testing {model}...")
            response = await client.messages.create(
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
                model=model
            )
            print(f"SUCCESS: {model} is available!")
        except Exception as e:
            print(f"FAILED {model}: {type(e).__name__} - {str(e)}")

asyncio.run(check_models())
