import asyncio
import time
async def db():
    async def async_db_task():
        time.sleep(5)
    asyncio.create_task(async_db_task())
    return 1

async def node():
    a = await db()
    print("Done ",a)

asyncio.run(node())