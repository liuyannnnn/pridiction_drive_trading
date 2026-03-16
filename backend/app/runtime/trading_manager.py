import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.domain.events import MarketTickEvent
from app.execution.simulator import SimulationExecutor
from app.models import MatchCard
from app.strategy.registry import build_strategy, get_strategy_catalog


@dataclass
class TradingInstance:
    trading_id: str
    strategy_name: str
    strategy_params: dict
    affect_sports: list[str]
    mode: str
    created_at: datetime
    initial_balance: float = 10000.0
    account_alias: str | None = None
    status: str = "created"
    executor: SimulationExecutor = field(default_factory=lambda: SimulationExecutor(initial_balance=10000.0))
    logs: list[dict] = field(default_factory=list)
    task: asyncio.Task | None = None
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    log_dir: Path | None = None
    repository: object | None = None

    def __post_init__(self) -> None:
        self.initial_balance = float(self.strategy_params.get("initial_balance", self.initial_balance))
        self._strategy = self._build_strategy()
        self.executor = SimulationExecutor(initial_balance=self.initial_balance)
        self.log_dir = self.log_dir or Path("logs/tradings")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_dir / f"{self.trading_id}.log"

    def _build_strategy(self):
        return build_strategy(
            name=self.strategy_name,
            strategy_id=f"{self.trading_id}-S001",
            params=self.strategy_params,
        )

    def update_config(
        self,
        strategy_params: dict | None = None,
        affect_sports: list[str] | None = None,
    ) -> None:
        if strategy_params:
            merged = dict(self.strategy_params)
            merged.update(strategy_params)
            old_initial_balance = self.initial_balance
            new_initial_balance = float(merged.get("initial_balance", old_initial_balance))
            self.strategy_params = merged
            self.initial_balance = new_initial_balance
            if (
                new_initial_balance != old_initial_balance
                and not self.executor.positions
                and not self.executor.logs
                and abs(self.executor.balance - old_initial_balance) < 1e-9
            ):
                self.executor.balance = new_initial_balance
            self._strategy = self._build_strategy()
        if affect_sports is not None:
            self.affect_sports = [item.lower() for item in affect_sports]

    async def enqueue_tick(self, tick: MarketTickEvent) -> None:
        await self._queue.put(tick)

    async def run(self) -> None:
        self.status = "running"
        while self.status == "running":
            tick = await self._queue.get()
            self.process_tick(tick)
            await self._persist_snapshot()

    def process_tick(self, tick: MarketTickEvent) -> None:
        signal = self._strategy.on_tick(tick)
        if signal is None:
            return
        result = self.executor.execute(
            strategy_id=signal.strategy_id,
            action=signal.action,
            match_id=signal.match_id,
            outcome=signal.outcome,
            price=signal.price,
            amount=signal.amount,
        )
        self.logs.append(
            {
                "ts_utc": signal.ts_utc.isoformat(),
                "trading_id": self.trading_id,
                "strategy_name": self.strategy_name,
                "action": signal.action,
                "match_id": signal.match_id,
                "outcome": signal.outcome,
                "price": signal.price,
                "result": result,
            }
        )
        self._append_log(self.logs[-1])
        self._schedule_trade_persist(signal, result, self.logs[-1])

    def snapshot(self) -> dict:
        closed = [item for item in self.executor.logs if item.get("action") in {"sell", "settle"} and item.get("status") == "filled"]
        wins = len([item for item in closed if float(item.get("profit", 0.0)) > 0])
        total = len(closed)
        win_rate = float(wins) / total if total > 0 else 0.0
        equity = float(self.executor.balance + sum(item.amount for item in self.executor.positions))
        return {
            "trading_id": self.trading_id,
            "mode": self.mode,
            "status": self.status,
            "strategy_name": self.strategy_name,
            "strategy_params": self.strategy_params,
            "affect_sports": self.affect_sports,
            "initial_balance": self.initial_balance,
            "account_alias": self.account_alias,
            "balance": self.executor.balance,
            "equity": equity,
            "positions": len(self.executor.positions),
            "trades": len(self.executor.logs),
            "wins": wins,
            "total_closed_trades": total,
            "win_rate": win_rate,
        }

    def _append_log(self, payload: dict) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        with self._log_file.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")

    def _schedule_trade_persist(self, signal, result: dict, log_row: dict) -> None:
        if self.repository is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_trade(signal, result, log_row))
        except RuntimeError:
            return

    async def _persist_trade(self, signal, result: dict, log_row: dict) -> None:
        if self.repository is None:
            return
        try:
            await self.repository.insert_trading_trade(
                {
                    "trading_id": self.trading_id,
                    "strategy_id": signal.strategy_id,
                    "action": signal.action,
                    "match_id": signal.match_id,
                    "outcome": signal.outcome,
                    "price": signal.price,
                    "amount": signal.amount,
                    "profit": float(result.get("profit", 0.0)),
                    "status": result.get("status", "unknown"),
                    "ts_utc": signal.ts_utc,
                    "payload": result,
                }
            )
            await self.repository.insert_trading_log(
                {
                    "trading_id": self.trading_id,
                    "ts_utc": signal.ts_utc,
                    "level": "trade",
                    "message": f'{signal.action} {signal.match_id} {signal.outcome}',
                    "payload": log_row,
                }
            )
        except Exception:
            return

    async def _persist_snapshot(self) -> None:
        if self.repository is None:
            return
        try:
            await self.repository.upsert_trading_account(
                {
                    "trading_id": self.trading_id,
                    "balance": float(self.executor.balance),
                    "equity": float(self.executor.balance + sum(p.amount for p in self.executor.positions)),
                    "available_cash": float(self.executor.balance),
                    "position_count": len(self.executor.positions),
                }
            )
            await self.repository.replace_trading_positions(
                self.trading_id,
                [
                    {
                        "trading_id": self.trading_id,
                        "strategy_id": item.strategy_id,
                        "match_id": item.match_id,
                        "outcome": item.outcome,
                        "entry_price": item.entry_price,
                        "amount": item.amount,
                    }
                    for item in self.executor.positions
                ],
            )
        except Exception:
            return


