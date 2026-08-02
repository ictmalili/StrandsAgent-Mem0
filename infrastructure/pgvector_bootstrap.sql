-- Aurora PostgreSQL 上启用 pgvector。
--
-- 用法 (在 VPC 内的堡垒机或应用主机执行):
--   PGPASSWORD='<password>' psql \
--       -h <PGVECTOR_HOST> \
--       -U <PGVECTOR_USER> \
--       -d <PGVECTOR_DBNAME> \
--       -f infrastructure/pgvector_bootstrap.sql
--
-- Mem0 首次 add() 时会自动建 collection 表并创建 HNSW 索引,这里只需保证
-- extension 已启用 & 用户对目标库有 CREATE 权限即可。

CREATE EXTENSION IF NOT EXISTS vector;

-- 可选:确认版本 (需 >= 0.5.0 才有 HNSW)
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
