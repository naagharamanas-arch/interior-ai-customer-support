
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "chat_memory.db"


def initialize_database():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_customer
            ON chat_history (customer_id, id)
        """)

    print("Chat memory database initialized successfully.")


def save_message(customer_id, role, message):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO chat_history (customer_id, role, message)
            VALUES (?, ?, ?)
            """,
            (customer_id, role, message),
        )


def get_chat_history(customer_id, limit=20):
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT role, message
            FROM chat_history
            WHERE customer_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()

    return [
        {"role": role, "content": message}
        for role, message in reversed(rows)
    ]


def clear_chat_history(customer_id):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "DELETE FROM chat_history WHERE customer_id = ?",
            (customer_id,),
        )


if __name__ == "__main__":
    initialize_database()

    test_customer = "test_customer_001"

    save_message(
        test_customer,
        "user",
        "I need aluminium solar sections."
    )

    save_message(
        test_customer,
        "assistant",
        "Please share the required quantity."
    )

    history = get_chat_history(test_customer)

    print("\nSaved chat history:")
    for item in history:
        print(f'{item["role"]}: {item["content"]}')

    clear_chat_history(test_customer)
    print("\nTest chat history cleared.")