class TradingManager:
    def __init__(self, market_runtime=None, repository=None) -> None:
        self._market_runtime = market_runtime
        self._repository = repository
        self._tradings: dict[str, TradingInstance] = {}
        self._lock = asyncio.Lock()
        self._dispatcher_task: asyncio.Task | None = None

    def strategy_catalog(self) -> list[dict]:
        return get_strategy_catalog()

    def create_trading(
        self,
        strategy_name: str,
        strategy_params: dict,
        affect_sports: list[str],
        mode: str,
        account_alias: str | None = None,
    ) -> dict:
        trading_id = f"TRD-{uuid.uuid4().hex[:8]}"
        instance = TradingInstance(
            trading_id=trading_id,
            strategy_name=strategy_name,
            strategy_params=dict(strategy_params),
            affect_sports=[item.lower() for item in affect_sports],
            mode=mode,
            created_at=datetime.now(UTC),
            account_alias=account_alias,
            repository=self._repository,
        )
        self._tradings[trading_id] = instance
        self._schedule_persist("create", instance)
        return instance.snapshot()

    def start_trading(self, trading_id: str) -> dict:
        instance = self._require(trading_id)
        if instance.status == "running":
            return instance.snapshot()
        instance.status = "running"
        try:
            loop = asyncio.get_running_loop()
            instance.task = loop.create_task(instance.run())
        except RuntimeError:
            instance.task = None
        try:
            asyncio.get_running_loop().create_task(self.start_dispatcher())
        except RuntimeError:
            pass
        self._schedule_snapshot_persist(instance)
        self._schedule_persist("status", instance)
        return instance.snapshot()

    def stop_trading(self, trading_id: str) -> dict:
        instance = self._require(trading_id)
        instance.status = "stopped"
        if instance.task is not None:
            instance.task.cancel()
            instance.task = None
        if not self._has_running_tradings():
            try:
                asyncio.get_running_loop().create_task(self.stop_dispatcher())
            except RuntimeError:
                pass
        self._schedule_snapshot_persist(instance)
        self._schedule_persist("status", instance)
        return instance.snapshot()

    def list_tradings(self) -> list[dict]:
        return [item.snapshot() for item in self._tradings.values()]

    def get_trading(self, trading_id: str) -> dict:
        return self._require(trading_id).snapshot()

    def update_trading(
        self,
        trading_id: str,
        strategy_params: dict | None = None,
        affect_sports: list[str] | None = None,
    ) -> dict:
        instance = self._require(trading_id)
        instance.update_config(strategy_params=strategy_params, affect_sports=affect_sports)
        self._schedule_persist("update", instance)
        return instance.snapshot()

    def delete_trading(self, trading_id: str) -> dict:
        instance = self._require(trading_id)
        instance.status = "stopped"
        if instance.task is not None:
            instance.task.cancel()
            instance.task = None
        del self._tradings[trading_id]
        if not self._has_running_tradings():
            try:
                asyncio.get_running_loop().create_task(self.stop_dispatcher())
            except RuntimeError:
                pass
        if self._repository is not None:
            try:
                asyncio.get_running_loop().create_task(self._repository.delete_trading(trading_id))
            except RuntimeError:
                pass
        return {"deleted": True, "trading_id": trading_id}

    def get_trading_logs(self, trading_id: str, limit: int = 200, match_id: str | None = None) -> list[dict]:
        rows = self._require(trading_id).logs
        if match_id:
            rows = [item for item in rows if item.get("match_id") == match_id]
        return rows[-limit:]

    def get_trading_trades(self, trading_id: str, limit: int = 200, match_id: str | None = None) -> list[dict]:
        rows = self._require(trading_id).executor.logs
        if match_id:
            rows = [item for item in rows if item.get("match_id") == match_id]
        return rows[-limit:]

    def get_trading_positions(self, trading_id: str) -> list[dict]:
        instance = self._require(trading_id)
        latest_ticks = {}
        matches = {}
        if self._market_runtime is not None:
            latest_ticks = {tick["match_id"]: tick for tick in self._market_runtime.get_ticks(limit=500)}
            matches = {item.match_id: item for item in self._market_runtime.get_matches()}
        rows: list[dict] = []
        for index, item in enumerate(instance.executor.positions):
            latest = latest_ticks.get(item.match_id, {})
            current_price = float(latest.get("bid", item.entry_price))
            pnl = (current_price - item.entry_price) * (item.amount / max(item.entry_price, 0.000001))
            match = matches.get(item.match_id)
            rows.append(
                {
                    "id": f"{trading_id}-P{index + 1:03d}",
                    "trading_id": trading_id,
                    "strategy_id": item.strategy_id,
                    "match_id": item.match_id,
                    "match_name": f"{match.team_home} vs {match.team_away}" if match is not None else item.match_id,
                    "outcome": item.outcome,
                    "entry_price": item.entry_price,
                    "current_price": current_price,
                    "amount": item.amount,
                    "pnl": pnl,
                }
            )
        return rows

    async def dispatch_tick(self, tick: MarketTickEvent, match: MatchCard) -> None:
        async with self._lock:
            for instance in self._tradings.values():
                if instance.status != "running":
                    continue
                if match.sport.value.lower() not in instance.affect_sports:
                    continue
                await instance.enqueue_tick(tick)
                if match.status.value.lower() == "finished":
                    winning = "home" if (match.score_home or 0) >= (match.score_away or 0) else "away"
                    instance.executor.settle_match(match.match_id, winning)

    async def start_dispatcher(self) -> None:
        if self._market_runtime is None or self._dispatcher_task is not None:
            return
        if not self._has_running_tradings():
            return
        self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

    async def stop_dispatcher(self) -> None:
        if self._dispatcher_task is None:
            return
        self._dispatcher_task.cancel()
        self._dispatcher_task = None

    async def _dispatcher_loop(self) -> None:
        while True:
            produced = await self._market_runtime.step_once()
            for match, tick in produced:
                await self.dispatch_tick(tick, match)
            await asyncio.sleep(1)

    def _require(self, trading_id: str) -> TradingInstance:
        instance = self._tradings.get(trading_id)
        if instance is None:
            raise KeyError(f"trading not found: {trading_id}")
        return instance

    def _has_running_tradings(self) -> bool:
        return any(item.status == "running" for item in self._tradings.values())

    def _schedule_persist(self, action: str, instance: TradingInstance) -> None:
        if self._repository is None:
            return
        try:
            asyncio.get_running_loop().create_task(self._persist(action, instance))
        except RuntimeError:
            return

    def _schedule_snapshot_persist(self, instance: TradingInstance) -> None:
        if self._repository is None:
            return
        try:
            asyncio.get_running_loop().create_task(instance._persist_snapshot())
        except RuntimeError:
            return

    async def _persist(self, action: str, instance: TradingInstance) -> None:
        try:
            if action in {"create", "update"}:
                await self._repository.save_trading(
                    {
                        "trading_id": instance.trading_id,
                        "strategy_name": instance.strategy_name,
                        "strategy_params": instance.strategy_params,
                        "affect_sports": instance.affect_sports,
                        "mode": instance.mode,
                        "status": instance.status,
                        "initial_balance": instance.initial_balance,
                        "account_alias": instance.account_alias,
                    }
                )
            else:
                await self._repository.update_trading_status(
                    {
                        "trading_id": instance.trading_id,
                        "status": instance.status,
                    }
                )
        except Exception:
            return
