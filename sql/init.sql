-- Database initialization script for Secret Santa Bot

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rooms table
CREATE TABLE IF NOT EXISTS rooms (
    room_id SERIAL PRIMARY KEY,
    room_name VARCHAR(255) NOT NULL,
    admin_id BIGINT NOT NULL REFERENCES users(user_id),
    invite_code VARCHAR(50) UNIQUE NOT NULL,
    is_drawn BOOLEAN DEFAULT FALSE,
    price_range VARCHAR(255),
    deadline VARCHAR(255),
    gift_time VARCHAR(255),
    gift_location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    drawn_at TIMESTAMP
);

-- Room members table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS room_members (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    is_participating BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(room_id, user_id)
);

-- Secret Santa assignments table
CREATE TABLE IF NOT EXISTS assignments (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    giver_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    receiver_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(room_id, giver_id)
);

-- Wishlist items table
CREATE TABLE IF NOT EXISTS wishlist_items (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    item_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_room_members_room ON room_members(room_id);
CREATE INDEX IF NOT EXISTS idx_room_members_user ON room_members(user_id);
CREATE INDEX IF NOT EXISTS idx_room_members_participating ON room_members(room_id, is_participating) WHERE is_participating = TRUE;
CREATE INDEX IF NOT EXISTS idx_assignments_room ON assignments(room_id);
CREATE INDEX IF NOT EXISTS idx_assignments_giver ON assignments(giver_id);
CREATE INDEX IF NOT EXISTS idx_assignments_receiver ON assignments(receiver_id);
CREATE INDEX IF NOT EXISTS idx_assignments_room_giver ON assignments(room_id, giver_id);
CREATE INDEX IF NOT EXISTS idx_rooms_invite_code ON rooms(invite_code);
CREATE INDEX IF NOT EXISTS idx_rooms_admin ON rooms(admin_id);
CREATE INDEX IF NOT EXISTS idx_wishlist_room_user ON wishlist_items(room_id, user_id);
CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist_items(user_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL;

-- Security settings
-- Limit connections per user
ALTER ROLE postgres WITH CONNECTION LIMIT 50;

-- Enable logging for security monitoring
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_authentication_failures = 'on';
ALTER SYSTEM SET log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ';

-- Set authentication timeout
ALTER SYSTEM SET authentication_timeout = '10s';
