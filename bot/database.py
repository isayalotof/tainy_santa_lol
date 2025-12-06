import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging
import threading

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, dsn: str, min_conn: int = 1, max_conn: int = 10):
        self.dsn = dsn
        self.connection_pool = None
        self.min_conn = min_conn
        self.max_conn = max_conn
        self._lock = threading.Lock()

    def connect(self):
        """Establish database connection pool"""
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                self.min_conn,
                self.max_conn,
                self.dsn
            )
            logger.info(f"Database connection pool established ({self.min_conn}-{self.max_conn} connections)")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    def close(self):
        """Close database connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")

    def _get_connection(self):
        """Get connection from pool"""
        if not self.connection_pool:
            raise RuntimeError("Database connection pool not initialized")
        return self.connection_pool.getconn()

    def _put_connection(self, conn):
        """Return connection to pool"""
        if self.connection_pool:
            self.connection_pool.putconn(conn)

    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Execute SQL query using connection pool"""
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                conn.commit()
                if fetch:
                    return [dict(row) for row in cur.fetchall()]
                return None
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self._put_connection(conn)

    # User operations
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user in database"""
        query = """
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name
        """
        self.execute(query, (user_id, username, first_name, last_name))

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        query = "SELECT * FROM users WHERE user_id = %s"
        result = self.execute(query, (user_id,), fetch=True)
        return result[0] if result else None

    # Room operations
    def create_room(self, room_name: str, admin_id: int, invite_code: str) -> int:
        """Create a new room"""
        query = """
            INSERT INTO rooms (room_name, admin_id, invite_code)
            VALUES (%s, %s, %s)
            RETURNING room_id
        """
        result = self.execute(query, (room_name, admin_id, invite_code), fetch=True)
        return result[0]['room_id']

    def get_room_by_id(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get room by ID"""
        query = "SELECT * FROM rooms WHERE room_id = %s"
        result = self.execute(query, (room_id,), fetch=True)
        return result[0] if result else None

    def get_room_by_invite_code(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """Get room by invite code"""
        query = "SELECT * FROM rooms WHERE invite_code = %s"
        result = self.execute(query, (invite_code,), fetch=True)
        return result[0] if result else None

    def get_user_rooms(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all rooms user is member of"""
        query = """
            SELECT r.* FROM rooms r
            JOIN room_members rm ON r.room_id = rm.room_id
            WHERE rm.user_id = %s
            ORDER BY r.created_at DESC
        """
        return self.execute(query, (user_id,), fetch=True) or []

    def update_room_drawn(self, room_id: int, is_drawn: bool = True):
        """Mark room as drawn"""
        query = """
            UPDATE rooms
            SET is_drawn = %s, drawn_at = CURRENT_TIMESTAMP
            WHERE room_id = %s
        """
        self.execute(query, (is_drawn, room_id))

    def update_room_price_range(self, room_id: int, price_range: str = None):
        """Update room price range"""
        query = """
            UPDATE rooms
            SET price_range = %s
            WHERE room_id = %s
        """
        self.execute(query, (price_range, room_id))

    def update_room_deadline(self, room_id: int, deadline: str = None):
        """Update room deadline"""
        query = """
            UPDATE rooms
            SET deadline = %s
            WHERE room_id = %s
        """
        self.execute(query, (deadline, room_id))

    def update_room_gift_time(self, room_id: int, gift_time: str = None):
        """Update room gift time"""
        query = """
            UPDATE rooms
            SET gift_time = %s
            WHERE room_id = %s
        """
        self.execute(query, (gift_time, room_id))

    def update_room_gift_location(self, room_id: int, gift_location: str = None):
        """Update room gift location"""
        query = """
            UPDATE rooms
            SET gift_location = %s
            WHERE room_id = %s
        """
        self.execute(query, (gift_location, room_id))

    # Room member operations
    def add_member_to_room(self, room_id: int, user_id: int):
        """Add user to room"""
        query = """
            INSERT INTO room_members (room_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (room_id, user_id) DO NOTHING
        """
        self.execute(query, (room_id, user_id))

    def get_room_members(self, room_id: int) -> List[Dict[str, Any]]:
        """Get all members of a room with participation status"""
        query = """
            SELECT u.*, rm.is_participating FROM users u
            JOIN room_members rm ON u.user_id = rm.user_id
            WHERE rm.room_id = %s
            ORDER BY rm.joined_at
        """
        return self.execute(query, (room_id,), fetch=True) or []

    def get_room_participants(self, room_id: int) -> List[Dict[str, Any]]:
        """Get only participating members of a room"""
        query = """
            SELECT u.* FROM users u
            JOIN room_members rm ON u.user_id = rm.user_id
            WHERE rm.room_id = %s AND rm.is_participating = TRUE
            ORDER BY rm.joined_at
        """
        return self.execute(query, (room_id,), fetch=True) or []

    def get_room_member_count(self, room_id: int) -> int:
        """Get count of room members"""
        query = "SELECT COUNT(*) as count FROM room_members WHERE room_id = %s"
        result = self.execute(query, (room_id,), fetch=True)
        return result[0]['count'] if result else 0

    def get_participant_count(self, room_id: int) -> int:
        """Get count of participating members"""
        query = """
            SELECT COUNT(*) as count FROM room_members
            WHERE room_id = %s AND is_participating = TRUE
        """
        result = self.execute(query, (room_id,), fetch=True)
        return result[0]['count'] if result else 0

    def is_user_in_room(self, room_id: int, user_id: int) -> bool:
        """Check if user is member of room"""
        query = "SELECT 1 FROM room_members WHERE room_id = %s AND user_id = %s"
        result = self.execute(query, (room_id, user_id), fetch=True)
        return bool(result)

    def set_participation(self, room_id: int, user_id: int, is_participating: bool):
        """Set participation status for a user in a room"""
        query = """
            UPDATE room_members
            SET is_participating = %s
            WHERE room_id = %s AND user_id = %s
        """
        self.execute(query, (is_participating, room_id, user_id))

    def remove_member_from_room(self, room_id: int, user_id: int):
        """Remove user from room"""
        # Delete wishlist items
        query = "DELETE FROM wishlist_items WHERE room_id = %s AND user_id = %s"
        self.execute(query, (room_id, user_id))
        
        # Delete assignments if any
        query = """
            DELETE FROM assignments
            WHERE room_id = %s AND (giver_id = %s OR receiver_id = %s)
        """
        self.execute(query, (room_id, user_id, user_id))
        
        # Remove from room
        query = "DELETE FROM room_members WHERE room_id = %s AND user_id = %s"
        self.execute(query, (room_id, user_id))

    # Assignment operations
    def create_assignment(self, room_id: int, giver_id: int, receiver_id: int):
        """Create Secret Santa assignment"""
        query = """
            INSERT INTO assignments (room_id, giver_id, receiver_id)
            VALUES (%s, %s, %s)
        """
        self.execute(query, (room_id, giver_id, receiver_id))

    def get_assignment(self, room_id: int, giver_id: int) -> Optional[Dict[str, Any]]:
        """Get assignment for a giver in a room"""
        query = """
            SELECT a.*, u.user_id, u.username, u.first_name, u.last_name
            FROM assignments a
            JOIN users u ON a.receiver_id = u.user_id
            WHERE a.room_id = %s AND a.giver_id = %s
        """
        result = self.execute(query, (room_id, giver_id), fetch=True)
        return result[0] if result else None

    def get_room_assignments(self, room_id: int) -> List[Dict[str, Any]]:
        """Get all assignments for a room"""
        query = "SELECT * FROM assignments WHERE room_id = %s"
        return self.execute(query, (room_id,), fetch=True) or []

    def get_room_assignments_with_users(self, room_id: int) -> List[Dict[str, Any]]:
        """Get all assignments for a room with giver and receiver user info"""
        query = """
            SELECT 
                a.room_id,
                a.giver_id,
                a.receiver_id,
                giver.user_id as giver_user_id,
                giver.username as giver_username,
                giver.first_name as giver_first_name,
                giver.last_name as giver_last_name,
                receiver.user_id as receiver_user_id,
                receiver.username as receiver_username,
                receiver.first_name as receiver_first_name,
                receiver.last_name as receiver_last_name
            FROM assignments a
            JOIN users giver ON a.giver_id = giver.user_id
            JOIN users receiver ON a.receiver_id = receiver.user_id
            WHERE a.room_id = %s
            ORDER BY giver.first_name, giver.last_name
        """
        return self.execute(query, (room_id,), fetch=True) or []

    def delete_room_assignments(self, room_id: int):
        """Delete all assignments for a room"""
        query = "DELETE FROM assignments WHERE room_id = %s"
        self.execute(query, (room_id,))

    # Wishlist operations
    def add_wishlist_item(self, room_id: int, user_id: int, item_name: str, item_url: str = None) -> int:
        """Add item to user's wishlist for a room"""
        query = """
            INSERT INTO wishlist_items (room_id, user_id, item_name, item_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute(query, (room_id, user_id, item_name, item_url), fetch=True)
        return result[0]['id'] if result else None

    def get_wishlist_items(self, room_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all wishlist items for a user in a room"""
        query = """
            SELECT * FROM wishlist_items
            WHERE room_id = %s AND user_id = %s
            ORDER BY created_at ASC
        """
        return self.execute(query, (room_id, user_id), fetch=True) or []

    def get_wishlist_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get wishlist item by ID"""
        query = "SELECT * FROM wishlist_items WHERE id = %s"
        result = self.execute(query, (item_id,), fetch=True)
        return result[0] if result else None

    def update_wishlist_item(self, item_id: int, item_name: str = None, item_url: str = None):
        """Update wishlist item"""
        updates = []
        params = []
        
        if item_name is not None:
            updates.append("item_name = %s")
            params.append(item_name)
        if item_url is not None:
            updates.append("item_url = %s")
            params.append(item_url)
        
        if not updates:
            return
        
        params.append(item_id)
        query = f"UPDATE wishlist_items SET {', '.join(updates)} WHERE id = %s"
        self.execute(query, tuple(params))

    def delete_wishlist_item(self, item_id: int):
        """Delete wishlist item"""
        query = "DELETE FROM wishlist_items WHERE id = %s"
        self.execute(query, (item_id,))

    def delete_user_wishlist(self, room_id: int, user_id: int):
        """Delete all wishlist items for a user in a room"""
        query = "DELETE FROM wishlist_items WHERE room_id = %s AND user_id = %s"
        self.execute(query, (room_id, user_id))
