-- Example: members register for events (many-to-many).
-- Each member may register once per event; fee_paid describes that registration.
-- Run where these table names are unused, or replace COMMIT with ROLLBACK
-- for a trial run that leaves no tables behind.

BEGIN;

CREATE TABLE example_member (
    member_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_name text NOT NULL CHECK (btrim(member_name) <> ''),
    email text NOT NULL UNIQUE
);

CREATE TABLE example_event (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL CHECK (btrim(title) <> ''),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    CONSTRAINT example_event_time_order CHECK (ends_at > starts_at)
);

-- Both referenced tables now exist, so the foreign keys can be declared.
CREATE TABLE example_registration (
    member_id bigint REFERENCES example_member(member_id),
    event_id bigint REFERENCES example_event(event_id),
    registered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fee_paid numeric(10, 2) NOT NULL CHECK (fee_paid >= 0),
    PRIMARY KEY (member_id, event_id)
);

-- The composite primary key makes the pair unique and both columns NOT NULL.

COMMIT;
