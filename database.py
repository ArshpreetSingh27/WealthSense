import sqlite3
import os
from contextlib import closing
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_FILE = os.path.join(BASE_DIR, "wealth_sense.db")
LEGACY_DB_FILE = os.path.join(BASE_DIR, "master_predictor.db")
DB_FILE = DEFAULT_DB_FILE

def init_db():
    if DB_FILE == DEFAULT_DB_FILE and not os.path.exists(DB_FILE) and os.path.exists(LEGACY_DB_FILE):
        with sqlite3.connect(LEGACY_DB_FILE) as old_db, sqlite3.connect(DB_FILE) as new_db:
            old_db.backup(new_db)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email),
            UNIQUE(user_email, ticker)
        )
    ''')
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in cursor.fetchall()}
    if "is_admin" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    cursor.execute("DROP TABLE IF EXISTS broker_connections")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_accounts (
            user_email TEXT PRIMARY KEY,
            starting_cash REAL NOT NULL,
            cash REAL NOT NULL,
            bot_enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_positions (
            user_email TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            average_price REAL NOT NULL CHECK (average_price > 0),
            PRIMARY KEY (user_email, ticker),
            FOREIGN KEY (user_email) REFERENCES paper_accounts(user_email) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            client_order_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            price REAL NOT NULL CHECK (price > 0),
            notional REAL NOT NULL,
            realized_pnl REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            market_date TEXT NOT NULL,
            executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_email, client_order_id),
            FOREIGN KEY (user_email) REFERENCES paper_accounts(user_email) ON DELETE CASCADE
        )
    ''')
    cursor.execute("PRAGMA table_info(paper_accounts)")
    if "bot_enabled" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE paper_accounts ADD COLUMN bot_enabled INTEGER NOT NULL DEFAULT 0")
    cursor.execute("PRAGMA table_info(paper_trades)")
    if "source" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE paper_trades ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
    
    # Check for missing columns in existing portfolio table
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'quantity' not in columns:
        cursor.execute("ALTER TABLE portfolio ADD COLUMN quantity REAL DEFAULT 0")
    if 'purchase_price' not in columns:
        cursor.execute("ALTER TABLE portfolio ADD COLUMN purchase_price REAL DEFAULT 0")
        
    conn.commit()
    conn.close()

def create_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    try:
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
        conn.commit()
        return True, "User created successfully."
    except sqlite3.IntegrityError:
        return False, "Email already exists."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    cursor.execute("SELECT password FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user[0], password):
        return True
    return False


def user_exists(email):
    if not email:
        return False
    with closing(sqlite3.connect(DB_FILE)) as conn:
        row = conn.execute("SELECT 1 FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    return row is not None

def user_is_admin(email):
    if not email:
        return False
    with closing(sqlite3.connect(DB_FILE)) as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    return bool(row and row[0])

def set_user_admin(email, enabled=True):
    with closing(sqlite3.connect(DB_FILE)) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE users SET is_admin=? WHERE email=?",
                (int(enabled), email.lower().strip()),
            )
            return cursor.rowcount == 1

# ================================
# PORTFOLIO MANAGEMENT
# ================================

def add_to_portfolio(email, ticker, quantity=1, purchase_price=0):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    try:
        cursor.execute("""
            INSERT INTO portfolio (user_email, ticker, quantity, purchase_price) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_email, ticker) DO UPDATE SET
                quantity = excluded.quantity,
                purchase_price = excluded.purchase_price
        """, (email, ticker.upper(), quantity, purchase_price))
        conn.commit()
        return True, f"{ticker} updated in portfolio."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remove_from_portfolio(email, ticker):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    try:
        cursor.execute("DELETE FROM portfolio WHERE user_email=? AND ticker=?", (email, ticker.upper()))
        conn.commit()
        return True, f"{ticker} removed from portfolio."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_user_portfolio(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    cursor.execute("SELECT ticker, quantity, purchase_price FROM portfolio WHERE user_email=?", (email,))
    rows = cursor.fetchall()
    conn.close()
    
    portfolio = []
    for row in rows:
        portfolio.append({
            "ticker": row[0],
            "quantity": row[1],
            "purchase_price": row[2]
        })
    return portfolio

def get_all_users_summary():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Join users and portfolio to get counts
    cursor.execute("""
        SELECT u.email, u.created_at, COUNT(p.id) as holdings, u.is_admin
        FROM users u
        LEFT JOIN portfolio p ON u.email = p.user_email
        GROUP BY u.email
        ORDER BY u.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    summary = []
    for row in rows:
        summary.append({
            "email": row[0],
            "created_at": row[1],
            "holdings": row[2],
            "is_admin": bool(row[3])
        })
    return summary

def delete_user_account(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    try:
        cursor.execute("DELETE FROM paper_trades WHERE user_email=?", (email,))
        cursor.execute("DELETE FROM paper_positions WHERE user_email=?", (email,))
        cursor.execute("DELETE FROM paper_accounts WHERE user_email=?", (email,))
        # 1. Delete portfolio items
        cursor.execute("DELETE FROM portfolio WHERE user_email=?", (email,))
        # 2. Delete user account
        cursor.execute("DELETE FROM users WHERE email=?", (email,))
        conn.commit()
        return True, f"User {email} and their data deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Initialize the database or manage an existing user's admin role.")
    parser.add_argument("--promote-admin", metavar="EMAIL")
    args = parser.parse_args()
    init_db()
    if args.promote_admin:
        if not set_user_admin(args.promote_admin):
            parser.error("That account does not exist. Register it first.")
        print(f"Admin role enabled for {args.promote_admin.lower().strip()}")
    else:
        print(f"Database initialized at {DB_FILE}")
