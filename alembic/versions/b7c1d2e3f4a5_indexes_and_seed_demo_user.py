"""indexes, seed demo user, cascade FKs

Revision ID: b7c1d2e3f4a5
Revises: 9c522449fdf1
Create Date: 2026-11-07 19:30:00.000000

在原有迁移之后补齐生产可用所需的基础设施：
  - pgvector 扩展与 HNSW 向量索引
  - 外键索引（避免全表扫描）与级联删除
  - messages / conversations 的创建时间
  - 演示用户 id=1（/agent 默认以该用户身份运行）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = '9c522449fdf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- pgvector 扩展（需要数据库账号有创建扩展的权限）----
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---- 外键索引 ----
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_user_id "
               "ON conversations (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_conversation_id "
               "ON messages (conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_document_id "
               "ON chunks (document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_tenant_filename "
               "ON documents (tenant_id, filename)")

    # ---- 向量索引：HNSW + 余弦距离（pgvector >= 0.5）----
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
               "ON chunks USING hnsw (embedding vector_cosine_ops)")

    # ---- 级联删除：删文档/会话时自动清掉子表 ----
    op.execute("ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_document_id_fkey")
    op.execute("ALTER TABLE chunks ADD CONSTRAINT chunks_document_id_fkey "
               "FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE")

    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey")
    op.execute("ALTER TABLE messages ADD CONSTRAINT messages_conversation_id_fkey "
               "FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE")

    op.execute("ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_user_id_fkey")
    op.execute("ALTER TABLE conversations ADD CONSTRAINT conversations_user_id_fkey "
               "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE")

    # ---- 时间戳 ----
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS created_at "
               "timestamptz NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS created_at "
               "timestamptz NOT NULL DEFAULT now()")

    # ---- 演示用户：/agent 在未传 X-User-Id 时使用 id=1 ----
    op.execute(
        "INSERT INTO users (id, email, name) "
        "VALUES (1, 'demo@example.com', 'Demo User') "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('users', 'id'), "
        "GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS created_at")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_documents_tenant_filename")
    op.execute("DROP INDEX IF EXISTS ix_chunks_document_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_conversation_id")
    op.execute("DROP INDEX IF EXISTS ix_conversations_user_id")
    op.execute("DELETE FROM users WHERE email = 'demo@example.com'")
