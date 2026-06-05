import sqlite3
import json
from datetime import datetime
import os

# Vercel/serverless: project dir is read-only at runtime — use /tmp
_dir = os.path.dirname(os.path.abspath(__file__))
_local = os.path.join(_dir, "ghost.db")
_default = "/tmp/ghost.db" if (os.getenv("VERCEL") or not os.access(_dir, os.W_OK)) else _local
DB_PATH = os.getenv("DB_PATH", _default)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        emotion TEXT DEFAULT 'neutro',
        topics TEXT DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE,
        value TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS cognitive_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        pattern_type TEXT,
        description TEXT,
        frequency INTEGER DEFAULT 1,
        context TEXT
    );
    CREATE TABLE IF NOT EXISTS contradictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        declared TEXT,
        observed TEXT,
        frequency INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        title TEXT,
        description TEXT,
        action TEXT,
        score INTEGER,
        status TEXT DEFAULT 'nova',
        window_closes TEXT
    );
    CREATE TABLE IF NOT EXISTS simulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        topic TEXT,
        cost_analysis TEXT,
        risk_analysis TEXT,
        return_analysis TEXT,
        causal_inversion TEXT
    );
    CREATE TABLE IF NOT EXISTS ghost_thoughts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        thought TEXT,
        triggered_by TEXT,
        shown INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS actions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        task TEXT,
        result TEXT,
        apis_used TEXT
    );
    """)
    conn.commit()
    conn.close()

def save_message(session_id, role, content, emotion="neutro", topics="[]"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO memories (timestamp, session_id, role, content, emotion, topics) VALUES (?,?,?,?,?,?)",
              (datetime.now().isoformat(), session_id, role, content, emotion, topics))
    conn.commit()
    conn.close()

def get_last_messages(n=40):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp, emotion FROM memories ORDER BY id DESC LIMIT ?", (n,))
    rows = c.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": r[0], "content": r[1], "timestamp": r[2], "emotion": r[3]} for r in rows]

def count_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT session_id) FROM memories")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def save_profile(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?,?,?)",
              (key, value, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_profile():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key, value FROM profile")
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def get_profile_text():
    p = get_profile()
    if not p:
        return "Perfil ainda não configurado."
    return "\n".join(f"{k}: {v}" for k, v in p.items())

def save_pattern(pattern_type, description, context=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, frequency FROM cognitive_patterns WHERE pattern_type=? AND description=?",
              (pattern_type, description))
    row = c.fetchone()
    if row:
        c.execute("UPDATE cognitive_patterns SET frequency=?, timestamp=? WHERE id=?",
                  (row[1]+1, datetime.now().isoformat(), row[0]))
    else:
        c.execute("INSERT INTO cognitive_patterns (timestamp, pattern_type, description, context) VALUES (?,?,?,?)",
                  (datetime.now().isoformat(), pattern_type, description, context))
    conn.commit()
    conn.close()

def get_patterns_text():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT pattern_type, description, frequency FROM cognitive_patterns ORDER BY frequency DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "Nenhum padrão identificado ainda."
    return "\n".join([f"[{r[0]}] {r[1]} (apareceu {r[2]}x)" for r in rows])

def save_contradiction(declared, observed):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, frequency FROM contradictions WHERE declared=?", (declared,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE contradictions SET frequency=?, timestamp=? WHERE id=?",
                  (row[1]+1, datetime.now().isoformat(), row[0]))
    else:
        c.execute("INSERT INTO contradictions (timestamp, declared, observed) VALUES (?,?,?)",
                  (datetime.now().isoformat(), declared, observed))
    conn.commit()
    conn.close()

def get_contradictions_text():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT declared, observed, frequency FROM contradictions ORDER BY frequency DESC LIMIT 5")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "Nenhuma contradição registrada ainda."
    return "\n".join([f"Disse querer: {r[0]} | Comportamento: {r[1]} | Vezes: {r[2]}" for r in rows])

def save_opportunity(title, description, action, score, window="indefinida"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO opportunities (timestamp, title, description, action, score, window_closes) VALUES (?,?,?,?,?,?)",
              (datetime.now().isoformat(), title, description, action, score, window))
    conn.commit()
    conn.close()

def get_opportunities(status="nova"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, description, action, score, window_closes FROM opportunities WHERE status=? ORDER BY score DESC",
              (status,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "description": r[2], "action": r[3], "score": r[4], "window": r[5]} for r in rows]

def update_opportunity(id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE opportunities SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

def save_simulation(topic, cost, risk, ret, causal):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO simulations (timestamp, topic, cost_analysis, risk_analysis, return_analysis, causal_inversion) VALUES (?,?,?,?,?,?)",
              (datetime.now().isoformat(), topic, cost, risk, ret, causal))
    conn.commit()
    conn.close()

def save_thought(thought, triggered_by="sistema"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO ghost_thoughts (timestamp, thought, triggered_by) VALUES (?,?,?)",
              (datetime.now().isoformat(), thought, triggered_by))
    conn.commit()
    conn.close()

def get_unshown_thoughts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, thought, triggered_by FROM ghost_thoughts WHERE shown=0")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "thought": r[1], "triggered_by": r[2]} for r in rows]

def mark_thought_shown(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE ghost_thoughts SET shown=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

def save_action(task, result, apis_used=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO actions_log (timestamp, task, result, apis_used) VALUES (?,?,?,?)",
              (datetime.now().isoformat(), task, result, apis_used))
    conn.commit()
    conn.close()

init_db()
