-- Add city column to listings for multi-city support
ALTER TABLE listings ADD COLUMN IF NOT EXISTS city TEXT;

-- Backfill existing listings as milan
UPDATE listings SET city = 'milan' WHERE city IS NULL;
