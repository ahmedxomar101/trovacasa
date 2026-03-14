-- Add gallery_fetched_at column to track which listings have full image galleries
ALTER TABLE listings ADD COLUMN IF NOT EXISTS gallery_fetched_at TIMESTAMPTZ;
