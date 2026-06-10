import Combine
import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published var config: BookMakerConfig
    @Published var templates: [BookTemplate] = []
    @Published var projects: [ProjectRecord] = []
    @Published var volumes: [VolumeRecord] = []
    @Published var chapters: [ChapterRecord] = []
    @Published var selectedProject: ProjectRecord?
    @Published var selectedVolume: VolumeRecord?
    @Published var selectedChapter: ChapterRecord?
    @Published var draft = ""
    @Published var draftPayload = DraftPayload(draftId: nil, versionNumber: 0, body: "", source: "none", versions: [])
    @Published var briefChatState = ChapterBriefChatState.empty(seed: .blank)
    @Published var briefComposerText = ""
    @Published var briefComposerMediaRefs: [String] = []
    @Published var isBriefSending = false
    @Published var sourceStats = SourceStats()
    @Published var compiledBook: CompiledBook?
    @Published var apiKeySource: APIKeySource = .missing
    @Published var isConfigPresented = false
    @Published var isBusy = false
    @Published var statusMessage = "Ready"
    @Published var errorMessage = ""
    @Published var newBookName = ""
    @Published var newChapterTitle = ""
    @Published var newChapterSubtitle = ""
    @Published var isTerminalPresented = false
    @Published var selectedTerminalPresetId = "pwd"
    @Published var terminalCommand = "pwd"
    @Published var terminalWorkingDirectory = ""
    @Published var terminalStatus: TerminalRunStatus = .idle
    @Published var terminalExitCode: Int32?
    @Published var terminalOutput: [TerminalOutputChunk] = []

    private let configStore: ConfigStore
    private let credentials: CredentialStore
    private let shellRunner: ShellCommandRunner
    private var database: (any BookDatabase)?
    private var repository: BookRepository?
    private var briefRepository: ChapterBriefChatRepository?
    private var autosaveTask: Task<Void, Never>?
    private var terminalTask: Task<Void, Never>?

    init(
        configStore: ConfigStore = ConfigStore(),
        credentials: CredentialStore = KeychainCredentialStore(),
        shellRunner: ShellCommandRunner = ShellCommandRunner()
    ) {
        self.configStore = configStore
        self.config = configStore.config
        self.credentials = credentials
        self.shellRunner = shellRunner
        self.templates = (try? TemplateStore().loadTemplates()) ?? []
        self.newBookName = "Untitled Book"
        let firstPreset = terminalPresets.first
        self.selectedTerminalPresetId = firstPreset?.id ?? "pwd"
        self.terminalCommand = firstPreset?.command ?? "pwd"
        self.terminalWorkingDirectory = firstPreset.map {
            BookMakerPathResolver.workingDirectory(for: $0.workingDirectoryMode, workspaceRoot: config.workspaceRoot)
        } ?? BookMakerPathResolver.sourceRoot(workspaceRoot: config.workspaceRoot)
        refreshAPIKeySource()
        isConfigPresented = config.databaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || apiKeySource == .missing
    }

    var selectedTemplate: BookTemplate? {
        templates.first { $0.id == config.defaultTemplateID } ?? templates.first
    }

    var canUseWorkspace: Bool {
        repository != nil && selectedProject != nil
    }

    var terminalPresets: [TerminalPreset] {
        [
            TerminalPreset(id: "pwd", label: "pwd", command: "pwd", workingDirectoryMode: .sourceRoot),
            TerminalPreset(id: "git-status", label: "Git Status", command: "git status --short", workingDirectoryMode: .workspaceRoot),
            TerminalPreset(
                id: "bookmaker-test",
                label: "BookMaker Tests",
                command: "CLANG_MODULE_CACHE_PATH=/private/tmp/bookmaker-clang-cache swift test",
                workingDirectoryMode: .sourceRoot
            ),
            TerminalPreset(
                id: "bookmaker-build",
                label: "BookMaker Build",
                command: "CLANG_MODULE_CACHE_PATH=/private/tmp/bookmaker-clang-cache swift build",
                workingDirectoryMode: .sourceRoot
            ),
            TerminalPreset(id: "render", label: "Render Book", command: config.renderCommand, workingDirectoryMode: .workspaceRoot)
        ]
    }

    var canRunTerminalCommand: Bool {
        terminalStatus != .running &&
            terminalCommand.nilIfBlank != nil &&
            terminalWorkingDirectory.nilIfBlank != nil
    }

    var terminalStatusSummary: String {
        if let terminalExitCode {
            "\(terminalStatus.label) (\(terminalExitCode))"
        } else {
            terminalStatus.label
        }
    }

    func refreshAPIKeySource() {
        if (try? credentials.loadAPIKey())?.nilIfBlank != nil {
            apiKeySource = .keychain
        } else if ProcessInfo.processInfo.environment["OPENAI_API_KEY"]?.nilIfBlank != nil {
            apiKeySource = .environment
        } else {
            apiKeySource = .missing
        }
    }

    func saveConfig(apiKey: String? = nil) async {
        do {
            configStore.config = config
            try configStore.save()
            if let apiKey {
                try credentials.saveAPIKey(apiKey)
            }
            refreshSelectedTerminalPreset()
            refreshAPIKeySource()
            isConfigPresented = false
            await connect()
        } catch {
            report(error)
        }
    }

    func connect() async {
        await runBusy("Connecting") {
            let parsed = try ParsedDatabaseURL(config.databaseURL)
            let db = makeBookDatabase(from: parsed)
            try await db.connect()
            try await SchemaInitializer(database: db).ensureSchema()
            database = db
            repository = BookRepository(database: db)
            briefRepository = ChapterBriefChatRepository(database: db)
            statusMessage = "Connected to \(parsed.kind.rawValue)"
            try await loadProjects()
        }
    }

    func loadProjects() async throws {
        guard let repository else { return }
        projects = try await repository.listProjects()
        if selectedProject == nil {
            selectedProject = projects.first
        }
        try await loadSelectedProject()
    }

    func loadSelectedProject() async throws {
        guard let repository, let project = selectedProject else {
            volumes = []
            chapters = []
            selectedVolume = nil
            selectedChapter = nil
            draft = ""
            briefChatState = ChapterBriefChatState.empty(seed: .blank)
            briefComposerText = ""
            briefComposerMediaRefs = []
            return
        }
        volumes = try await repository.volumes(projectId: project.id)
        selectedVolume = volumes.first
        chapters = try await repository.chapters(projectId: project.id, volumeId: selectedVolume?.id)
        sourceStats = try await repository.sourceStats(projectId: project.id)
        if selectedChapter == nil || !chapters.contains(where: { $0.id == selectedChapter?.id }) {
            selectedChapter = chapters.first
        }
        try await loadSelectedChapter()
    }

    func selectProject(_ project: ProjectRecord) {
        selectedProject = project
        selectedChapter = nil
        Task {
            do { try await loadSelectedProject() } catch { report(error) }
        }
    }

    func selectChapter(_ chapter: ChapterRecord) {
        selectedChapter = chapter
        Task {
            do { try await loadSelectedChapter() } catch { report(error) }
        }
    }

    func loadSelectedChapter() async throws {
        guard let repository, let chapter = selectedChapter else {
            draft = ""
            draftPayload = DraftPayload(draftId: nil, versionNumber: 0, body: "", source: "none", versions: [])
            briefChatState = ChapterBriefChatState.empty(seed: .blank)
            briefComposerText = ""
            briefComposerMediaRefs = []
            return
        }
        draftPayload = try await repository.draftPayload(chapterId: chapter.id)
        draft = draftPayload.body
        try await loadBriefChatState()
    }

    func loadBriefChatState() async throws {
        guard let briefRepository, let project = selectedProject, let chapter = selectedChapter else {
            briefChatState = ChapterBriefChatState.empty(seed: .blank)
            return
        }
        briefChatState = try await briefRepository.state(projectId: project.id, chapter: chapter)
        briefComposerText = ""
        briefComposerMediaRefs = []
    }

    func createBook() async {
        guard let repository, let template = selectedTemplate else { return }
        let name = newBookName.nilIfBlank ?? "Untitled Book"
        await runBusy("Creating book") {
            let project = try await repository.createProject(name: name, template: template)
            projects = try await repository.listProjects()
            selectedProject = project
            selectedChapter = nil
            newBookName = "Untitled Book"
            try await loadSelectedProject()
            statusMessage = "Created \(project.name)"
        }
    }

    func createChapter() async {
        guard let repository, let project = selectedProject else { return }
        let title = newChapterTitle.nilIfBlank ?? "Untitled Chapter"
        await runBusy("Creating chapter") {
            let chapter = try await repository.createChapter(
                projectId: project.id,
                volumeId: selectedVolume?.id,
                title: title,
                subtitle: newChapterSubtitle
            )
            chapters = try await repository.chapters(projectId: project.id, volumeId: selectedVolume?.id)
            selectedChapter = chapter
            newChapterTitle = ""
            newChapterSubtitle = ""
            try await loadSelectedChapter()
        }
    }

    func updateSelectedChapter(_ chapter: ChapterRecord) {
        selectedChapter = chapter
        if let index = chapters.firstIndex(where: { $0.id == chapter.id }) {
            chapters[index] = chapter
        }
        Task {
            do {
                try await repository?.updateChapter(chapter)
                statusMessage = "Chapter saved"
            } catch {
                report(error)
            }
        }
    }

    func moveSelectedChapter(delta: Int) async {
        guard let selectedChapter, let index = chapters.firstIndex(where: { $0.id == selectedChapter.id }) else { return }
        let target = index + delta
        guard chapters.indices.contains(target) else { return }
        chapters.swapAt(index, target)
        await runBusy("Reordering") {
            try await repository?.reorderChapters(chapters)
            if let project = selectedProject {
                chapters = try await repository?.chapters(projectId: project.id, volumeId: selectedVolume?.id) ?? chapters
            }
        }
    }

    func scheduleAutosave() {
        autosaveTask?.cancel()
        autosaveTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 700_000_000)
            guard !Task.isCancelled else { return }
            await self?.autosaveDraft()
        }
    }

    func autosaveDraft() async {
        guard let repository, let selectedChapter else { return }
        let body = draft
        do {
            draftPayload = try await repository.autosaveDraft(
                chapterId: selectedChapter.id,
                body: body,
                baseVersion: draftPayload.versionNumber
            )
            statusMessage = "Saved v\(draftPayload.versionNumber)"
        } catch {
            report(error)
        }
    }

    func saveDraftVersion() async {
        guard let repository, let selectedChapter else { return }
        await runBusy("Saving version") {
            draftPayload = try await repository.saveDraftVersion(
                chapterId: selectedChapter.id,
                body: draft,
                baseVersion: draftPayload.versionNumber,
                notes: "Manual BookMaker save."
            )
            statusMessage = "Saved v\(draftPayload.versionNumber)"
        }
    }

    func restore(version: DraftVersion) async {
        guard let repository, let selectedChapter else { return }
        await runBusy("Restoring") {
            draftPayload = try await repository.restoreDraftVersion(chapterId: selectedChapter.id, version: version.versionNumber)
            draft = draftPayload.body
        }
    }

    func viewPreviousBriefVersion() {
        var state = briefChatState
        let versions = state.orderedVersions
        guard let index = state.viewedIndex, index > 0 else { return }
        state.viewedVersionId = versions[index - 1].id
        briefChatState = state
    }

    func viewNextBriefVersion() {
        var state = briefChatState
        let versions = state.orderedVersions
        guard let index = state.viewedIndex, index < versions.count - 1 else { return }
        state.viewedVersionId = versions[index + 1].id
        briefChatState = state
    }

    func restoreViewedBriefVersion() async {
        guard let briefRepository, let project = selectedProject, let chapter = selectedChapter,
              let viewedVersion = briefChatState.viewedVersion, !briefChatState.isViewingLatest else { return }
        await runBusy("Restoring brief") {
            briefChatState = try await briefRepository.restoreVersion(
                projectId: project.id,
                chapter: chapter,
                version: viewedVersion
            )
            try await reloadSelectedChapterRecord(chapterId: chapter.id)
            statusMessage = "Restored brief v\(briefChatState.activeVersion?.versionNumber ?? 0)"
        }
    }

    func sendBriefMessage() async {
        guard let briefRepository, let project = selectedProject, let chapter = selectedChapter else { return }
        let text = briefComposerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let mediaRefs = briefComposerMediaRefs
        isBriefSending = true
        errorMessage = ""
        statusMessage = "Updating brief"
        defer { isBriefSending = false }

        do {
            guard let apiKey = try credentials.loadAPIKey()?.nilIfBlank else {
                throw BookMakerError.missingAPIKey
            }
            briefComposerText = ""
            briefComposerMediaRefs = []
            let userMessage = try await briefRepository.appendUserMessage(
                projectId: project.id,
                chapterId: chapter.id,
                text: text,
                mediaRefs: mediaRefs
            )
            briefChatState = try await briefRepository.state(projectId: project.id, chapter: chapter)

            let client = OpenAIResponsesClient(apiKey: apiKey)
            let currentState = briefChatState
            let activeBrief = currentState.activeVersion?.brief ?? currentState.seedBrief
            let turn = try await client.generateChapterBriefTurn(
                model: config.openAIModel,
                chapter: chapter,
                activeBrief: activeBrief,
                recentMessages: currentState.messages,
                draftExcerpt: excerpt(draft, limit: 12_000),
                writingSystem: project.metadata.writingSystem,
                userMessage: text
            )
            briefChatState = try await briefRepository.appendAssistantTurn(
                projectId: project.id,
                chapter: chapter,
                userMessage: userMessage,
                result: turn.result,
                model: turn.response.model,
                responseId: turn.response.responseId,
                usage: turn.response.usage
            )
            try await reloadSelectedChapterRecord(chapterId: chapter.id)
            statusMessage = "Brief v\(briefChatState.activeVersion?.versionNumber ?? 0)"
        } catch {
            report(error)
        }
    }

    func addBriefMediaRefs(_ refs: [String]) {
        let cleaned = refs
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        for ref in cleaned where !briefComposerMediaRefs.contains(ref) {
            briefComposerMediaRefs.append(ref)
        }
    }

    func removeBriefMediaRef(_ ref: String) {
        briefComposerMediaRefs.removeAll { $0 == ref }
    }

    func applyTerminalPreset(id: String) {
        selectedTerminalPresetId = id
        guard let preset = terminalPresets.first(where: { $0.id == id }) else { return }
        terminalCommand = preset.command
        terminalWorkingDirectory = BookMakerPathResolver.workingDirectory(
            for: preset.workingDirectoryMode,
            workspaceRoot: config.workspaceRoot,
            custom: terminalWorkingDirectory
        )
    }

    func runTerminalCommand() {
        guard terminalStatus != .running else { return }
        guard let command = terminalCommand.nilIfBlank else { return }
        let workingDirectory = BookMakerPathResolver.workspaceRoot(terminalWorkingDirectory.nilIfBlank ?? config.workspaceRoot)
        terminalCommand = command
        terminalWorkingDirectory = workingDirectory
        isTerminalPresented = true
        terminalStatus = .running
        terminalExitCode = nil
        appendTerminalOutput(.system, "$ \(command)\n")
        appendTerminalOutput(.system, "cd \(workingDirectory)\n")
        statusMessage = "Terminal running"

        terminalTask = Task { [weak self] in
            guard let self else { return }
            do {
                for try await event in shellRunner.run(command: command, workingDirectory: workingDirectory) {
                    handleTerminalEvent(event)
                }
            } catch {
                terminalStatus = .failed
                terminalExitCode = nil
                terminalTask = nil
                appendTerminalOutput(.stderr, "\(error.localizedDescription)\n")
                statusMessage = "Terminal failed"
            }
        }
    }

    func cancelTerminalCommand() {
        guard terminalStatus == .running else { return }
        appendTerminalOutput(.system, "Stopping command...\n")
        statusMessage = "Stopping terminal command"
        shellRunner.cancel()
    }

    func clearTerminalOutput() {
        terminalOutput = []
        if terminalStatus != .running {
            terminalExitCode = nil
            terminalStatus = .idle
        }
    }

    func openExternalTerminal() {
        do {
            try ShellCommandRunner.openExternalTerminal(at: terminalWorkingDirectory.nilIfBlank ?? config.workspaceRoot)
            statusMessage = "Opened Terminal"
        } catch {
            report(error)
        }
    }

    func compileBook(includeDrafts: Bool = true) async {
        guard let repository, let selectedProject else { return }
        await runBusy("Compiling") {
            compiledBook = try await repository.compiledBook(projectId: selectedProject.id, includeDrafts: includeDrafts)
            statusMessage = "Compiled \(compiledBook?.chapterCount ?? 0) chapters"
        }
    }

    func runRewrite(mode: String) async {
        guard let selectedChapter else { return }
        await runBusy("\(mode.capitalized)") {
            guard let apiKey = try credentials.loadAPIKey()?.nilIfBlank else {
                throw BookMakerError.missingAPIKey
            }
            let client = OpenAIResponsesClient(apiKey: apiKey)
            let packet = client.makeRewriteInput(mode: mode, chapterTitle: selectedChapter.title, body: draft)
            let result = try await client.generateText(
                model: config.openAIModel,
                instructions: packet.instructions,
                input: packet.input,
                verbosity: "medium"
            )
            draft = result.text
            statusMessage = "OpenAI \(mode) complete"
            await autosaveDraft()
        }
    }

    func renderBook() async {
        guard let repository, let selectedProject else { return }
        await runBusy("Rendering") {
            let result = try await RenderService().render(command: config.renderCommand, workspaceRoot: config.workspaceRoot)
            try await repository.recordRender(
                projectId: selectedProject.id,
                volumeId: selectedVolume?.id,
                outputPath: result.outputPath,
                logs: result.logs,
                status: result.status
            )
            statusMessage = "Render \(result.status)"
        }
    }

    private func runBusy(_ label: String, _ work: () async throws -> Void) async {
        isBusy = true
        errorMessage = ""
        statusMessage = label
        defer { isBusy = false }
        do {
            try await work()
        } catch {
            report(error)
        }
    }

    private func report(_ error: Error) {
        errorMessage = error.localizedDescription
        statusMessage = "Error"
    }

    private func refreshSelectedTerminalPreset() {
        if terminalPresets.contains(where: { $0.id == selectedTerminalPresetId }) {
            applyTerminalPreset(id: selectedTerminalPresetId)
        } else if let firstPreset = terminalPresets.first {
            applyTerminalPreset(id: firstPreset.id)
        }
    }

    private func handleTerminalEvent(_ event: ShellCommandEvent) {
        switch event {
        case .output(let stream, let text):
            appendTerminalOutput(stream, text)
        case .finished(let result):
            terminalStatus = result.status
            terminalExitCode = result.exitCode
            terminalTask = nil
            statusMessage = "Terminal \(result.status.label.lowercased())"
            if let exitCode = result.exitCode {
                appendTerminalOutput(.system, "Exit \(exitCode): \(result.status.label)\n")
            } else {
                appendTerminalOutput(.system, "\(result.status.label)\n")
            }
        }
    }

    private func appendTerminalOutput(_ stream: TerminalOutputStream, _ text: String) {
        guard !text.isEmpty else { return }
        terminalOutput.append(TerminalOutputChunk(stream: stream, text: text))
        if terminalOutput.count > 800 {
            terminalOutput.removeFirst(terminalOutput.count - 800)
        }
    }

    private func reloadSelectedChapterRecord(chapterId: UUID) async throws {
        guard let repository, let project = selectedProject else { return }
        chapters = try await repository.chapters(projectId: project.id, volumeId: selectedVolume?.id)
        if let refreshed = chapters.first(where: { $0.id == chapterId }) {
            selectedChapter = refreshed
        }
    }

    private func excerpt(_ value: String, limit: Int) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count > limit else { return trimmed }
        return String(trimmed.prefix(limit))
    }
}
