from app.runtime.trading_runtime import TradingRuntime
from app.runtime.trading_manager import TradingManager


runtime = TradingRuntime()
trading_manager = TradingManager(market_runtime=runtime, repository=runtime.repository)
