-- Run ONCE as the owner of the NEW, dedicated WORKBASE database.
-- Do not run in the original Zakazkovnik database.
-- Set the role password separately in your database console; never commit it.
CREATE ROLE pc_workbase_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO pc_workbase_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, pc_workbase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pc_workbase_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, pc_workbase_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, pc_workbase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pc_workbase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC;
ALTER ROLE pc_workbase_reader SET default_transaction_read_only = on;
DO $$ BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO pc_workbase_reader', current_database());
END $$;
-- Then, in a private console only:
-- ALTER ROLE pc_workbase_reader PASSWORD '<your-new-random-password>';
