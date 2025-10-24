-- Migration: Update karma_events delta constraint
-- Allow admin karma adjustments with wider range (-10000 to +10000)
-- instead of reaction-only values (-1, 1)

-- Drop old constraint
ALTER TABLE karma_events DROP CONSTRAINT IF EXISTS karma_events_delta_check;

-- Add new constraint with wider range
ALTER TABLE karma_events ADD CONSTRAINT karma_events_delta_check
  CHECK (delta BETWEEN -10000 AND 10000);

COMMENT ON CONSTRAINT karma_events_delta_check ON karma_events IS
  'Allows karma delta from -10000 to +10000 for admin adjustments';
