import Foundation

struct SchemaInitializer {
    let database: any BookDatabase

    func inspect() async throws -> [String] {
        switch database.kind {
        case .sqlite:
            let rows = try await database.query(SQLStatement("select name from sqlite_master where type = 'table' order by name"))
            return rows.map { $0.string("name") }
        case .postgres:
            let rows = try await database.query(SQLStatement("select tablename as name from pg_tables where schemaname = 'public' order by tablename"))
            return rows.map { $0.string("name") }
        }
    }

    func ensureSchema() async throws {
        let tables = try await inspect()
        let needsBaseSchema = !tables.contains("projects") || !tables.contains("chapter_drafts")
        try await database.transaction {
            if needsBaseSchema {
                for statement in schemaStatements(for: database.kind) {
                    try await database.execute(SQLStatement(statement))
                }
            }
            for statement in appSchemaStatements(for: database.kind) {
                try await database.execute(SQLStatement(statement))
            }
        }
    }

    private func schemaStatements(for kind: DatabaseKind) -> [String] {
        switch kind {
        case .sqlite:
            sqliteSchema
        case .postgres:
            postgresSchema
        }
    }

    private func appSchemaStatements(for kind: DatabaseKind) -> [String] {
        switch kind {
        case .sqlite:
            sqliteAppSchema
        case .postgres:
            postgresAppSchema
        }
    }

