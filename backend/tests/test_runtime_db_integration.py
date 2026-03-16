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
        has_moneyline_col = await conn.fetchval(
            """
            select count(*) from information_schema.columns
            where table_schema='polypdt' and table_name='matches' and column_name='moneyline_volume'
            """
        )
        has_total_col = await conn.fetchval(
            """
            select count(*) from information_schema.columns
            where table_schema='polypdt' and table_name='matches' and column_name='total_volume'
            """
        )
        max_moneyline = await conn.fetchval("select coalesce(max(moneyline_volume), 0) from polypdt.matches")
        max_total = await conn.fetchval("select coalesce(max(total_volume), 0) from polypdt.matches")
        await conn.close()
        assert matches >= 1
        assert ticks >= 1
        assert has_moneyline_col == 1
        assert has_total_col == 1
        assert float(max_moneyline) >= 0
        assert float(max_total) >= 0

    asyncio.run(case())
