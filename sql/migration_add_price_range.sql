-- Migration: Add price_range column to rooms table
-- Run this if you have an existing database

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS price_range VARCHAR(255);

