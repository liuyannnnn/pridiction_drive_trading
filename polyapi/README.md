# Polymarket 文档本地索引

## 1. 说明

- 目录目标：沉淀 Polymarket 开发文档与常用接口索引，便于本项目离线查询。
- 当前网络环境下 `docs.polymarket.com` 请求存在超时，已先落地可用入口索引与能力映射。
- 后续可通过定时脚本补全原文快照。

## 2. 核心文档入口

- 文档首页：`https://docs.polymarket.com/`
- API 介绍：`https://docs.polymarket.com/api-reference/introduction`
- Quickstart：`https://docs.polymarket.com/quickstart/overview`
- API Intro（快捷入口）：`https://docs.polymarket.com/quickstart`

## 3. 三类 API 能力映射

- 市场发现（Gamma API）：`https://gamma-api.polymarket.com`
- 交易与盘口（CLOB API）：`https://clob.polymarket.com`
- 持仓与历史（Data API）：`https://data-api.polymarket.com`

## 4. 已提取要点

- Polymarket 平台由多个 API 域组成，按“发现/交易/数据”拆分。
- 市场浏览主要走 Gamma API。
- 实时价格、深度与下单主要走 CLOB API。
- 用户资产与历史活动主要走 Data API。

## 5. 补全计划

- 使用 `polyapi/sync-plan.md` 中定义的步骤周期性拉取页面快照。
- 每次同步后更新 `polyapi/index.md` 与版本时间戳。
