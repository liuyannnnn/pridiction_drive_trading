from sqlalchemy import text
from app.storage.postgres import engine


class Repository:
    def __init__(self) -> None:
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS polypdt"))
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.matches (
                      match_id TEXT PRIMARY KEY,
                      sport TEXT NOT NULL,
                      league TEXT NOT NULL,
                      team_home TEXT NOT NULL,
                      team_away TEXT NOT NULL,
                      start_time_utc TIMESTAMPTZ NOT NULL,
                      status TEXT NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.market_ticks (
                      tick_id BIGSERIAL PRIMARY KEY,
                      match_id TEXT NOT NULL,
                      ts_utc TIMESTAMPTZ NOT NULL,
                      source TEXT NOT NULL,
                      outcome TEXT NOT NULL,
                      bid NUMERIC(10,6),
                      ask NUMERIC(10,6),
                      volume NUMERIC(18,6),
                      extra JSONB
                    )
                    """
                )
            )
        self._schema_ready = True

    async def ensure_match(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.matches (match_id, sport, league, team_home, team_away, start_time_utc, status, updated_at)
            VALUES (:match_id, :sport, :league, :team_home, :team_away, :start_time_utc, :status, NOW())
            ON CONFLICT (match_id) DO UPDATE SET
              sport = EXCLUDED.sport,
              league = EXCLUDED.league,
              team_home = EXCLUDED.team_home,
              team_away = EXCLUDED.team_away,
              start_time_utc = EXCLUDED.start_time_utc,
              status = EXCLUDED.status,
              updated_at = NOW()
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)

    async def insert_tick(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.market_ticks (match_id, ts_utc, source, outcome, bid, ask, volume, extra)
            VALUES (:match_id, :ts_utc, :source, :outcome, :bid, :ask, :volume, CAST(:extra AS JSONB))
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)
