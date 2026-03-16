from dataclasses import dataclass


@dataclass(slots=True)
class Position:
    strategy_id: str
    match_id: str
    outcome: str
    amount: float
    entry_price: float


class SimulationExecutor:
    def __init__(self, initial_balance: float = 10000.0) -> None:
        self.balance = initial_balance
        self.positions: list[Position] = []
        self.logs: list[dict] = []

    def execute(self, strategy_id: str, action: str, match_id: str, outcome: str, price: float, amount: float) -> dict:
        if action == "buy":
            if self.balance < amount:
                return {"status": "rejected", "reason": "insufficient_balance"}
            self.balance -= amount
            self.positions.append(
                Position(
                    strategy_id=strategy_id,
                    match_id=match_id,
                    outcome=outcome,
                    amount=amount,
                    entry_price=price,
                )
            )
            result = {"status": "filled", "action": action, "price": price, "amount": amount, "outcome": outcome}
            self.logs.append(result)
            return result
        target = next(
            (p for p in self.positions if p.strategy_id == strategy_id and p.match_id == match_id and p.outcome == outcome),
            None,
        )
        if target is None:
            return {"status": "rejected", "reason": "no_position"}
        profit = (price - target.entry_price) * (target.amount / max(target.entry_price, 0.000001))
        self.balance += target.amount + profit
        self.positions = [p for p in self.positions if p is not target]
        result = {
            "status": "filled",
            "action": action,
            "price": price,
            "amount": amount,
            "outcome": outcome,
            "profit": profit,
        }
        self.logs.append(result)
        return result

    def settle_match(self, match_id: str, winning_outcome: str) -> list[dict]:
        closed: list[dict] = []
        for position in list(self.positions):
            if position.match_id != match_id:
                continue
            settle_price = 1.0 if position.outcome == winning_outcome else 0.0
            profit = (settle_price - position.entry_price) * (position.amount / max(position.entry_price, 0.000001))
            self.balance += position.amount + profit
            self.positions.remove(position)
            result = {
                "status": "filled",
                "action": "settle",
                "price": settle_price,
                "amount": position.amount,
                "outcome": position.outcome,
                "profit": profit,
                "match_id": match_id,
            }
            closed.append(result)
            self.logs.append(result)
        return closed
