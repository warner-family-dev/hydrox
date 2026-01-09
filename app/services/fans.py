from app.db import get_connection
from app.services.settings import get_fan_count


def _default_fans(indices: list[int]):
    return [{"channel_index": i, "default_name": f"Fan {i}"} for i in indices]


def seed_fans_if_empty() -> None:
    fan_count = get_fan_count()
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM fan_channels").fetchone()
        if row["count"] == 0:
            conn.executemany(
                """
                INSERT INTO fan_channels (channel_index, name, default_name, active)
                VALUES (:channel_index, :default_name, :default_name, 1)
                """,
                _default_fans(list(range(1, fan_count + 1))),
            )
            conn.commit()
        else:
            _sync_fan_count(conn, fan_count)


def _sync_fan_count(conn, fan_count: int) -> None:
    rows = conn.execute(
        """
        SELECT channel_index FROM fan_channels
        ORDER BY channel_index ASC
        """
    ).fetchall()
    existing = {row["channel_index"] for row in rows}
    to_add = [i for i in range(1, fan_count + 1) if i not in existing]
    if to_add:
        conn.executemany(
            """
            INSERT INTO fan_channels (channel_index, name, default_name, active)
            VALUES (:channel_index, :default_name, :default_name, 1)
            """,
            _default_fans(to_add),
        )
        conn.commit()
    conn.execute(
        """
        UPDATE fan_channels
        SET active = CASE WHEN channel_index <= ? THEN 1 ELSE 0 END
        """,
        (fan_count,),
    )
    conn.commit()


def list_fans(active_only: bool = False):
    with get_connection() as conn:
        if active_only:
            rows = conn.execute(
                """
                SELECT id, channel_index, name, default_name, active, max_rpm
                FROM fan_channels
                WHERE active = 1
                ORDER BY channel_index ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, channel_index, name, default_name, active, max_rpm
                FROM fan_channels
                ORDER BY channel_index ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]


def update_fan_settings(fan_id: int, name: str, max_rpm: int | None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE fan_channels
            SET name = ?, max_rpm = ?
            WHERE id = ?
            """,
            (name, max_rpm, fan_id),
        )
        conn.commit()


def sync_fan_count(fan_count: int) -> None:
    with get_connection() as conn:
        _sync_fan_count(conn, fan_count)


def update_fan_max_rpm(channel_index: int, max_rpm: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE fan_channels
            SET max_rpm = ?
            WHERE channel_index = ?
            """,
            (max_rpm, channel_index),
        )
        conn.commit()
