import asyncio
import os
from openai import AsyncOpenAI

async def test_qwen():
    api_key = "sk-ws-H.IYXXLP.z0yJ.MEYCIQCTkDeQj8eUvDcL90ccLpCRiA--gOnCdTK9QSCDAPf-FQIhAOHeuVtvzydi1QGd0QQSERK1xgPjSpFf8a7M4-oMJZ6x"
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    
    try:
        response = await client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": "Hello!"}],
            max_tokens=10
        )
        print("Success:", response.choices[0].message.content)
    except Exception as e:
        print("Error:", e)

asyncio.run(test_qwen())
