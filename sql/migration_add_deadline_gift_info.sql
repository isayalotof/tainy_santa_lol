-- Migration: Add deadline, gift_time, gift_location columns to rooms table
-- Run this if you have an existing database

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS deadline VARCHAR(255);
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS gift_time VARCHAR(255);
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS gift_location VARCHAR(255);

