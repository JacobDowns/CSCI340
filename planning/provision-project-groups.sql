-- CSCI 340 Autumn 2026 final-project group accounts.
-- Run locally on the database server as the PostgreSQL OS administrator:
--   sudo -u postgres psql -d csci340 -f planning/provision-project-groups.sql
--
-- Each project group receives one shared login and an isolated schema.
-- Set passwords afterward from the untracked instructor credential file.

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    group_login text;
BEGIN
    FOREACH group_login IN ARRAY ARRAY[
        'project_g01', 'project_g02', 'project_g03', 'project_g04',
        'project_g05', 'project_g06', 'project_g07', 'project_g08'
    ]
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = group_login) THEN
            EXECUTE format(
                'CREATE ROLE %I LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 8',
                group_login
            );
        ELSE
            EXECUTE format(
                'ALTER ROLE %I LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 8',
                group_login
            );
        END IF;

        -- Inherit CONNECT and read-only public-schema privileges.
        EXECUTE format('GRANT course_students TO %I', group_login);

        IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = group_login) THEN
            EXECUTE format('CREATE SCHEMA %I AUTHORIZATION %I', group_login, group_login);
        ELSE
            EXECUTE format('ALTER SCHEMA %I OWNER TO %I', group_login, group_login);
        END IF;

        -- Only the group role and database administrators may use this schema.
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', group_login);
        EXECUTE format(
            'ALTER ROLE %I IN DATABASE csci340 SET search_path TO %I, public',
            group_login,
            group_login
        );
    END LOOP;
END
$$;

COMMIT;
