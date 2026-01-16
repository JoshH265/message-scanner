import psycopg2
from psycopg2 import pool
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

# Database connection pool
connection_pool = None

def init_connection_pool():
    """Initialise the database connection pool"""
    global connection_pool
    try:
        from psycopg2 import pool
        connection_pool = pool.SimpleConnectionPool(
            1, 10,
            DATABASE_URL
        )
        print("Database connection pool created")

    except Exception as e:
        print(f"Error creating connection pool: {e}")
        raise

def get_db_connection():
    """Get a connection from the pool"""
    if connection_pool:
        return connection_pool.getconn()
    raise Exception("Database connection pool not initialized")


def return_db_connection(conn):
    """Return connection to the pool"""    
    if connection_pool:
        connection_pool.putconn(conn)

def init_db():
    """Initialise the database with required tables"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_triggers (
                user_id BIGINT,
                trigger_word TEXT,
                PRIMARY KEY (user_id, trigger_word)
            )
        ''')
        
        # Create table for user settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY,
                notifications_enabled BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trigger_word 
            ON user_triggers(trigger_word)
        ''')
        
        # Create table for token monitoring
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_monitors (
                token_mint TEXT PRIMARY KEY,
                added_by BIGINT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create table for claim event tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS claim_events (
                signature TEXT PRIMARY KEY,
                token_mint TEXT NOT NULL,
                wallet TEXT NOT NULL,
                is_creator BOOLEAN,
                amount TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token_mint) REFERENCES token_monitors(token_mint)
            )
        ''')
        
        # Create indexes for token monitoring
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_claim_events_token_mint 
            ON claim_events(token_mint)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_claim_events_timestamp 
            ON claim_events(timestamp)
        ''')

        conn.commit()
        print("Database tables initialised")
    except Exception as e:
        print(f"Error initialising BB {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        return_db_connection(conn)


#############


def get_user_triggers(user_id):
    """Get all trigger words for a specific user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT trigger_word FROM user_triggers WHERE user_id = %s', (user_id,))
        triggers = [row[0] for row in cursor.fetchall()]
        return triggers
    finally:
        cursor.close()
        return_db_connection(conn)

def get_all_users_monitoring(word):
    """Get all users who are monitoring a specific word"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_triggers WHERE trigger_word = %s', (word.lower(),))
        users = [row[0] for row in cursor.fetchall()]
        return users
    finally:
        cursor.close()
        return_db_connection(conn)

def add_trigger_word(user_id, word):
    """Add a trigger word for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO user_triggers (user_id, trigger_word) VALUES (%s, %s)',
                          (user_id, word.lower()))
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            conn.rollback()
            return False  # Word already exists
    finally:
        cursor.close()
        return_db_connection(conn)

def add_multiple_trigger_words(user_id, words):
    """Add multiple trigger words for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        added = []
        duplicates = []
        
        for word in words:
            word = word.strip().lower()
            if not word:
                continue
            try:
                cursor.execute('INSERT INTO user_triggers (user_id, trigger_word) VALUES (%s, %s)',
                              (user_id, word))
                added.append(word)
            except psycopg2.IntegrityError:
                duplicates.append(word)
                conn.rollback()
        
        conn.commit()
        return added, duplicates
    finally:
        cursor.close()
        return_db_connection(conn)
    

def remove_trigger_word(user_id, word):
    """Remove a trigger word for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_triggers WHERE user_id = %s AND trigger_word = %s',
                      (user_id, word.lower()))
        removed = cursor.rowcount > 0
        conn.commit()
        return removed
    finally:
        cursor.close()
        return_db_connection(conn)

def is_notifications_enabled(user_id):
    """Check if notifications are enabled for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT notifications_enabled FROM user_settings WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else True  # Default to enabled
    finally:
        cursor.close()
        return_db_connection(conn)

def toggle_notifications(user_id):
    """Toggle notifications on/off for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get current state
        cursor.execute('SELECT notifications_enabled FROM user_settings WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result:
            new_state = not result[0]
            cursor.execute('UPDATE user_settings SET notifications_enabled = %s WHERE user_id = %s',
                          (new_state, user_id))
        else:
            new_state = False  # If no record, they want to disable (default is enabled)
            cursor.execute('INSERT INTO user_settings (user_id, notifications_enabled) VALUES (%s, %s)',
                          (user_id, new_state))
        
        conn.commit()
        return new_state
    finally:
        cursor.close()
        return_db_connection(conn)


#############
# Token Monitoring Functions

def add_token_monitor(token_mint, user_id):
    """Add a token to monitor for fee claim events"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO token_monitors (token_mint, added_by) 
            VALUES (%s, %s)
            ON CONFLICT (token_mint) DO NOTHING
        ''', (token_mint, user_id))
        success = cursor.rowcount > 0
        conn.commit()
        return success
    finally:
        cursor.close()
        return_db_connection(conn)

def remove_token_monitor(token_mint):
    """Remove a token from monitoring"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM token_monitors WHERE token_mint = %s', (token_mint,))
        removed = cursor.rowcount > 0
        
        # Also clean up related claim events
        cursor.execute('DELETE FROM claim_events WHERE token_mint = %s', (token_mint,))
        
        conn.commit()
        return removed
    finally:
        cursor.close()
        return_db_connection(conn)

def get_all_monitored_tokens():
    """Get all tokens being monitored"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT token_mint, added_by, added_at FROM token_monitors ORDER BY added_at')
        return cursor.fetchall()
    finally:
        cursor.close()
        return_db_connection(conn)

def update_last_checked(token_mint):
    """Update the last checked timestamp for a token"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE token_monitors SET last_checked = CURRENT_TIMESTAMP WHERE token_mint = %s', (token_mint,))
        conn.commit()
    finally:
        cursor.close()
        return_db_connection(conn)

def add_claim_event(signature, token_mint, wallet, is_creator, amount, timestamp):
    """Add a new claim event to track"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO claim_events (signature, token_mint, wallet, is_creator, amount, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (signature) DO NOTHING
        ''', (signature, token_mint, wallet, is_creator, amount, timestamp))
        success = cursor.rowcount > 0
        conn.commit()
        return success
    finally:
        cursor.close()
        return_db_connection(conn)

def get_unnotified_claim_events():
    """Get all claim events that haven't been notified yet"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT signature, token_mint, wallet, is_creator, amount, timestamp
            FROM claim_events 
            WHERE notified = FALSE 
            ORDER BY created_at
        ''')
        return cursor.fetchall()
    finally:
        cursor.close()
        return_db_connection(conn)

def mark_claim_event_notified(signature):
    """Mark a claim event as notified"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE claim_events SET notified = TRUE WHERE signature = %s', (signature,))
        conn.commit()
    finally:
        cursor.close()
        return_db_connection(conn)