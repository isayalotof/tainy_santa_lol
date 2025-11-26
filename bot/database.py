import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.dsn)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Execute SQL query"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                self.conn.commit()
                if fetch:
                    return [dict(row) for row in cur.fetchall()]
                return None
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Database error: {e}")
            raise

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

    def update_user_bio(self, user_id: int, bio: str):
        """Update user bio"""
        query = """
            UPDATE users
            SET bio = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        self.execute(query, (bio, user_id))

    def update_user_photo(self, user_id: int, photo_file_id: str):
        """Update user photo"""
        query = """
            UPDATE users
            SET photo_file_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        self.execute(query, (photo_file_id, user_id))

    def update_user_wishlist(self, user_id: int, wishlist: str):
        """Update user wishlist"""
        query = """
            UPDATE users
            SET wishlist = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        self.execute(query, (wishlist, user_id))

    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile with all info"""
        query = """
            SELECT user_id, username, first_name, last_name, bio, photo_file_id, wishlist
            FROM users WHERE user_id = %s
        """
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
        """Get all members of a room"""
        query = """
            SELECT u.* FROM users u
            JOIN room_members rm ON u.user_id = rm.user_id
            WHERE rm.room_id = %s
            ORDER BY rm.joined_at
        """
        return self.execute(query, (room_id,), fetch=True) or []

    def get_room_member_count(self, room_id: int) -> int:
        """Get count of room members"""
        query = "SELECT COUNT(*) as count FROM room_members WHERE room_id = %s"
        result = self.execute(query, (room_id,), fetch=True)
        return result[0]['count'] if result else 0

    def is_user_in_room(self, room_id: int, user_id: int) -> bool:
        """Check if user is member of room"""
        query = "SELECT 1 FROM room_members WHERE room_id = %s AND user_id = %s"
        result = self.execute(query, (room_id, user_id), fetch=True)
        return bool(result)

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

    def delete_room_assignments(self, room_id: int):
        """Delete all assignments for a room"""
        query = "DELETE FROM assignments WHERE room_id = %s"
        self.execute(query, (room_id,))
