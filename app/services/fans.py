from app.db import get_connection

DEFAULT_FANS = [
    {"channel_index": i, "default_name": f"Fan {i}"} for i in range(1, 8)
]


def seed_fans_if_empty() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM fan_channels").fetchone()
        if row["count"] == 0:
            conn.executemany(
                """
                INSERT INTO fan_channels (channel_index, name, default_name)
                VALUES (:channel_index, :default_name, :default_name)
                """,
                DEFAULT_FANS,
            )
            conn.commit()


def list_fans():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, channel_index, name, default_name
            FROM fan_channels
            ORDER BY channel_index ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def update_fan_name(fan_id: int, name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE fan_channels
            SET name = ?
            WHERE id = ?
            """,
            (name, fan_id),
        )
        conn.commit()
