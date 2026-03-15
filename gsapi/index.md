# Goalserve 文档索引

## 1. 当前本地资源

- `gsapi/raw/homepage.html`：官网文档首页快照。

## 2. 接入关注点

- 足球与篮球实时赛事数据接口。
- 历史比赛下载接口。
- 阵容、赔率、赛程与状态字段定义。
- websocket 或实时推送能力说明。

## 3. 本项目映射

- `connectors/goalserve/rest`：历史下载与补拉。
- `connectors/goalserve/realtime`：live 赛事实时更新。
- `domain/normalizers`：Goalserve 字段到统一模型映射。
- `matching`：与 PM 比赛实体匹配。

## 4. 补充计划

- 追加关键页面快照至 `gsapi/raw/`。
- 为每个页面建立“接口用途 -> 字段 -> 目标表”的映射清单。
