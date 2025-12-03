-- Migration: Add is_participating column to room_members table
-- Run this if you have an existing database

ALTER TABLE room_members ADD COLUMN IF NOT EXISTS is_participating BOOLEAN DEFAULT TRUE;

-- Set all existing members as participating
UPDATE room_members SET is_participating = TRUE WHERE is_participating IS NULL;

