\set ON_ERROR_STOP on

CREATE ROLE copilot_migrator LOGIN PASSWORD 'migrator-local-only';
CREATE ROLE copilot_runtime LOGIN PASSWORD 'runtime-local-only'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

ALTER DATABASE jobtracking OWNER TO copilot_migrator;
GRANT CONNECT ON DATABASE jobtracking TO copilot_runtime;

\connect jobtracking
ALTER SCHEMA public OWNER TO copilot_migrator;
GRANT USAGE ON SCHEMA public TO copilot_runtime;
