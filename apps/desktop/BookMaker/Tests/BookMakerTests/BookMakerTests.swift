import Foundation
import Testing
@testable import BookMaker

@Test
func databaseURLParsesSupportedForms() throws {
    let sqlite = try ParsedDatabaseURL("sqlite:////tmp/bookmaker.db")
    #expect(sqlite.kind == .sqlite)
    #expect(sqlite.sqlitePath == "/tmp/bookmaker.db")

    let postgres = try ParsedDatabaseURL("postgresql+psycopg://user:pass@localhost:5432/books")
    #expect(postgres.kind == .postgres)
    #expect(postgres.postgresURL == "postgresql://user:pass@localhost:5432/books")
}

@Test
func stableSlugKeepsUsefulWords() {
    #expect(stableSlug("Everything in Moderation, Including Moderation") == "everything-in-moderation-including-moderation")
    #expect(stableSlug("   ", fallback: "chapter") == "chapter")
}

@Test
func templateStoreLoadsBundledProfiles() throws {
    let templates = try TemplateStore().loadTemplates()
    #expect(templates.map(\.id).contains("field-notes-essay"))
    #expect(templates.map(\.id).contains("blank-builder-book"))
    #expect(templates.first { $0.id == "field-notes-essay" }?.starterChapters.isEmpty == false)
}

@Test
func manuscriptCompilerBuildsRawAndVivliostyleMarkdown() {
    let chapter = ChapterRecord(
        id: UUID(),
        projectId: UUID(),
        volumeId: nil,
        title: "The Draft Is A Workbench",
        subtitle: "Versioned prose",
        slug: "draft-workbench",
        sequenceOrder: 2,
        status: .ready,
        intendedPageCount: 8,
        targetWordCount: 2000,
        situation: "",
        constraint: "",
        build: "",
        pattern: "",
        oahuLayer: "",
        fieldNote: "",
        nextBuild: "",
        metadata: .empty
    )
    let compiled = ManuscriptCompiler.compile(bodies: [(chapter, "# The Draft Is A Workbench\n\nBody text.")])

    #expect(compiled.chapterCount == 1)
    #expect(compiled.rawMarkdown.contains("Body text."))
    #expect(compiled.vivliostyleMarkdown.contains("data-chapter-slug=\"draft-workbench\""))
    #expect(compiled.vivliostyleMarkdown.contains("<p class=\"opener-roman\" aria-hidden=\"true\">II</p>"))
}

