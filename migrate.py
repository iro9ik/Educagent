import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "agent"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", ""),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
)
cur = conn.cursor()
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'completed'")
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS generation_id VARCHAR(64)")
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS reasoning TEXT")
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources TEXT")
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS agent_steps TEXT")
cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS attached_files TEXT")
conn.commit()
cur.close()
conn.close()
print("Migration done")
