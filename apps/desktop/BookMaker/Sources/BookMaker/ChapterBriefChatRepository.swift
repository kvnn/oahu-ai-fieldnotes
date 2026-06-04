import Foundation

actor ChapterBriefChatRepository {
    let database: any BookDatabase

    init(database: any BookDatabase) {
        self.database = database
    }

    func state(projectId: UUID, chapter: ChapterRecord) async throws -> ChapterBriefChatState {
        let messages = try await messages(chapterId: chapter.id)
        let versions = try await versions(chapter: chapter)
        let activeId = try await activeVersionId(chapterId: chapter.id) ?? versions.last?.id
        return ChapterBriefChatState(
            seedBrief: StructuredChapterBrief.seed(from: chapter),
            messages: messages,
            versions: versions,
            activeVersionId: activeId,
            viewedVersionId: activeId
        )
    }

    func appendUserMessage(projectId: UUID, chapterId: UUID, text: String, mediaRefs: [String] = []) async throws -> ChapterBriefMessage {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw BookMakerError.database("Brief message cannot be empty.")
        }

        let id = UUID()
        let now = Date()
        let createdAt = DateCoding.string(from: now)
        let turnIndex = try await nextTurnIndex(chapterId: chapterId)
        try await database.execute(SQLStatement("""
            insert into bookmaker_chapter_messages (
              id, project_id, chapter_brief_id, role, text, media_refs, turn_index, created_at, metadata
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                .uuid(id),
                .uuid(projectId),
                .uuid(chapterId),
                .string(BriefMessageRole.user.rawValue),
                .string(trimmed),
                .json(try jsonData(mediaRefs)),
                .int(turnIndex),
                .date(now),
                .json(Data("{}".utf8))
            ]))
        return ChapterBriefMessage(
            id: id,
            projectId: projectId,
            chapterId: chapterId,
            role: .user,
            text: trimmed,
            mediaRefs: mediaRefs,
            turnIndex: turnIndex,
            createdAt: createdAt
        )
    }

    func appendAssistantTurn(
        projectId: UUID,
        chapter: ChapterRecord,
        userMessage: ChapterBriefMessage,
        result: ChapterBriefTurnResult,
        model: String,
        responseId: String,
        usage: OpenAIUsage
    ) async throws -> ChapterBriefChatState {
        let versionId = UUID()
        let messageId = UUID()
        let now = Date()
        try await database.transaction {
            try await database.execute(SQLStatement("""
                insert into bookmaker_chapter_messages (
                  id, project_id, chapter_brief_id, role, text, media_refs, turn_index, created_at, metadata
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    .uuid(messageId),
                    .uuid(projectId),
                    .uuid(chapter.id),
                    .string(BriefMessageRole.assistant.rawValue),
                    .string(result.assistantText),
                    .json(Data("[]".utf8)),
                    .int(userMessage.turnIndex),
                    .date(now),
                    .json(Data("{}".utf8))
                ]))
            try await insertVersion(
                id: versionId,
                projectId: projectId,
                chapter: chapter,
                versionNumber: try await nextVersionNumber(chapterId: chapter.id),
                turnIndex: userMessage.turnIndex,
                brief: result.brief,
                changeSummary: result.changeSummary,
                modelProvider: "openai",
                modelName: model,
                responseId: responseId,
                usage: usage,
                createdAt: now
            )
            try await setActiveVersion(chapterId: chapter.id, versionId: versionId, updatedAt: now)
            try await mirrorActiveBrief(result.brief, into: chapter, updatedAt: now)
        }
        return try await state(projectId: projectId, chapter: chapter)
    }

    func restoreVersion(projectId: UUID, chapter: ChapterRecord, version: ChapterBriefVersion) async throws -> ChapterBriefChatState {
        let versionId = UUID()
        let now = Date()
        let turnIndex = try await nextTurnIndex(chapterId: chapter.id)
        try await database.transaction {
            try await insertVersion(
                id: versionId,
                projectId: projectId,
                chapter: chapter,
                versionNumber: try await nextVersionNumber(chapterId: chapter.id),
                turnIndex: turnIndex,
                brief: version.brief,
                changeSummary: "Restored from brief v\(version.versionNumber).",
                modelProvider: "bookmaker",
                modelName: "restore",
                responseId: version.id.uuidString,
                usage: OpenAIUsage(inputTokens: 0, outputTokens: 0, totalTokens: 0),
                createdAt: now
            )
            try await setActiveVersion(chapterId: chapter.id, versionId: versionId, updatedAt: now)
            try await mirrorActiveBrief(version.brief, into: chapter, updatedAt: now)
        }
        return try await state(projectId: projectId, chapter: chapter)
    }

    private func messages(chapterId: UUID) async throws -> [ChapterBriefMessage] {
        let rows = try await database.query(SQLStatement("""
            select id, project_id, chapter_brief_id, role, text, media_refs, turn_index, created_at
            from bookmaker_chapter_messages
            where chapter_brief_id = ?
            order by turn_index asc, created_at asc
            """, [.uuid(chapterId)]))
        return try rows.map(message(from:))
    }

    private func versions(chapter: ChapterRecord) async throws -> [ChapterBriefVersion] {
        let rows = try await database.query(SQLStatement("""
            select id, project_id, chapter_brief_id, version_number, turn_index, brief_json,
                   change_summary, coalesce(model_provider, '') as model_provider,
                   coalesce(model_name, '') as model_name, coalesce(response_id, '') as response_id,
                   usage_json, created_at
            from bookmaker_chapter_brief_versions
            where chapter_brief_id = ?
            order by version_number asc, created_at asc
            """, [.uuid(chapter.id)]))
        return try rows.map { try version(from: $0, chapter: chapter) }
    }

    private func activeVersionId(chapterId: UUID) async throws -> UUID? {
        let row = try await database.query(SQLStatement(
            "select active_version_id from bookmaker_chapter_brief_state where chapter_brief_id = ?",
            [.uuid(chapterId)]
        )).first
        guard let raw = row?.string("active_version_id").nilIfBlank else { return nil }
        return try UUID(bookMakerDatabaseString: raw)
    }

    private func nextTurnIndex(chapterId: UUID) async throws -> Int {
        let rows = try await database.query(SQLStatement(
            "select coalesce(max(turn_index), 0) + 1 as next_turn from bookmaker_chapter_messages where chapter_brief_id = ?",
            [.uuid(chapterId)]
        ))
        return rows.first?.int("next_turn", default: 1) ?? 1
    }

    private func nextVersionNumber(chapterId: UUID) async throws -> Int {
        let rows = try await database.query(SQLStatement(
            "select coalesce(max(version_number), 0) + 1 as next_version from bookmaker_chapter_brief_versions where chapter_brief_id = ?",
            [.uuid(chapterId)]
        ))
        return rows.first?.int("next_version", default: 1) ?? 1
    }

    private func insertVersion(
        id: UUID,
        projectId: UUID,
        chapter: ChapterRecord,
        versionNumber: Int,
        turnIndex: Int,
        brief: StructuredChapterBrief,
        changeSummary: String,
        modelProvider: String,
        modelName: String,
        responseId: String,
        usage: OpenAIUsage,
        createdAt: Date
    ) async throws {
        try await database.execute(SQLStatement("""
            insert into bookmaker_chapter_brief_versions (
              id, project_id, chapter_brief_id, version_number, turn_index, brief_json,
              change_summary, model_provider, model_name, response_id, usage_json, created_at, metadata
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                .uuid(id),
                .uuid(projectId),
                .uuid(chapter.id),
                .int(versionNumber),
                .int(turnIndex),
                .json(try jsonData(brief)),
                .string(changeSummary),
                .string(modelProvider),
                .string(modelName),
                .string(responseId),
                .json(try jsonData(usage)),
                .date(createdAt),
                .json(Data("{}".utf8))
            ]))
    }

    private func setActiveVersion(chapterId: UUID, versionId: UUID, updatedAt: Date) async throws {
        try await database.execute(SQLStatement("""
            insert into bookmaker_chapter_brief_state (chapter_brief_id, active_version_id, updated_at)
            values (?, ?, ?)
            on conflict(chapter_brief_id) do update set
              active_version_id = excluded.active_version_id,
              updated_at = excluded.updated_at
            """, [
                .uuid(chapterId),
                .uuid(versionId),
                .date(updatedAt)
            ]))
    }

    private func mirrorActiveBrief(_ brief: StructuredChapterBrief, into chapter: ChapterRecord, updatedAt: Date) async throws {
        let metadata = brief.asChapterMetadata(existing: chapter.metadata)
        try await database.execute(SQLStatement("""
            update chapter_briefs
            set situation = ?, "constraint" = ?, build = ?, pattern = ?,
                field_note = ?, next_build = ?, metadata = ?, updated_at = ?
            where id = ?
            """, [
                .string(brief.situation),
                .string(brief.constraint),
                .string(brief.build),
                .string(brief.pattern),
                .string(brief.fieldNote),
                .string(brief.nextBuild),
                .json(try jsonData(metadata)),
                .date(updatedAt),
                .uuid(chapter.id)
            ]))
    }

    private func message(from row: SQLRow) throws -> ChapterBriefMessage {
        ChapterBriefMessage(
            id: try row.uuid("id"),
            projectId: try row.uuid("project_id"),
            chapterId: try row.uuid("chapter_brief_id"),
            role: BriefMessageRole(rawValue: row.string("role")) ?? .assistant,
            text: row.string("text"),
            mediaRefs: decodeJSON([String].self, from: row.string("media_refs"), fallback: []),
            turnIndex: row.int("turn_index"),
            createdAt: row.string("created_at")
        )
    }

    private func version(from row: SQLRow, chapter: ChapterRecord) throws -> ChapterBriefVersion {
        ChapterBriefVersion(
            id: try row.uuid("id"),
            projectId: try row.uuid("project_id"),
            chapterId: try row.uuid("chapter_brief_id"),
            versionNumber: row.int("version_number"),
            turnIndex: row.int("turn_index"),
            brief: decodeJSON(StructuredChapterBrief.self, from: row.string("brief_json"), fallback: .seed(from: chapter)),
            changeSummary: row.string("change_summary"),
            modelProvider: row.string("model_provider"),
            modelName: row.string("model_name"),
            responseId: row.string("response_id"),
            usageJSON: row.string("usage_json"),
            createdAt: row.string("created_at")
        )
    }
}