@Test
func sqliteRepositoryCreatesTemplateBackedBook() async throws {
    let path = FileManager.default.temporaryDirectory
        .appendingPathComponent("bookmaker-test-\(UUID().uuidString).db")
        .path
    defer { try? FileManager.default.removeItem(atPath: path) }

    let db = SQLiteBookDatabase(path: path)
    try await db.connect()
    try await SchemaInitializer(database: db).ensureSchema()
    let repository = BookRepository(database: db)
    let template = try #require(try TemplateStore().loadTemplates().first { $0.id == "field-notes-essay" })

    let project = try await repository.createProject(name: "Builder Notes", template: template)
    let projects = try await repository.listProjects()
    let volumes = try await repository.volumes(projectId: project.id)
    let chapters = try await repository.chapters(projectId: project.id, volumeId: volumes.first?.id)
    let draft = try await repository.draftPayload(chapterId: try #require(chapters.first?.id))

    #expect(projects.count == 1)
    #expect(volumes.count == 1)
    #expect(chapters.count == template.starterChapters.count)
    #expect(draft.body.contains("#"))
}

@Test
func sqliteSchemaCreatesBriefChatTables() async throws {
    let path = FileManager.default.temporaryDirectory
        .appendingPathComponent("bookmaker-schema-\(UUID().uuidString).db")
        .path
    defer { try? FileManager.default.removeItem(atPath: path) }

    let db = SQLiteBookDatabase(path: path)
    try await db.connect()
    let initializer = SchemaInitializer(database: db)
    try await initializer.ensureSchema()

    let tables = try await initializer.inspect()
    #expect(tables.contains("bookmaker_chapter_messages"))
    #expect(tables.contains("bookmaker_chapter_brief_versions"))
    #expect(tables.contains("bookmaker_chapter_brief_state"))
}

@Test
func briefChatRepositoryVersionsAndRestoresWithoutMutatingHistory() async throws {
    let path = FileManager.default.temporaryDirectory
        .appendingPathComponent("bookmaker-brief-chat-\(UUID().uuidString).db")
        .path
    defer { try? FileManager.default.removeItem(atPath: path) }

    let db = SQLiteBookDatabase(path: path)
    try await db.connect()
    try await SchemaInitializer(database: db).ensureSchema()
    let repository = BookRepository(database: db)
    let chatRepository = ChapterBriefChatRepository(database: db)
    let template = try #require(try TemplateStore().loadTemplates().first { $0.id == "field-notes-essay" })
    let project = try await repository.createProject(name: "Versioned Briefs", template: template)
    let volume = try #require(try await repository.volumes(projectId: project.id).first)
    let chapter = try #require(try await repository.chapters(projectId: project.id, volumeId: volume.id).first)

    let initial = try await chatRepository.state(projectId: project.id, chapter: chapter)
    #expect(initial.messages.isEmpty)
    #expect(initial.versions.isEmpty)

    let user = try await chatRepository.appendUserMessage(
        projectId: project.id,
        chapterId: chapter.id,
        text: "Make this chapter about the moment the interface became the source of truth."
    )
    var brief = StructuredChapterBrief.seed(from: chapter)
    brief.goal = "Show how the interface became the durable state."
    brief.thesis = "The chat explains the path, but the structured brief carries the chapter."
    brief.fieldNote = "A good writing tool lets conversation move while state stays inspectable."
    brief.confidence0To1 = 0.78
    let result = ChapterBriefTurnResult(
        assistantText: "I am treating the brief as the durable layer and the chat as the path there.",
        brief: brief,
        changeSummary: "Clarified canonical state and chat transcript roles."
    )
    let first = try await chatRepository.appendAssistantTurn(
        projectId: project.id,
        chapter: chapter,
        userMessage: user,
        result: result,
        model: "gpt-test",
        responseId: "resp_test",
        usage: OpenAIUsage(inputTokens: 10, outputTokens: 20, totalTokens: 30)
    )

    #expect(first.messages.count == 2)
    #expect(first.versions.count == 1)
    #expect(first.activeVersion?.versionNumber == 1)
    #expect(first.activeVersion?.brief.thesis == brief.thesis)

    let restored = try await chatRepository.restoreVersion(
        projectId: project.id,
        chapter: chapter,
        version: try #require(first.activeVersion)
    )
    #expect(restored.versions.count == 2)
    #expect(restored.activeVersion?.versionNumber == 2)
    #expect(restored.orderedVersions.first?.versionNumber == 1)

    let refreshed = try #require(try await repository.chapters(projectId: project.id, volumeId: volume.id).first)
    #expect(refreshed.fieldNote == brief.fieldNote)
    #expect(refreshed.metadata.thesis == brief.thesis)
}

@Test
func chapterBriefTurnResultDecodesSnakeCase() throws {
    let json = """
    {
      "assistant_text": "That gives the chapter a clearer job.",
      "change_summary": "Set the goal and uncertainty.",
      "brief": {
        "chapter_form": "scene_to_principle",
        "goal": "Explain the working pattern.",
        "reader": "Builder-reader",
        "thesis": "The brief is the durable product state.",
        "situation": "A chat turn produced a useful distinction.",
        "constraint": "The transcript alone is too loose for downstream drafting.",
        "build": "A full replacement brief is extracted after each turn.",
        "pattern": "Conversation can be fluid when state is structured.",
        "field_note": "The transcript remembers the path; the brief carries the work.",
        "next_build": "Use the brief to draft the chapter.",
        "source_cluster": ["workspace notes"],
        "visual_slots": ["brief version timeline"],
        "success_criteria": ["Clear canonical state"],
        "open_questions": ["Which source scenes belong here?"],
        "confidence_0_to_1": 0.72
      }
    }
    """.data(using: .utf8)!

    let decoded = try JSONCoding.decoder.decode(ChapterBriefTurnResult.self, from: json)
    #expect(decoded.assistantText.contains("clearer job"))
    #expect(decoded.brief.confidence0To1 == 0.72)
    #expect(decoded.brief.openQuestions == ["Which source scenes belong here?"])
}

@Test
func sourceRootResolverPrefersCurrentPackageDirectory() throws {
    let root = try makeTemporaryDirectory(prefix: "bookmaker-source-root")
    defer { try? FileManager.default.removeItem(at: root) }
    try "test package".write(to: root.appendingPathComponent("Package.swift"), atomically: true, encoding: .utf8)

    let resolved = BookMakerPathResolver.sourceRoot(currentDirectory: root, workspaceRoot: root.deletingLastPathComponent().path)
    #expect(resolved == root.standardizedFileURL.path)
}

@Test
func sourceRootResolverFindsNestedBookMakerPackage() throws {
    let workspace = try makeTemporaryDirectory(prefix: "bookmaker-workspace-root")
    defer { try? FileManager.default.removeItem(at: workspace) }
    let nested = workspace.appendingPathComponent("apps/desktop/BookMaker", isDirectory: true)
    try FileManager.default.createDirectory(at: nested, withIntermediateDirectories: true)
    try "test package".write(to: nested.appendingPathComponent("Package.swift"), atomically: true, encoding: .utf8)

    let unrelated = workspace.appendingPathComponent("notes", isDirectory: true)
    try FileManager.default.createDirectory(at: unrelated, withIntermediateDirectories: true)
    let resolved = BookMakerPathResolver.sourceRoot(currentDirectory: unrelated, workspaceRoot: workspace.path)
    #expect(resolved == nested.standardizedFileURL.path)
}

@Test
func shellCommandRunnerCapturesStdoutAndStderr() async throws {
    let root = try makeTemporaryDirectory(prefix: "bookmaker-shell-output")
    defer { try? FileManager.default.removeItem(at: root) }
    let runner = ShellCommandRunner()

    let result = try await collectShellCommand(
        runner.run(command: "printf 'hello'; printf 'warn' >&2", workingDirectory: root.path)
    )

    #expect(result.stdout.contains("hello"))
    #expect(result.stderr.contains("warn"))
    #expect(result.result?.status == .succeeded)
    #expect(result.result?.exitCode == 0)
}

@Test
func shellCommandRunnerReportsFailedExit() async throws {
    let root = try makeTemporaryDirectory(prefix: "bookmaker-shell-failure")
    defer { try? FileManager.default.removeItem(at: root) }
    let runner = ShellCommandRunner()

    let result = try await collectShellCommand(
        runner.run(command: "printf 'bad' >&2; exit 7", workingDirectory: root.path)
    )

    #expect(result.stderr.contains("bad"))
    #expect(result.result?.status == .failed)
    #expect(result.result?.exitCode == 7)
}

@Test
func shellCommandRunnerCancelsActiveProcess() async throws {
    let root = try makeTemporaryDirectory(prefix: "bookmaker-shell-cancel")
    defer { try? FileManager.default.removeItem(at: root) }
    let runner = ShellCommandRunner()

    let task = Task {
        try await collectShellCommand(runner.run(command: "sleep 2", workingDirectory: root.path))
    }
    try await Task.sleep(nanoseconds: 120_000_000)
    runner.cancel()

    let result = try await task.value
    #expect(result.result?.status == .cancelled)
}

private func makeTemporaryDirectory(prefix: String) throws -> URL {
    let url = FileManager.default.temporaryDirectory
        .appendingPathComponent("\(prefix)-\(UUID().uuidString)", isDirectory: true)
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

private func collectShellCommand(_ stream: AsyncThrowingStream<ShellCommandEvent, Error>) async throws -> (
    stdout: String,
    stderr: String,
    result: TerminalRunResult?
) {
    var stdout = ""
    var stderr = ""
    var result: TerminalRunResult?
    for try await event in stream {
        switch event {
        case .output(.stdout, let text):
            stdout += text
        case .output(.stderr, let text):
            stderr += text
        case .output(.system, _):
            break
        case .finished(let runResult):
            result = runResult
        }
    }
    return (stdout, stderr, result)
}
