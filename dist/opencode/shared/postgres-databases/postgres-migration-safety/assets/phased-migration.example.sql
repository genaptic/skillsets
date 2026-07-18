-- Illustrative phased SQL fragments. They are not one transaction or a ready-to-run file.
-- Confirm PostgreSQL version, table size, lock behavior, runner semantics, and application
-- compatibility. Use explicit operational approval for every production step.

-- Phase A: short-lock expansion.
SET lock_timeout = '2s';
SET statement_timeout = '30s';

ALTER TABLE app.invoice
    ADD COLUMN settlement_reference text;

-- Application is deployed to populate settlement_reference for new/changed rows.
-- Historical rows are backfilled by a bounded, restartable external worker.

-- Phase B: preflight must show zero null rows before adding/validating the proof.
SELECT count(*) AS missing_count
FROM app.invoice
WHERE settlement_reference IS NULL;

ALTER TABLE app.invoice
    ADD CONSTRAINT invoice_settlement_reference_present_chk
    CHECK (settlement_reference IS NOT NULL) NOT VALID;

ALTER TABLE app.invoice
    VALIDATE CONSTRAINT invoice_settlement_reference_present_chk;

-- Confirm target-version lock and proof behavior before this step.
ALTER TABLE app.invoice
    ALTER COLUMN settlement_reference SET NOT NULL;

ALTER TABLE app.invoice
    DROP CONSTRAINT invoice_settlement_reference_present_chk;

-- A concurrent index build must be a separate non-transaction-block phase.
CREATE INDEX CONCURRENTLY invoice_unsettled_due_idx
    ON app.invoice (tenant_id, due_at)
    INCLUDE (total_amount)
    WHERE settled_at IS NULL;

-- Verify pg_index.indisvalid/indisready, plans, write cost, and replication lag.
