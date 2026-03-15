# PM 多策略交易系统设计文档

## 1. 设计目标

- 构建事件驱动、异步优先、策略可插拔的交易系统。
- 将高频行情处理与交易决策解耦，保证实时性与可扩展性。
- 在不重构现有前端页面结构的前提下完成数据接入。

## 2. 总体架构

### 2.1 分层
- Connectors：PM/Goalserve 的 REST 与 WS 接入。
- Normalizer：外部字段映射到统一领域模型。
- Event Bus：标准化事件发布与订阅。
- Strategy Runtime：多策略隔离执行。
- Execution：模拟执行器与真实执行器。
- Storage：Redis 高频缓存 + PostgreSQL/Timescale 持久化。
- API Gateway：提供 HTTP/WS 给前端。

### 2.2 核心数据流
- 抓取候选赛事 -> 建立 WS -> 标准化事件 -> Redis 缓存。
- 事件广播给策略 -> 输出交易信号 -> 执行器下单/撤单。
- 执行结果写日志与持仓 -> API 推送前端。
- 重采样任务将高频价格写入 Timescale 分钟表。

## 3. 领域模型

### 3.1 赛事与市场
- Match：比赛主键、运动类型、联赛、开赛时间、状态。
- Outcome：主胜/客胜/平局盘口与概率。
- MarketTick：时间点盘口快照（bid/ask/volume）。

### 3.2 交易与策略
- StrategyConfig：策略名称、参数定义、运行模式。
- TradeSignal：策略输出动作（buy/sell/cancel）与置信度。
- Order：订单生命周期（created/open/partial/filled/canceled/rejected）。
- Position：持仓、均价、已实现/未实现收益。
- TradeLog：策略日志、交易日志、告警日志。

## 4. 匹配设计（PM vs Goalserve）

- 名称归一化：去噪、缩写映射、别名词典。
- 时间归一化：统一 UTC，对齐开赛时间窗口。
- 评分机制：name_score + time_score + league_score。
- 阈值策略：
  - 高于 high_threshold：自动绑定。
  - 低于 low_threshold：拒绝绑定。
  - 中间区间：进入人工确认队列。

## 5. 存储设计

### 5.1 Redis
- 保存 live 赛事最新快照。
- 存放事件流或队列，支撑策略快速消费。
- 为 API 提供低延迟读取路径。

### 5.2 PostgreSQL/Timescale
- 业务表：matches、match_mapping、orders、positions、strategy_runs、trade_logs。
- 时序表：market_ticks（hypertable）。
- 通过异步写入任务将 Redis 数据按分钟聚合入库。

## 6. 策略引擎设计

- StrategyBase 统一接口：
  - `get_config_schema()`
  - `on_market_event(event)`
  - `on_match_event(event)`
  - `on_timer(ts)`
  - `on_fill(fill_event)`
- Runtime 管理策略生命周期：
  - 加载配置
  - 启停策略
  - 错误隔离
  - 心跳与健康状态

## 7. 交易执行设计

### 7.1 模拟执行器
- 读取当前盘口模拟成交。
- 支持手续费、滑点、部分成交模型。
- 产出与真实执行一致的订单/成交事件。

### 7.2 真实执行器
- 通过账户别名加载 PM 认证信息。
- 执行前进行余额与风控校验。
- 记录完整审计日志与失败原因。

## 8. API 设计（最小集）

- `GET /api/v1/health`：系统健康状态。
- `GET /api/v1/matches`：比赛列表（支持 live/pre、sport 过滤）。
- `GET /api/v1/strategies`：策略清单与参数定义。
- `POST /api/v1/simulation/start`：启动模拟交易。
- `POST /api/v1/live/start`：启动真实交易（受风控保护）。

## 9. 前端对接策略

- 保留现有三栏布局与组件层级。
- 用 API Client 替换当前 context 内 mock 数据来源。
- 在 MatchDetail 中补充 Goalserve 信息块数据绑定。
- 在 TradingPanel 中补充账户别名与策略参数表单映射。

## 10. 可观测性

- 结构化日志：trace_id、match_id、strategy_id、order_id。
- 指标：
  - 数据延迟
  - WS 重连次数
  - 策略处理耗时
  - 订单成功率
- 告警：
  - 数据流中断
  - 策略异常退出
  - 真实交易拒单率异常
