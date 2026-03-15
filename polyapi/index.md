# Polymarket API 索引

## 1. 查询入口

- Market Discovery：`gamma-api.polymarket.com`
- Trading & Orderbook：`clob.polymarket.com`
- Portfolio & Activity：`data-api.polymarket.com`

## 2. 常用能力映射

### 2.1 比赛/市场发现
- 列表查询 events/markets
- 按 id 或 slug 查询单条事件
- 标签、分类与活跃状态过滤

### 2.2 行情与交易
- 获取盘口与价格
- 订阅实时行情
- 下单、撤单、查询订单状态

### 2.3 用户数据
- 查询持仓
- 查询交易历史
- 查询账户活动

## 3. 本项目使用映射

- 左侧比赛区：读取市场发现能力（live/pre + 成交量过滤）
- 中间图表：读取行情与历史价格能力
- 右侧交易：模拟执行器与真实执行器统一订单协议，真实交易走 PM 交易接口

## 4. 后续补充

- 补充认证与签名细节
- 补充限流规则
- 补充 websocket topic 与 payload 结构