    private var sqliteSchema: [String] {
        [
            "create table if not exists alembic_version (version_num varchar(32) not null primary key)",
            """
            create table if not exists projects (
              id char(32) not null primary key,
              name varchar(255) not null,
              slug varchar(160) not null unique,
              description text,
              status varchar(64) not null,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            """
            create table if not exists book_volumes (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              title varchar(255) not null,
              subtitle varchar(255),
              slug varchar(160) not null,
              trim_size varchar(64),
              page_size varchar(64),
              binding_type varchar(120),
              printer_target varchar(160),
              status varchar(64) not null,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null,
              unique(project_id, slug)
            )
            """,
            """
            create table if not exists chapter_briefs (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              volume_id char(32) references book_volumes(id) on delete set null,
              title varchar(255) not null,
              subtitle varchar(255),
              slug varchar(160) not null,
              sequence_order integer,
              status varchar(64) not null,
              intended_page_count integer,
              target_word_count integer,
              situation text,
              "constraint" text,
              build text,
              pattern text,
              oahu_layer text,
              field_note text,
              next_build text,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null,
              unique(volume_id, slug)
            )
            """,
            """
            create table if not exists agent_runs (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              run_type varchar(80) not null,
              agent_name varchar(160) not null,
              tool_name varchar(160),
              prompt text,
              input_refs json not null,
              output_refs json not null,
              status varchar(64) not null,
              error_message text,
              started_at datetime,
              completed_at datetime,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            """
            create table if not exists chapter_drafts (
              id char(32) not null primary key,
              chapter_brief_id char(32) not null references chapter_briefs(id) on delete cascade,
              agent_run_id char(32) references agent_runs(id) on delete set null,
              version_number integer not null,
              body_format varchar(40) not null,
              body text not null,
              model_provider varchar(120),
              model_name varchar(160),
              model_metadata json not null,
              generation_prompt_ref text,
              status varchar(64) not null,
              editor_notes text,
              created_at datetime not null,
              updated_at datetime not null,
              unique(chapter_brief_id, version_number)
            )
            """,
            """
            create table if not exists source_materials (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              source_type varchar(64) not null,
              title varchar(255),
              location text,
              uri text,
              external_id varchar(255),
              provenance json not null,
              metadata json not null,
              content_hash varchar(128),
              status varchar(64) not null,
              occurred_at datetime,
              captured_at datetime,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            """
            create table if not exists source_chunks (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              source_id char(32) not null references source_materials(id) on delete cascade,
              chunk_type varchar(64) not null,
              chunk_index integer not null,
              title varchar(255),
              text text not null,
              text_hash varchar(128) not null,
              locator_type varchar(64),
              locator_data json not null,
              status varchar(64) not null,
              ocr_engine varchar(160),
              ocr_confidence float,
              uncertainty_notes text,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null,
              unique(source_id, chunk_index)
            )
            """,
            """
            create table if not exists extracted_candidates (
              id char(32) not null primary key,
              project_id char(32) not null,
              extraction_run_id char(32) not null,
              source_id char(32) not null,
              source_chunk_id char(32) not null,
              node_type varchar(64) not null,
              title varchar(255) not null,
              body text not null,
              confidence_score float not null,
              reuse_score float not null,
              evidence_quote text,
              rationale text,
              raw_output json not null,
              status varchar(64) not null,
              promoted_node_id char(32),
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            """
            create table if not exists knowledge_nodes (
              id char(32) not null primary key,
              project_id char(32) not null,
              node_type varchar(64) not null,
              title varchar(255) not null,
              body text not null,
              confidence float not null,
              status varchar(64) not null,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            """
            create table if not exists rendered_outputs (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              volume_id char(32),
              chapter_brief_id char(32),
              output_type varchar(64) not null,
              renderer varchar(120) not null,
              config_path text,
              output_path text not null,
              git_commit_hash varchar(80),
              build_logs text,
              status varchar(64) not null,
              rendered_at datetime,
              metadata json not null,
              created_at datetime not null,
              updated_at datetime not null
            )
            """,
            "insert or ignore into alembic_version(version_num) values ('0002_ingestion_review')"
        ]
    }

    private var postgresSchema: [String] {
        sqliteSchema.map { statement in
            if statement.hasPrefix("insert or ignore into alembic_version") {
                return "insert into alembic_version(version_num) values ('0002_ingestion_review') on conflict do nothing"
            }
            return statement
                .replacingOccurrences(of: "char(32)", with: "uuid")
                .replacingOccurrences(of: "datetime", with: "timestamp with time zone")
                .replacingOccurrences(of: "metadata json", with: "metadata jsonb")
                .replacingOccurrences(of: "provenance json", with: "provenance jsonb")
                .replacingOccurrences(of: "locator_data json", with: "locator_data jsonb")
                .replacingOccurrences(of: "model_metadata json", with: "model_metadata jsonb")
                .replacingOccurrences(of: "input_refs json", with: "input_refs jsonb")
                .replacingOccurrences(of: "output_refs json", with: "output_refs jsonb")
                .replacingOccurrences(of: "raw_output json", with: "raw_output jsonb")
        }
    }

    private var sqliteAppSchema: [String] {
        [
            """
            create table if not exists bookmaker_chapter_messages (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              chapter_brief_id char(32) not null references chapter_briefs(id) on delete cascade,
              role varchar(32) not null,
              text text not null,
              media_refs json not null,
              turn_index integer not null,
              created_at datetime not null,
              metadata json not null
            )
            """,
            """
            create index if not exists bookmaker_chapter_messages_chapter_turn_idx
            on bookmaker_chapter_messages(chapter_brief_id, turn_index, created_at)
            """,
            """
            create table if not exists bookmaker_chapter_brief_versions (
              id char(32) not null primary key,
              project_id char(32) not null references projects(id) on delete cascade,
              chapter_brief_id char(32) not null references chapter_briefs(id) on delete cascade,
              version_number integer not null,
              turn_index integer not null,
              brief_json json not null,
              change_summary text not null,
              model_provider varchar(120),
              model_name varchar(160),
              response_id varchar(255),
              usage_json json not null,
              created_at datetime not null,
              metadata json not null,
              unique(chapter_brief_id, version_number)
            )
            """,
            """
            create index if not exists bookmaker_chapter_brief_versions_chapter_idx
            on bookmaker_chapter_brief_versions(chapter_brief_id, version_number)
            """,
            """
            create table if not exists bookmaker_chapter_brief_state (
              chapter_brief_id char(32) not null primary key references chapter_briefs(id) on delete cascade,
              active_version_id char(32) references bookmaker_chapter_brief_versions(id) on delete set null,
              updated_at datetime not null
            )
            """
        ]
    }

    private var postgresAppSchema: [String] {
        [
            """
            create table if not exists bookmaker_chapter_messages (
              id uuid not null primary key,
              project_id uuid not null references projects(id) on delete cascade,
              chapter_brief_id uuid not null references chapter_briefs(id) on delete cascade,
              role varchar(32) not null,
              text text not null,
              media_refs jsonb not null,
              turn_index integer not null,
              created_at timestamp with time zone not null,
              metadata jsonb not null
            )
            """,
            """
            create index if not exists bookmaker_chapter_messages_chapter_turn_idx
            on bookmaker_chapter_messages(chapter_brief_id, turn_index, created_at)
            """,
            """
            create table if not exists bookmaker_chapter_brief_versions (
              id uuid not null primary key,
              project_id uuid not null references projects(id) on delete cascade,
              chapter_brief_id uuid not null references chapter_briefs(id) on delete cascade,
              version_number integer not null,
              turn_index integer not null,
              brief_json jsonb not null,
              change_summary text not null,
              model_provider varchar(120),
              model_name varchar(160),
              response_id varchar(255),
              usage_json jsonb not null,
              created_at timestamp with time zone not null,
              metadata jsonb not null,
              unique(chapter_brief_id, version_number)
            )
            """,
            """
            create index if not exists bookmaker_chapter_brief_versions_chapter_idx
            on bookmaker_chapter_brief_versions(chapter_brief_id, version_number)
            """,
            """
            create table if not exists bookmaker_chapter_brief_state (
              chapter_brief_id uuid not null primary key references chapter_briefs(id) on delete cascade,
              active_version_id uuid references bookmaker_chapter_brief_versions(id) on delete set null,
              updated_at timestamp with time zone not null
            )
            """
        ]
    }
}
