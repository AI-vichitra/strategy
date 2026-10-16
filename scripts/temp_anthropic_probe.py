import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
import asyncio

load_dotenv('backend/.env')

async def main():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print('No ANTHROPIC_API_KEY environment variable found.')
        return
    client = AsyncAnthropic(api_key=api_key)
    print('client models methods:', [m for m in dir(client.models) if not m.startswith('_')])
    print('client messages methods:', [m for m in dir(client.messages) if not m.startswith('_')])
    try:
        print('\nTrying list method...')
        if hasattr(client.models, 'list'):
            models = await client.models.list()
            print('list returned type:', type(models))
            print('models keys:', [k for k in dir(models) if not k.startswith('_')] )
            print('first 50 models:')
            for item in list(models.data)[:50]:
                print(item)
        else:
            print('client.models.list not available')
    except Exception as exc:
        print('list failed:', type(exc).__name__, exc)

    try:
        print('\nTrying sample create call with possible models...')
        for model in [
            'claude-sonnet-4-6',
            'claude-haiku-4-5-20251001',
            'claude-sonnet-4-5-20250929',
            'claude-opus-4-8',
            'claude-opus-4-7',
        ]:
            print('TEST model', model)
            try:
                await client.messages.create(
                    model=model,
                    messages=[{'role': 'user', 'content': 'Hello'}],
                    max_tokens=1,
                )
                print('SUCCESS', model)
            except Exception as e:
                print('FAIL', model, type(e).__name__, str(e))
    except Exception as exc:
        print('sample calls failed:', type(exc).__name__, exc)

asyncio.run(main())
