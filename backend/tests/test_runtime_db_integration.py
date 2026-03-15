import asyncio

import asyncpg
import pytest

from app.runtime.trading_runtime import TradingRuntime


def test_runtime_persists_rows_when_db_available() -> None:
    async def case() -> None:
        try:
            conn = await asyncpg.connect(
                user="postgres",
                password="dT3Hu89envHg3Nc",
                host="127.0.0.1",
                port=5432,
                database="postgres",
            )
            await conn.close()
        except Exception as exc:
            pytest.skip(f"postgres unavailable: {exc}")
        runtime = TradingRuntime()
        await runtime.start_simulation(initial_balance=1000.0, retracement=0.05)
        conn = await asyncpg.connect(
            user="postgres",
            password="dT3Hu89envHg3Nc",
            host="127.0.0.1",
            port=5432,
            database="postgres",
        )
        matches = await conn.fetchval("select count(*) from polypdt.matches")
        ticks = await conn.fetchval("select count(*) from polypdt.market_ticks")
        await conn.close()
        assert matches >= 1
        assert ticks >= 1

    asyncio.run(case())
