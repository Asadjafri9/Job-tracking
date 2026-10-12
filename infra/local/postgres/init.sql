\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'copilot_migrator') THEN
    CREATE ROLE copilot_migrator LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'copilot_runtime') THEN
    CREATE ROLE copilot_runtime LOGIN;
  END IF;
END
$$;

ALTER ROLE copilot_migrator LOGIN PASSWORD 'migrator-local-only'
  NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS;
ALTER ROLE copilot_runtime LOGIN PASSWORD 'runtime-local-only'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

ALTER DATABASE jobtracking OWNER TO copilot_migrator;
GRANT CONNECT ON DATABASE jobtracking TO copilot_runtime;

\connect jobtracking
ALTER SCHEMA public OWNER TO copilot_migrator;
GRANT USAGE ON SCHEMA public TO copilot_runtime;
