-- Runs only when the Postgres data directory is initialised for the first time.
-- Existing volumes need `make create-test-db`.
SELECT 'CREATE DATABASE enrollio_test OWNER ' || current_user
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'enrollio_test')\gexec
