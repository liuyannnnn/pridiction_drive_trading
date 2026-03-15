# Infra

## 初始化数据库

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -f infra/sql/init_polypdt.sql
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -f infra/sql/enable_timescale.sql
```
