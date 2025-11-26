-- Migration: Add profile fields to users table
-- Date: 2025-11-26

-- Add new columns to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS bio TEXT,
ADD COLUMN IF NOT EXISTS photo_file_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS wishlist TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Update existing rows to have updated_at same as created_at
UPDATE users
SET updated_at = created_at
WHERE updated_at IS NULL;
