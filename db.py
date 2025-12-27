import sqlite3
import random 
from pathlib import Path
from traceback import print_exc

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.db"

def connect(func):
    def wrapper(*args, **kwargs):
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        result = None
        try:
            result = func(cur, *args, **kwargs)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] in {func.__name__}: {print_exc()}")
        finally:
            conn.close()
        return result
    return wrapper


@connect 
def init_db(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            username TEXT,
            role TEXT DEFAULT 'citizen',
            dead INTEGER DEFAULT 0,
            voted INTEGER DEFAULT 0
        )""")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_type TEXT NOT NULL,
            target_username TEXT NOT NULL,
            voted_id INTEGER NOT NULL,
            FOREIGN KEY (voted_id) REFERENCES players(id)
        )""")

@connect
def insert_player(cur, player_id: int, username: str) -> None:
    cur.execute("""
        INSERT OR REPLACE INTO players(player_id, username, dead, voted)
        VALUES (?, ?, COALESCE((SELECT dead FROM players WHERE player_id=?), 0), 0)
    """, (player_id, username, player_id))


@connect
def players_amount(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM players")
    return cur.fetchone()[0]

@connect
def get_mafia_usernames(cur) -> str:
    cur.execute("SELECT username FROM players WHERE role = 'mafia' AND dead=0")
    rows = cur.fetchall()
    return "\n".join(row[0] for row in rows)

@connect
def get_players_roles(cur) -> list:
    cur.execute("SELECT player_id, role FROM players")
    return cur.fetchall()

@connect
def get_all_alive(cur) -> list:
    cur.execute("SELECT username FROM players WHERE dead=0")
    return [row[0] for row in cur.fetchall()] # [("Имя",), ("Имя",), ("Имя",)] -> ["Имя", "Имя", "Имя"]

@connect
def set_roles(cur):
    cur.execute("SELECT player_id FROM players ORDER BY player_id")
    player_rows = cur.fetchall()
    print(player_rows)
    n = len(player_rows)
    if n == 0:
        return
    
    mafias = max(1, int(n * 0.3))
    roles = ["mafia"] * mafias + ["citizen"] * (n - mafias)
    random.shuffle(player_rows)
    for (player_id,), role in zip(player_rows, roles):
        cur.execute("UPDATE players SET role=?, dead=0, voted=0 WHERE player_id =?", (role, player_id))

@connect
def user_exists(cur, player_id: int) -> bool:
    cur.execute("SELECT 1 FROM players WHERE player_id = ?", (player_id,))
    return cur.fetchone() is not None

@connect
def cast_vote(cur, vote_type: str, target_username: str, voted_id: int) -> bool:
    cur.execute("SELECT dead, voted FROM players WHERE player_id = ?", (voted_id,))

    row = cur.fetchone()
    if not row:
        return False
    dead, voted = row
    if dead != 0 or voted != 0:
        return False
    
    cur.execute("SELECT 1 FROM players WHERE username = ? AND dead = 0", (target_username,))
    if not cur.fetchone():
        return False
    
    cur.execute("INSERT INTO votes (vote_type, target_username, voted_id) VALUES (?, ?, ?)",
                (vote_type, target_username, voted_id))
    cur.execute("UPDATE players SET voted = 1 WHERE player_id = ?", (voted_id,))
    return True

@connect
def mafia_kill(cur) -> str:
    cur.execute("SELECT COUNT(*) FROM players WHERE role='mafia' AND dead=0")
    mafia_alive = cur.fetchone()[0]
    if mafia_alive == 0:
        return "Никого"
    
    cur.execute("""
        SELECT target_username, COUNT(*) as count
        FROM votes
        WHERE vote_type = 'mafia'
        GROUP BY target_username
        ORDER BY count DESC
        LIMIT 1
    """)

    top = cur.fetchone()
    if not top:
        return "Никого"
    target, count = top
    if count == mafia_alive:
        cur.execute("UPDATE players SET dead = 1 WHERE username = ?", (target,))
        return target
    return "Никого"

 
@connect
def citizen_kill(cur) -> str:
    cur.execute("""
        SELECT target_username, COUNT(*) as count 
        FROM votes 
        WHERE vote_type='citizen'
        GROUP BY target_username
        ORDER BY count DESC
        LIMIT 2
    """)

    rows = cur.fetchall()
    if not rows:
        return "Никого"
    top = rows[0]
    top_username, top_count = top
    if len(rows) > 1 and rows[1][1] == top_count:
        return "Никого"
    cur.execute("UPDATE players SET dead = 1 WHERE username = ?", (top_username,))
    return top_username

@connect 
def clear_round(cur, reset_dead: bool = False) -> None:
    cur.execute("DELETE FROM votes")
    if reset_dead:
        cur.execute("UPDATE players SET dead = 0, voted = 0, role = 'citizen'")
    else:
        cur.execute("UPDATE players SET voted = 0")


@connect
def check_winner(cur) -> str | None:
    cur.execute("SELECT COUNT(*) FROM players WHERE role='mafia' AND dead=0")
    mafia_alive = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM players WHERE role!='mafia AND dead=0")
    citizen_alive = cur.fetchone()[0]
    if mafia_alive >= citizen_alive and mafia_alive > 0:
        return "Мафия"
    if mafia_alive == 0:
        return "Горожане "
    return None



if __name__ == "__main__":
    # init_db()
    # insert_player(1, "Артём")
    # print(players_amount())
    # set_roles()
    # print(get_mafia_usernames())
    # print(get_all_alive())
    # print(get_players_roles())
    # print(cast_vote("mafia", "Кирилл", 2))
    # print(mafia_kill())
    print(citizen_kill())
    clear_round(reset_dead=True)