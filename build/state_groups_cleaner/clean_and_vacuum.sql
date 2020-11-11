CREATE TEMPORARY TABLE unreffed(id BIGINT PRIMARY KEY);
COPY unreffed FROM '/var/lib/postgresql/data/sgs.csv' WITH (FORMAT 'csv');  

BEGIN;
DELETE FROM state_groups_state WHERE state_group IN (SELECT id FROM unreffed);
DELETE FROM state_group_edges WHERE state_group IN (SELECT id FROM unreffed);
DELETE FROM state_groups WHERE id IN (SELECT id FROM unreffed);
COMMIT;

VACUUM (FULL, VERBOSE, ANALYZE) state_groups_state;
