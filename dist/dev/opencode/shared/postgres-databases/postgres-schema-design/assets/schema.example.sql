-- Illustrative PostgreSQL 18 DDL. Review names, privileges, RLS identity,
-- extension availability, and migration behavior before use.

CREATE SCHEMA IF NOT EXISTS app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE TABLE app.tenant (
    tenant_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_key text NOT NULL,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tenant_key_format_chk
        CHECK (tenant_key ~ '^[a-z0-9][a-z0-9-]{2,62}$'),
    CONSTRAINT tenant_tenant_key_uq UNIQUE (tenant_key)
);

CREATE TABLE app.project (
    project_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id bigint NOT NULL,
    project_key text NOT NULL,
    display_name text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at timestamptz,
    CONSTRAINT project_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES app.tenant (tenant_id)
        ON DELETE RESTRICT,
    CONSTRAINT project_status_chk
        CHECK (status IN ('active', 'archived')),
    CONSTRAINT project_archive_state_chk
        CHECK (
            (status = 'active' AND archived_at IS NULL)
            OR (status = 'archived' AND archived_at IS NOT NULL)
        ),
    CONSTRAINT project_tenant_key_uq
        UNIQUE (tenant_id, project_key),
    CONSTRAINT project_tenant_project_uq
        UNIQUE (tenant_id, project_id)
);

CREATE TABLE app.project_member (
    tenant_id bigint NOT NULL,
    project_id bigint NOT NULL,
    user_id bigint NOT NULL,
    member_role text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT project_member_pk
        PRIMARY KEY (tenant_id, project_id, user_id),
    CONSTRAINT project_member_project_fk
        FOREIGN KEY (tenant_id, project_id)
        REFERENCES app.project (tenant_id, project_id)
        ON DELETE CASCADE,
    CONSTRAINT project_member_role_chk
        CHECK (member_role IN ('owner', 'editor', 'viewer'))
);

-- Referencing-side indexes are workload decisions; this one supports tenant/project joins
-- and parent-row lifecycle checks that begin with tenant_id.
CREATE INDEX project_member_tenant_user_idx
    ON app.project_member (tenant_id, user_id);

ALTER TABLE app.project ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.project FORCE ROW LEVEL SECURITY;

-- The application must set app.current_tenant to a validated identifier at transaction
-- start and fail closed when context is absent. Test owner/bypass behavior explicitly.
CREATE POLICY project_tenant_policy ON app.project
    USING (tenant_id = current_setting('app.current_tenant', true)::bigint)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::bigint);
