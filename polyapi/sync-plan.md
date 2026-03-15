# Polymarket 文档同步方案

## 1. 同步目标

- 将 docs.polymarket.com 的关键页面快照到本地。
- 将接口能力映射同步到 `polyapi/index.md`。
- 为后续自动化同步脚本预留执行规范。

## 2. 建议同步页面

- `/api-reference/introduction`
- `/api-reference/authentication`
- `/api-reference/rate-limits`
- `/quickstart/overview`
- `/quickstart`

## 3. 同步步骤

- 使用可访问网络环境执行抓取。
- 将每个页面保存为 `polyapi/raw/<slug>.md` 或 `polyapi/raw/<slug>.html`。
- 在 `polyapi/changelog.md` 记录同步时间与变更摘要。
- 变更后回归检查 `polyapi/index.md` 的能力映射是否仍准确。

## 4. 异常处理

- 当网络超时时，保留原文件并在 changelog 标记失败原因。
- 当页面结构变化时，仅更新 raw 快照，映射文档在人工确认后更新。
