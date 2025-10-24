-- Migration: Remove marriages system
-- Date: 2025-10-24
-- Description: Drop marriages table and related constraints

-- Drop marriages tables
DROP TABLE IF EXISTS marriages CASCADE;
DROP TABLE IF EXISTS marriage_proposals CASCADE;
