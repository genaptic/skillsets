-- PostgreSQL 18 read-only schema-review examples.
-- Run only after reviewing scope, permissions, provider behavior, and collection cost.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '2s';

SELECT current_database() AS database_name,
       current_user AS session_user,
       current_setting('server_version') AS server_version,
       current_setting('search_path') AS search_path;

SELECT n.nspname AS schema_name,
       pg_get_userbyid(n.nspowner) AS owner,
       n.nspacl
FROM pg_namespace AS n
WHERE n.nspname !~ '^pg_toast'
ORDER BY n.nspname;

SELECT c.oid::regclass AS object_name,
       c.relkind,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity,
       c.relforcerowsecurity,
       c.relpersistence
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname !~ '^pg_toast'
ORDER BY c.oid::regclass::text;

SELECT con.oid::regclass AS constraint_oid,
       con.conrelid::regclass AS table_name,
       con.conname,
       con.contype,
       con.convalidated,
       con.condeferrable,
       con.condeferred,
       pg_get_constraintdef(con.oid, true) AS definition
FROM pg_constraint AS con
JOIN pg_class AS c ON c.oid = con.conrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY con.conrelid::regclass::text, con.conname;

SELECT i.indrelid::regclass AS table_name,
       i.indexrelid::regclass AS index_name,
       i.indisunique,
       i.indisprimary,
       i.indisvalid,
       i.indisready,
       pg_get_indexdef(i.indexrelid) AS definition
FROM pg_index AS i
JOIN pg_class AS c ON c.oid = i.indrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY i.indrelid::regclass::text, i.indexrelid::regclass::text;

SELECT p.schemaname,
       p.tablename,
       p.policyname,
       p.permissive,
       p.roles,
       p.cmd,
       p.qual,
       p.with_check
FROM pg_policies AS p
ORDER BY p.schemaname, p.tablename, p.policyname;

ROLLBACK;
