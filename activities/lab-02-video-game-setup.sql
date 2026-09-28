-- Lab 2 and the joins lecture: reset the video game practice tables.
-- Run in your personal schema. Existing rows in these tables are removed.
-- Drop related tables from earlier lectures first, if they exist.
-- Recreating the tables restarts generated IDs to match the handout.
\set ON_ERROR_STOP on

DROP TABLE IF EXISTS save_file;
DROP TABLE IF EXISTS play_session;
DROP TABLE IF EXISTS player_game_library;
DROP TABLE IF EXISTS video_game;
DROP TABLE IF EXISTS player_account;

CREATE TABLE video_game (
    game_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL,
    studio_name text NOT NULL,
    released_on date,
    is_available boolean NOT NULL DEFAULT true
);

CREATE TABLE player_account (
    player_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL UNIQUE,
    account_status text NOT NULL
        CHECK (account_status IN ('active', 'suspended', 'closed'))
);

CREATE TABLE save_file (
    save_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id bigint NOT NULL REFERENCES player_account(player_id),
    game_id bigint NOT NULL REFERENCES video_game(game_id),
    saved_at timestamp with time zone NOT NULL,
    completion_percent numeric(5, 2)
        CHECK (completion_percent BETWEEN 0 AND 100),
    slot_label text
);

INSERT INTO video_game (title, studio_name, released_on)
VALUES
    ('Starfall Cartographers', 'Northline Studio', DATE '2024-10-04'),
    ('Mosslight', 'Juniper Byte', NULL),
    ('Circuit Garden', 'Northline Studio', DATE '2026-02-12');

INSERT INTO player_account (username, account_status)
VALUES ('pixel_fox', 'active'), ('moss_runner', 'active'), ('star_mapper', 'active');

-- In this fresh setup, generated player and game IDs are 1, 2, and 3.
INSERT INTO save_file
    (player_id, game_id, saved_at, completion_percent, slot_label)
VALUES
    (1, 1, '2026-09-24 09:00-06', 25.00, NULL),
    (1, 1, '2026-09-24 10:00-06', 50.00, NULL),
    (2, 1, '2026-09-24 09:00-06', 49.99, 'favorite'),
    (1, 1, '2026-09-24 11:00-06', 75.00, NULL),
    (3, 2, '2026-09-24 09:00-06', 80.00, NULL),
    (3, 2, '2026-09-24 10:00-06', 100.00, 'favorite'),
    (2, 3, '2026-09-24 10:00-06', NULL, 'new run'),
    (2, 3, '2026-09-24 11:00-06', 80.00, NULL);

SELECT * FROM video_game ORDER BY game_id;
SELECT * FROM player_account ORDER BY player_id;
SELECT * FROM save_file ORDER BY save_id;
