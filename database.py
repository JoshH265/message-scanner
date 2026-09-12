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
    global connection_pool
    if not connection_pool:
        init_connection_pool()
    return connection_pool.getconn()


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
        
        # Create table for reminders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                remind_at TIMESTAMPTZ NOT NULL,
                title TEXT NOT NULL,
                note TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                delivered BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_reminders_due 
            ON reminders(delivered, remind_at)
        ''')
        
        conn.commit()
        print("Database tables initialised")
    except Exception as e:
        print(f"Error initialising database {e}")
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
# Reminder Functions


def add_reminder(user_id, remind_at, title, note=None):
    """Add a reminder for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (user_id, remind_at, title, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (user_id, remind_at, title, note))
        reminder_id = cursor.fetchone()[0]
        conn.commit()
        return reminder_id
    finally:
        cursor.close()
        return_db_connection(conn)

def get_due_reminders():
    """Get all reminders that are due and not yet delivered"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, title, note, remind_at
            FROM reminders
            WHERE delivered = FALSE AND remind_at <= now()
            ORDER BY remind_at
        ''')
        return cursor.fetchall()
    finally:
        cursor.close()
        return_db_connection(conn)

def mark_reminder_delivered(reminder_id):
    """Mark a reminder as delivered"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE reminders SET delivered = TRUE WHERE id = %s', (reminder_id,))
        conn.commit()
    finally:
        cursor.close()
        return_db_connection(conn)

def get_user_reminders(user_id):
    """Get all upcoming (undelivered) reminders for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, note, remind_at
            FROM reminders
            WHERE user_id = %s AND delivered = FALSE
            ORDER BY remind_at
        ''', (user_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        return_db_connection(conn)

def cancel_reminder(user_id, reminder_id):
    """Cancel a reminder owned by a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reminders WHERE id = %s AND user_id = %s', (reminder_id, user_id))
        removed = cursor.rowcount > 0
        conn.commit()
        return removed
    finally:
        cursor.close()
        return_db_connection(conn)