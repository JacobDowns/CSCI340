-- Setup for "From rows to pages and indexes" (PostgreSQL).
-- Run once in the schema you use for coursework.
-- This regular table remains available after you disconnect.
-- In psql, load this file from an interactive session with:
--   \i storage-demo-setup.sql
-- In a graphical SQL editor, open and execute the file.

CREATE TABLE storage_demo (
    event_id integer PRIMARY KEY,
    player_id integer NOT NULL,
    score integer NOT NULL,
    note text
);

-- 100,000 events, with ten events for each of 10,000 players.
-- Notes vary in length, and every tenth event has a null note.
INSERT INTO storage_demo (event_id, player_id, score, note)
SELECT n,
       1 + (n % 10000),
       n % 100,
       CASE WHEN n % 10 = 0 THEN NULL
            ELSE 'event ' || n END
FROM generate_series(1, 100000) AS generated(n);

-- Gather planner statistics without changing the placement of the rows.
ANALYZE storage_demo;
SHOW block_size;

-- The primary key supplies an index on event_id. Leave player_id unindexed
-- until the lecture asks you to create storage_demo_player_idx.
