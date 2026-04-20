 
import asyncio
import redis.asyncio as redis

async def test():
    r = redis.from_url('redis://localhost:6379', decode_responses=True)
    keys = await r.keys('grabpic:token:*')
    print('tokens in redis:', keys)
    for k in keys:
        val = await r.get(k)
        print(k, '->', val)

asyncio.run(test())