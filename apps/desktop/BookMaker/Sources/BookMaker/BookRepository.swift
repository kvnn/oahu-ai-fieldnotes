import Foundation

actor BookRepository {
    let database: any BookDatabase

    init(database: any BookDatabase) {
        self.database = database
    }

    func listProjects() async throws -> [ProjectRecord] {
        let rows = try await database.query(SQLStatement("""
            select id, name, slug, coalesce(description, '') as description, status, metadata
            from projects
            order by updated_at desc, name asc
            """))
        return try rows.map(project(from:))
    }

    func volumes(projectId: UUID) async throws -> [VolumeRecord] {
        let rows = try await database.query(SQLStatement("""
            select id, project_id, title, coalesce(subtitle, '') as subtitle, slug, status, metadata
            from book_volumes
            where project_id = ?
            order by created_at asc
            """, [.uuid(projectId)]))
        return try rows.map(volume(from:))
    }

    func createProject(name: String, template: BookTemplate) async throws -> ProjectRecord {
        let cleanName = name.nilIfBlank ?? "Untitled Book"
        let projectId = UUID()
        let volumeId = UUID()
        let now = Date()
        let slug = try await uniqueProjectSlug(stableSlug(cleanName, fallback: "book"))
        let metadata = BookMakerMetadata(
            templateId: template.id,
            writingSystem: template.writingSystem,
            voiceRules: template.voiceRules,
            chapterForms: template.chapterForms,
            visualCadence: template.visualCadence,
            rubric: template.rubric
        )
        let metadataData = try jsonData(["bookmaker": metadata])
        let emptyJSON = Data("{}".utf8)

        try await database.transaction {
            try await database.execute(SQLStatement("""
                insert into projects (id, name, slug, description, status, metadata, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    .uuid(projectId),
                    .string(cleanName),
                    .string(slug),
                    .string(template.description),
                    .string("active"),
                    .json(metadataData),
                    .date(now),
                    .date(now)
                ]))
            try await database.execute(SQLStatement("""
                insert into book_volumes (id, project_id, title, subtitle, slug, trim_size, page_size, binding_type, printer_target, status, metadata, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    .uuid(volumeId),
                    .uuid(projectId),
                    .string(template.defaultVolumeTitle.nilIfBlank ?? cleanName),
                    .string(template.defaultVolumeSubtitle),
                    .string("vol-1"),
                    .string("5.5\" x 8.5\""),
                    .string("5.5\" x 8.5\""),
                    .string("perfect_bound"),
                    .string("Vivliostyle print PDF"),
                    .string("drafting"),
                    .json(metadataData),
                    .date(now),
                    .date(now)
                ]))

            for (index, chapter) in template.starterChapters.enumerated() {
                let chapterId = UUID()
                let draftId = UUID()
                let chapterMetadata = ChapterMetadata(
                    chapterForm: chapter.form,
                    thesis: chapter.thesis,
                    sourceCluster: [],
                    pageRhythm: [],
                    visualSlots: [],
                    keyClaims: [],
                    evaluationNotes: ""
                )
                try await database.execute(SQLStatement("""
                    insert into chapter_briefs (
                      id, project_id, volume_id, title, subtitle, slug, sequence_order, status,
                      intended_page_count, target_word_count, situation, "constraint", build,
                      pattern, oahu_layer, field_note, next_build, metadata, created_at, updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        .uuid(chapterId),
                        .uuid(projectId),
                        .uuid(volumeId),
                        .string(chapter.title),
                        .string(chapter.subtitle),
                        .string(try await uniqueChapterSlug(stableSlug(chapter.title, fallback: "chapter"), volumeId: volumeId)),
                        .int(index + 1),
                        .string(ChapterStatus.draft.rawValue),
                        .int(8),
                        .int(2200),
                        .string(""),
                        .string(""),
                        .string(""),
                        .string(""),
                        .string(""),
                        .string(chapter.thesis),
                        .string(""),
                        .json(try jsonData(chapterMetadata)),
                        .date(now),
                        .date(now)
                    ]))
                try await database.execute(SQLStatement("""
                    insert into chapter_drafts (
                      id, chapter_brief_id, agent_run_id, version_number, body_format, body,
                      model_provider, model_name, model_metadata, generation_prompt_ref, status,
                      editor_notes, created_at, updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        .uuid(draftId),
                        .uuid(chapterId),
                        .null,
                        .int(1),
                        .string("markdown"),
                        .string(chapter.body),
                        .null,
                        .null,
                        .json(emptyJSON),
                        .string("bookmaker.template.\(template.id)"),
                        .string("draft"),
                        .string("Created from BookMaker template."),
                        .date(now),
                        .date(now)
                    ]))
            }
        }
        return ProjectRecord(
            id: projectId,
            name: cleanName,
            slug: slug,
            description: template.description,
            status: "active",
            metadata: metadata
        )
    }

    func chapters(projectId: UUID, volumeId: UUID?) async throws -> [ChapterRecord] {
        let rows: [SQLRow]
        if let volumeId {
            rows = try await database.query(SQLStatement("""
                select * from chapter_briefs
                where project_id = ? and volume_id = ?
                order by coalesce(sequence_order, 9999), created_at asc
                """, [.uuid(projectId), .uuid(volumeId)]))
        } else {
            rows = try await database.query(SQLStatement("""
                select * from chapter_briefs
                where project_id = ?
                order by coalesce(sequence_order, 9999), created_at asc
                """, [.uuid(projectId)]))
        }
        return try rows.map(chapter(from:))
    }

    func sourceStats(projectId: UUID) async throws -> SourceStats {
        let sources = try await count("source_materials", where: "project_id = ?", [.uuid(projectId)])
        let ready = try await count("source_chunks", where: "project_id = ? and status = 'ready'", [.uuid(projectId)])
        let blocked = try await count("source_chunks", where: "project_id = ? and status in ('blocked', 'needs_ocr', 'failed')", [.uuid(projectId)])
        let needsReview = try await count("extracted_candidates", where: "project_id = ? and status = 'needs_review'", [.uuid(projectId)])
        let nodes = try await count("knowledge_nodes", where: "project_id = ? and status in ('accepted', 'drafted', 'published')", [.uuid(projectId)])
        return SourceStats(sources: sources, readyChunks: ready, blockedChunks: blocked, needsReview: needsReview, knowledgeNodes: nodes)
    }

    func createChapter(projectId: UUID, volumeId: UUID?, title: String, subtitle: String) async throws -> ChapterRecord {
        let cleanTitle = title.nilIfBlank ?? "Untitled Chapter"
        let nextOrderRows = try await database.query(SQLStatement(
            "select coalesce(max(sequence_order), 0) + 1 as next_order from chapter_briefs where project_id = ?",
            [.uuid(projectId)]
        ))
        let order = nextOrderRows.first?.int("next_order", default: 1) ?? 1
        let chapterId = UUID()
        let slug = try await uniqueChapterSlug(stableSlug(cleanTitle, fallback: "chapter"), volumeId: volumeId)
        let now = Date()
        try await database.execute(SQLStatement("""
            insert into chapter_briefs (
              id, project_id, volume_id, title, subtitle, slug, sequence_order, status,
              intended_page_count, target_word_count, situation, "constraint", build,
              pattern, oahu_layer, field_note, next_build, metadata, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                .uuid(chapterId),
                .uuid(projectId),
                volumeId.map(SQLValue.uuid) ?? .null,
                .string(cleanTitle),
                .string(subtitle),
                .string(slug),
                .int(order),
                .string(ChapterStatus.draft.rawValue),
                .int(8),
                .int(2200),
                .string(""),
                .string(""),
                .string(""),
                .string(""),
                .string(""),
                .string(""),
                .string(""),
                .json(try jsonData(ChapterMetadata.empty)),
                .date(now),
                .date(now)
            ]))
        let row = try await database.query(SQLStatement("select * from chapter_briefs where id = ?", [.uuid(chapterId)])).first
        guard let row else { throw BookMakerError.database("Created chapter could not be loaded.") }
        return try chapter(from: row)
    }

    func updateChapter(_ chapter: ChapterRecord) async throws {
        try await database.execute(SQLStatement("""
            update chapter_briefs
            set title = ?, subtitle = ?, status = ?, intended_page_count = ?, target_word_count = ?,
                situation = ?, "constraint" = ?, build = ?, pattern = ?, oahu_layer = ?,
                field_note = ?, next_build = ?, metadata = ?, updated_at = ?
            where id = ?
            """, [
                .string(chapter.title),
                .string(chapter.subtitle),
                .string(chapter.status.rawValue),
                chapter.intendedPageCount.map(SQLValue.int) ?? .null,
                chapter.targetWordCount.map(SQLValue.int) ?? .null,
                .string(chapter.situation),
                .string(chapter.constraint),
                .string(chapter.build),
                .string(chapter.pattern),
                .string(chapter.oahuLayer),
                .string(chapter.fieldNote),
                .string(chapter.nextBuild),
                .json(try jsonData(chapter.metadata)),
                .date(),
                .uuid(chapter.id)
            ]))
    }

    func reorderChapters(_ chapters: [ChapterRecord]) async throws {
        try await database.transaction {
            for (index, chapter) in chapters.enumerated() {
                try await database.execute(SQLStatement(
                    "update chapter_briefs set sequence_order = ?, updated_at = ? where id = ?",
                    [.int(index + 1), .date(), .uuid(chapter.id)]
                ))
            }
        }
    }

    func draftPayload(chapterId: UUID) async throws -> DraftPayload {
        let draftRows = try await database.query(SQLStatement("""
            select id, version_number, body
            from chapter_drafts
            where chapter_brief_id = ?
            order by version_number desc
            limit 1
            """, [.uuid(chapterId)]))
        let versionRows = try await database.query(SQLStatement("""
            select id, version_number, updated_at, coalesce(editor_notes, '') as editor_notes
            from chapter_drafts
            where chapter_brief_id = ?
            order by version_number desc
            """, [.uuid(chapterId)]))
        let versions = try versionRows.map { row in
            DraftVersion(
                id: try row.uuid("id"),
                versionNumber: row.int("version_number"),
                updatedAt: row.string("updated_at"),
                editorNotes: row.string("editor_notes")
            )
        }
        if let latest = draftRows.first {
            return DraftPayload(
                draftId: try latest.uuid("id"),
                versionNumber: latest.int("version_number"),
                body: latest.string("body"),
                source: "draft",
                versions: versions
            )
        }
        let chapter = try await database.query(SQLStatement("select * from chapter_briefs where id = ?", [.uuid(chapterId)])).first
        return DraftPayload(
            draftId: nil,
            versionNumber: 0,
            body: chapter.map { briefSkeleton(row: $0) } ?? "",
            source: "brief_skeleton",
            versions: []
        )
    }

    func autosaveDraft(chapterId: UUID, body: String, baseVersion: Int) async throws -> DraftPayload {
        if baseVersion == 0 {
            return try await saveDraftVersion(chapterId: chapterId, body: body, baseVersion: 0, notes: "Created from autosave.")
        }
        try await database.execute(SQLStatement("""
            update chapter_drafts
            set body = ?, updated_at = ?
            where chapter_brief_id = ? and version_number = ?
            """, [.string(body), .date(), .uuid(chapterId), .int(baseVersion)]))
        return try await draftPayload(chapterId: chapterId)
    }

    func saveDraftVersion(chapterId: UUID, body: String, baseVersion: Int, notes: String) async throws -> DraftPayload {
        let nextVersion = baseVersion + 1
        try await database.execute(SQLStatement("""
            insert into chapter_drafts (
              id, chapter_brief_id, agent_run_id, version_number, body_format, body,
              model_provider, model_name, model_metadata, generation_prompt_ref, status,
              editor_notes, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                .uuid(UUID()),
                .uuid(chapterId),
                .null,
                .int(nextVersion),
                .string("markdown"),
                .string(body),
                .null,
                .null,
                .json(Data("{}".utf8)),
                .string("bookmaker.manual"),
                .string("draft"),
                .string(notes),
                .date(),
                .date()
            ]))
        return try await draftPayload(chapterId: chapterId)
    }

    func restoreDraftVersion(chapterId: UUID, version: Int) async throws -> DraftPayload {
        let rows = try await database.query(SQLStatement(
            "select body from chapter_drafts where chapter_brief_id = ? and version_number = ?",
            [.uuid(chapterId), .int(version)]
        ))
        guard let body = rows.first?.string("body") else {
            throw BookMakerError.database("Draft version not found.")
        }
        let current = try await draftPayload(chapterId: chapterId)
        return try await saveDraftVersion(
            chapterId: chapterId,
            body: body,
            baseVersion: current.versionNumber,
            notes: "Restored from version \(version)."
        )
    }

    func compiledBook(projectId: UUID, includeDrafts: Bool) async throws -> CompiledBook {
        let rows = try await database.query(SQLStatement("""
            select cb.*, cd.body, cd.version_number
            from chapter_briefs cb
            left join chapter_drafts cd on cd.id = (
              select id from chapter_drafts latest
              where latest.chapter_brief_id = cb.id
              order by latest.version_number desc
              limit 1
            )
            where cb.project_id = ?
            \(includeDrafts ? "" : "and cb.status = 'ready'")
            order by coalesce(cb.sequence_order, 9999), cb.created_at asc
            """, [.uuid(projectId)]))
        let chapters = try rows.map { try chapter(from: $0) }
        let bodies = zip(chapters, rows).map { chapter, row in
            let body = row.string("body").nilIfBlank ?? briefSkeleton(row: row)
            return (chapter, body)
        }
        return ManuscriptCompiler.compile(bodies: bodies)
    }

    func recordRender(projectId: UUID, volumeId: UUID?, outputPath: String, logs: String, status: String) async throws {
        try await database.execute(SQLStatement("""
            insert into rendered_outputs (
              id, project_id, volume_id, chapter_brief_id, output_type, renderer, config_path,
              output_path, git_commit_hash, build_logs, status, rendered_at, metadata, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                .uuid(UUID()),
                .uuid(projectId),
                volumeId.map(SQLValue.uuid) ?? .null,
                .null,
                .string("print_ready_pdf"),
                .string("BookMaker Process"),
                .null,
                .string(outputPath),
                .null,
                .string(logs),
                .string(status),
                .date(),
                .json(Data("{}".utf8)),
                .date(),
                .date()
            ]))
    }

    private func count(_ table: String, where condition: String, _ parameters: [SQLValue]) async throws -> Int {
        let rows = try await database.query(SQLStatement("select count(*) as count from \(table) where \(condition)", parameters))
        return rows.first?.int("count") ?? 0
    }

    private func uniqueProjectSlug(_ base: String) async throws -> String {
        var slug = base
        var suffix = 2
        while try await count("projects", where: "slug = ?", [.string(slug)]) > 0 {
            slug = "\(base)-\(suffix)"
            suffix += 1
        }
        return slug
    }

    private func uniqueChapterSlug(_ base: String, volumeId: UUID?) async throws -> String {
        var slug = base
        var suffix = 2
        while true {
            let rows: [SQLRow]
            if let volumeId {
                rows = try await database.query(SQLStatement(
                    "select count(*) as count from chapter_briefs where volume_id = ? and slug = ?",
                    [.uuid(volumeId), .string(slug)]
                ))
            } else {
                rows = try await database.query(SQLStatement(
                    "select count(*) as count from chapter_briefs where volume_id is null and slug = ?",
                    [.string(slug)]
                ))
            }
            if rows.first?.int("count") ?? 0 == 0 { return slug }
            slug = "\(base)-\(suffix)"
            suffix += 1
        }
    }

    private func project(from row: SQLRow) throws -> ProjectRecord {
        let metadata = decodeBookMakerMetadata(row.string("metadata"))
        return ProjectRecord(
            id: try row.uuid("id"),
            name: row.string("name"),
            slug: row.string("slug"),
            description: row.string("description"),
            status: row.string("status"),
            metadata: metadata
        )
    }

    private func volume(from row: SQLRow) throws -> VolumeRecord {
        VolumeRecord(
            id: try row.uuid("id"),
            projectId: try row.uuid("project_id"),
            title: row.string("title"),
            subtitle: row.string("subtitle"),
            slug: row.string("slug"),
            status: row.string("status"),
            metadata: decodeBookMakerMetadata(row.string("metadata"))
        )
    }

    private func chapter(from row: SQLRow) throws -> ChapterRecord {
        ChapterRecord(
            id: try row.uuid("id"),
            projectId: try row.uuid("project_id"),
            volumeId: row.string("volume_id").isEmpty ? nil : try UUID(bookMakerDatabaseString: row.string("volume_id")),
            title: row.string("title"),
            subtitle: row.string("subtitle"),
            slug: row.string("slug"),
            sequenceOrder: row.int("sequence_order"),
            status: ChapterStatus(rawValue: row.string("status")) ?? .draft,
            intendedPageCount: optionalInt(row, "intended_page_count"),
            targetWordCount: optionalInt(row, "target_word_count"),
            situation: row.string("situation"),
            constraint: row.string("constraint"),
            build: row.string("build"),
            pattern: row.string("pattern"),
            oahuLayer: row.string("oahu_layer"),
            fieldNote: row.string("field_note"),
            nextBuild: row.string("next_build"),
            metadata: decodeJSON(ChapterMetadata.self, from: row.string("metadata"), fallback: .empty)
        )
    }

    private func optionalInt(_ row: SQLRow, _ key: String) -> Int? {
        let raw = row.string(key)
        return raw.isEmpty ? nil : Int(raw)
    }

    private func decodeBookMakerMetadata(_ value: String) -> BookMakerMetadata {
        guard let data = value.data(using: .utf8),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return .empty
        }
        if let maker = raw["bookmaker"],
           let makerData = try? JSONSerialization.data(withJSONObject: maker),
           let decoded = try? JSONCoding.decoder.decode(BookMakerMetadata.self, from: makerData) {
            return decoded
        }
        if let decoded = try? JSONCoding.decoder.decode(BookMakerMetadata.self, from: data) {
            return decoded
        }
        return .empty
    }

    private func briefSkeleton(row: SQLRow) -> String {
        let title = row.string("title", default: "Untitled Chapter")
        let subtitle = row.string("subtitle")
        let fieldNote = row.string("field_note")
        let situation = row.string("situation")
        let body = [situation, row.string("constraint"), row.string("build"), row.string("pattern"), fieldNote]
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .joined(separator: "\n\n")
        let subtitleLine = subtitle.isEmpty ? "" : "\n\n<p class=\"chapter-subtitle\">\(subtitle)</p>"
        return "# \(title)\(subtitleLine)\n\n\(body.nilIfBlank ?? "Draft from this chapter brief.")"
    }
}

