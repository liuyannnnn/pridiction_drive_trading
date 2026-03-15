# Backend

## 启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启用真实外部流（可选）：

```bash
EXTERNAL_STREAM_ENABLED=true
POLYMARKET_WS_ENABLED=true
GOALSERVE_WS_ENABLED=true
GOALSERVE_TOKEN_URL="https://your-goalserve-token-endpoint"
GOALSERVE_TOKEN_METHOD=auto
GOALSERVE_TOKEN_TTL_MINUTES=60
GOALSERVE_TOKEN_REFRESH_AHEAD_SECONDS=300
GOALSERVE_WS_URL="wss://your-goalserve-ws-endpoint?token={token}"
GOALSERVE_SUBSCRIBE_PAYLOAD='{"type":"subscribe","sports":["soccer","basketball"]}'
```

Goalserve 鉴权模式说明：

```bash
# auto: 依次尝试 POST json -> POST form -> GET query
GOALSERVE_TOKEN_METHOD=auto
# 或固定模式
# GOALSERVE_TOKEN_METHOD=post_json
# GOALSERVE_TOKEN_METHOD=post_form
# GOALSERVE_TOKEN_METHOD=get_query
```

Goalserve 文档写明 token 默认有效期为 60 分钟，系统会在到期前按 `GOALSERVE_TOKEN_REFRESH_AHEAD_SECONDS` 提前断开并重连以刷新 token。

## 验证

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/matches
curl http://127.0.0.1:8000/api/v1/settings/collector
```
