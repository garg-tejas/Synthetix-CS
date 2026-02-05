import asyncio
import asyncpg


async def main():
    conn = await asyncpg.connect("postgresql://slm:slm@localhost:5432/slm_rag")
    rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    for r in rows:
        print(r["table_name"])
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())