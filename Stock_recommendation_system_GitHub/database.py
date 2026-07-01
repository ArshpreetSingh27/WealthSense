import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "master_predictor.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
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
        SELECT u.email, u.created_at, COUNT(p.id) as holdings
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
            "holdings": row[2]
        })
    return summary

def delete_user_account(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    email = email.lower().strip()
    try:
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
    # Initialize when ran directly
    init_db()
    print(f"Database initialized at {DB_FILE}")
