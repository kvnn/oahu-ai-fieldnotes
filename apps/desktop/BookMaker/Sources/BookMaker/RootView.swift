import SwiftUI

private enum InspectorTab: String, CaseIterable, Identifiable {
    case brief = "Brief"
    case details = "Details"
    case drafts = "Drafts"

    var id: String { rawValue }
}

struct RootView: View {
    @ObservedObject var model: AppModel
    @State private var inspectorTab: InspectorTab = .brief

    var body: some View {
        ZStack {
            HStack(spacing: 0) {
                projectRail
                Divider()
                chapterRail
                Divider()
                editorPane
                Divider()
                inspectorPane
            }
            .background(BookMakerColor.room)

            if model.isConfigPresented {
                ConfigSheet(model: model)
                    .transition(.opacity)
            }
        }
        .alert("BookMaker", isPresented: Binding(
            get: { !model.errorMessage.isEmpty },
            set: { if !$0 { model.errorMessage = "" } }
        )) {
            Button("OK") { model.errorMessage = "" }
        } message: {
            Text(model.errorMessage)
        }
    }

    private var projectRail: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("BookMaker")
                        .font(BookMakerType.title(20))
                        .foregroundStyle(BookMakerColor.paper)
                    Text(model.apiKeySource.rawValue)
                        .font(BookMakerType.mono(10))
                        .foregroundStyle(BookMakerColor.muted)
                }
                Spacer()
                Button {
                    model.isConfigPresented = true
                } label: {
                    Image(systemName: "gearshape")
                }
                .buttonStyle(IconButtonStyle())
                .help("Settings")
            }

            HStack {
                TextField("New book", text: $model.newBookName)
                    .textFieldStyle(.roundedBorder)
                Button {
                    Task { await model.createBook() }
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(IconButtonStyle())
                .disabled(model.repositoryUnavailable)
                .help("Create Book")
            }

            if let template = model.selectedTemplate {
                Text(template.name)
                    .font(BookMakerType.interface(11, weight: .semibold))
                    .foregroundStyle(BookMakerColor.gold)
                    .lineLimit(2)
            }

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(model.projects) { project in
                        Button {
                            model.selectProject(project)
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(project.name)
                                    .font(BookMakerType.interface(13, weight: .semibold))
                                    .foregroundStyle(BookMakerColor.paper)
                                    .lineLimit(2)
                                Text(project.slug)
                                    .font(BookMakerType.mono(10))
                                    .foregroundStyle(BookMakerColor.muted)
                                    .lineLimit(1)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10)
                            .background(
                                RoundedRectangle(cornerRadius: 7)
                                    .fill(project.id == model.selectedProject?.id ? BookMakerColor.cardSelected : BookMakerColor.card)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Spacer()

            VStack(alignment: .leading, spacing: 5) {
                statRow("Sources", model.sourceStats.sources)
                statRow("Ready", model.sourceStats.readyChunks)
                statRow("Blocked", model.sourceStats.blockedChunks)
                statRow("Review", model.sourceStats.needsReview)
                statRow("Nodes", model.sourceStats.knowledgeNodes)
            }
            .padding(10)
            .background(BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))
        }
        .padding(14)
        .frame(width: 270)
        .background(BookMakerColor.sidebar)
    }

    private var chapterRail: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Chapters")
                    .font(BookMakerType.interface(13, weight: .semibold))
                    .foregroundStyle(BookMakerColor.paper)
                Spacer()
                Button {
                    Task { await model.moveSelectedChapter(delta: -1) }
                } label: { Image(systemName: "arrow.up") }
                    .buttonStyle(IconButtonStyle())
                    .help("Move Up")
                Button {
                    Task { await model.moveSelectedChapter(delta: 1) }
                } label: { Image(systemName: "arrow.down") }
                    .buttonStyle(IconButtonStyle())
                    .help("Move Down")
            }

            VStack(spacing: 8) {
                TextField("Title", text: $model.newChapterTitle)
                    .textFieldStyle(.roundedBorder)
                TextField("Subtitle", text: $model.newChapterSubtitle)
                    .textFieldStyle(.roundedBorder)
                Button {
                    Task { await model.createChapter() }
                } label: {
                    Label("Add Chapter", systemImage: "plus")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(!model.canUseWorkspace)
            }

            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(model.chapters) { chapter in
                        Button {
                            model.selectChapter(chapter)
                        } label: {
                            HStack(alignment: .top, spacing: 10) {
                                Text(chapter.displayNumber)
                                    .font(BookMakerType.mono(11))
                                    .foregroundStyle(BookMakerColor.gold)
                                    .frame(width: 22, alignment: .leading)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(chapter.title)
                                        .font(BookMakerType.interface(13, weight: .semibold))
                                        .foregroundStyle(BookMakerColor.paper)
                                        .lineLimit(2)
                                    if !chapter.subtitle.isEmpty {
                                        Text(chapter.subtitle)
                                            .font(BookMakerType.interface(11))
                                            .foregroundStyle(BookMakerColor.muted)
                                            .lineLimit(2)
                                    }
                                    Text(chapter.status.label)
                                        .font(BookMakerType.mono(10))
                                        .foregroundStyle(chapter.status == .ready ? BookMakerColor.olive : BookMakerColor.muted)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10)
                            .background(
                                RoundedRectangle(cornerRadius: 7)
                                    .fill(chapter.id == model.selectedChapter?.id ? BookMakerColor.cardSelected : BookMakerColor.card)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(14)
        .frame(width: 310)
        .background(BookMakerColor.rail)
    }

    private var editorPane: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(model.selectedChapter?.title ?? "No chapter selected")
                        .font(BookMakerType.title(22))
                        .foregroundStyle(BookMakerColor.ink)
                        .lineLimit(1)
                    Text("v\(model.draftPayload.versionNumber) / \(ManuscriptCompiler.wordCount(model.draft)) words")
                        .font(BookMakerType.mono(11))
                        .foregroundStyle(BookMakerColor.inkMuted)
                }
                Spacer()
                Button {
                    Task { await model.runRewrite(mode: "simplify") }
                } label: { Label("Simplify", systemImage: "wand.and.stars") }
                    .buttonStyle(SecondaryLightButtonStyle())
                    .disabled(model.selectedChapter == nil)
                Button {
                    Task { await model.runRewrite(mode: "expand") }
                } label: { Label("Expand", systemImage: "arrow.up.left.and.arrow.down.right") }
                    .buttonStyle(SecondaryLightButtonStyle())
                    .disabled(model.selectedChapter == nil)
                Button {
                    Task { await model.saveDraftVersion() }
                } label: { Label("Save", systemImage: "tray.and.arrow.down") }
                    .buttonStyle(PrimaryLightButtonStyle())
                    .disabled(model.selectedChapter == nil)
            }

            TextEditor(text: $model.draft)
                .font(.system(size: 15, design: .serif))
                .foregroundStyle(BookMakerColor.ink)
                .scrollContentBackground(.hidden)
                .padding(12)
                .background(BookMakerColor.paper, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(BookMakerColor.paperRule))
                .onChange(of: model.draft) { _, _ in
                    model.scheduleAutosave()
                }

            if model.isTerminalPresented {
                terminalDrawer
            }

            HStack {
                Text(model.statusMessage)
                    .font(BookMakerType.interface(12))
                    .foregroundStyle(BookMakerColor.inkMuted)
                Spacer()
                if model.isBusy {
                    ProgressView()
                        .controlSize(.small)
                }
                Button {
                    model.isTerminalPresented.toggle()
                } label: {
                    Label("Terminal", systemImage: "terminal")
                }
                .buttonStyle(SecondaryLightButtonStyle())
                Button {
                    Task { await model.compileBook(includeDrafts: true) }
                } label: { Label("Compile", systemImage: "doc.text") }
                    .buttonStyle(SecondaryLightButtonStyle())
                Button {
                    Task { await model.renderBook() }
                } label: { Label("Render", systemImage: "printer") }
                    .buttonStyle(SecondaryLightButtonStyle())
            }
        }
        .padding(16)
        .background(BookMakerColor.paperWell)
    }

    private var terminalDrawer: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 10) {
                Label("Terminal", systemImage: "terminal")
                    .font(BookMakerType.interface(12, weight: .semibold))
                    .foregroundStyle(BookMakerColor.paper)

                Text(model.terminalStatusSummary)
                    .font(BookMakerType.mono(10, weight: .semibold))
                    .foregroundStyle(terminalStatusColor(model.terminalStatus))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(BookMakerColor.card, in: Capsule())

                Spacer()

                Picker("Preset", selection: Binding(
                    get: { model.selectedTerminalPresetId },
                    set: { model.applyTerminalPreset(id: $0) }
                )) {
                    ForEach(model.terminalPresets) { preset in
                        Text(preset.label).tag(preset.id)
                    }
                }
                .frame(width: 190)
            }

            HStack(spacing: 8) {
                Text("cd")
                    .font(BookMakerType.mono(11, weight: .semibold))
                    .foregroundStyle(BookMakerColor.muted)
                TextField("Working directory", text: $model.terminalWorkingDirectory)
                    .font(BookMakerType.mono(11))
                    .textFieldStyle(.roundedBorder)
            }

            HStack(spacing: 8) {
                TextField("Command", text: $model.terminalCommand)
                    .font(BookMakerType.mono(12))
                    .textFieldStyle(.roundedBorder)
                    .onSubmit {
                        model.runTerminalCommand()
                    }

                Button {
                    model.runTerminalCommand()
                } label: {
                    Label("Run", systemImage: "play.fill")
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(!model.canRunTerminalCommand)

                Button {
                    model.cancelTerminalCommand()
                } label: {
                    Label("Stop", systemImage: "stop.fill")
                }
                .buttonStyle(SecondaryDarkButtonStyle())
                .disabled(model.terminalStatus != .running)

                Button {
                    model.clearTerminalOutput()
                } label: {
                    Label("Clear", systemImage: "trash")
                }
                .buttonStyle(SecondaryDarkButtonStyle())

                Button {
                    model.openExternalTerminal()
                } label: {
                    Label("Open", systemImage: "arrow.up.forward.app")
                }
                .buttonStyle(SecondaryDarkButtonStyle())
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 3) {
                        if model.terminalOutput.isEmpty {
                            Text("No command output yet.")
                                .font(BookMakerType.mono(11))
                                .foregroundStyle(BookMakerColor.muted)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(8)
                        } else {
                            ForEach(model.terminalOutput) { chunk in
                                terminalChunkRow(chunk)
                                    .id(chunk.id)
                            }
                        }
                    }
                    .padding(8)
                }
                .frame(minHeight: 120, maxHeight: 210)
                .background(BookMakerColor.room, in: RoundedRectangle(cornerRadius: 7))
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(BookMakerColor.cardSelected.opacity(0.6)))
                .onChange(of: model.terminalOutput.last?.id) { _, id in
                    if let id {
                        proxy.scrollTo(id, anchor: .bottom)
                    }
                }
            }
        }
        .padding(10)
        .background(BookMakerColor.sidebar, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(BookMakerColor.cardSelected.opacity(0.7)))
    }

    private var inspectorPane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Picker("Inspector", selection: $inspectorTab) {
                    ForEach(InspectorTab.allCases) { tab in
                        Text(tab.rawValue).tag(tab)
                    }
                }
                .pickerStyle(.segmented)

                if model.selectedChapter == nil {
                    Text("Select or create a chapter.")
                        .font(BookMakerType.interface(12))
                        .foregroundStyle(BookMakerColor.muted)
                } else {
                    switch inspectorTab {
                    case .brief:
                        briefInspector
                    case .details:
                        detailsInspector
                    case .drafts:
                        draftsInspector
                    }
                }
            }
            .padding(14)
        }
        .frame(width: 340)
        .background(BookMakerColor.sidebar)
    }

    private var briefInspector: some View {
        VStack(alignment: .leading, spacing: 14) {
            let state = model.briefChatState
            let brief = state.displayedBrief

            GroupBox("Current Brief") {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(brief.chapterForm.label)
                            .font(BookMakerType.mono(10, weight: .semibold))
                            .foregroundStyle(BookMakerColor.ink)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(BookMakerColor.gold, in: Capsule())
                        Spacer()
                        Text("\(Int((brief.confidence0To1 * 100).rounded()))%")
                            .font(BookMakerType.mono(11, weight: .semibold))
                            .foregroundStyle(BookMakerColor.paper)
                    }

                    briefField("Goal", brief.goal)
                    briefField("Thesis", brief.thesis)
                    briefField("Field Note", brief.fieldNote)

                    if !brief.openQuestions.isEmpty {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Open Questions")
                                .font(BookMakerType.interface(11, weight: .semibold))
                                .foregroundStyle(BookMakerColor.muted)
                            ForEach(brief.openQuestions, id: \.self) { question in
                                Text(question)
                                    .font(BookMakerType.interface(12))
                                    .foregroundStyle(BookMakerColor.paper)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }

                    HStack(spacing: 8) {
                        Button {
                            model.viewPreviousBriefVersion()
                        } label: {
                            Image(systemName: "chevron.left")
                        }
                        .buttonStyle(IconButtonStyle())
                        .disabled(!state.canViewPrevious)
                        .help("Previous Brief Version")

                        Text(state.versionLabel)
                            .font(BookMakerType.mono(11, weight: .semibold))
                            .foregroundStyle(BookMakerColor.paper)

                        Button {
                            model.viewNextBriefVersion()
                        } label: {
                            Image(systemName: "chevron.right")
                        }
                        .buttonStyle(IconButtonStyle())
                        .disabled(!state.canViewNext)
                        .help("Next Brief Version")

                        Spacer()

                        if !state.isViewingLatest {
                            Button {
                                Task { await model.restoreViewedBriefVersion() }
                            } label: {
                                Label("Restore", systemImage: "arrow.uturn.backward")
                            }
                            .buttonStyle(PrimaryButtonStyle())
                        }
                    }
                }
            }

            GroupBox("Chat") {
                VStack(alignment: .leading, spacing: 10) {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 8) {
                            if model.briefChatState.messages.isEmpty {
                                Text("No brief chat yet.")
                                    .font(BookMakerType.interface(12))
                                    .foregroundStyle(BookMakerColor.muted)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            } else {
                                ForEach(model.briefChatState.messages) { message in
                                    briefMessageBubble(message)
                                }
                            }
                        }
                    }
                    .frame(minHeight: 170, maxHeight: 260)

                    if !model.briefComposerMediaRefs.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(model.briefComposerMediaRefs, id: \.self) { ref in
                                HStack(spacing: 6) {
                                    Image(systemName: "paperclip")
                                    Text(mediaRefLabel(ref))
                                        .lineLimit(1)
                                    Spacer()
                                    Button {
                                        model.removeBriefMediaRef(ref)
                                    } label: {
                                        Image(systemName: "xmark")
                                    }
                                    .buttonStyle(IconButtonStyle())
                                    .help("Remove")
                                }
                                .font(BookMakerType.interface(11))
                                .foregroundStyle(BookMakerColor.paper)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(BookMakerColor.cardSelected, in: RoundedRectangle(cornerRadius: 7))
                            }
                        }
                    }

                    TextEditor(text: $model.briefComposerText)
                        .font(BookMakerType.interface(12))
                        .frame(height: 82)
                        .scrollContentBackground(.hidden)
                        .padding(6)
                        .background(BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))

                    HStack {
                        if model.isBriefSending {
                            ProgressView()
                                .controlSize(.small)
                        }
                        Spacer()
                        Button {
                            Task { await model.sendBriefMessage() }
                        } label: {
                            Label("Send", systemImage: "paperplane.fill")
                        }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(model.isBriefSending || model.briefComposerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
                .dropDestination(for: URL.self) { urls, _ in
                    model.addBriefMediaRefs(urls.map { $0.isFileURL ? $0.path : $0.absoluteString })
                    return true
                }
                .dropDestination(for: String.self) { values, _ in
                    model.addBriefMediaRefs(values)
                    return true
                }
            }
        }
    }

    private var detailsInspector: some View {
        VStack(alignment: .leading, spacing: 14) {
            if var chapter = model.selectedChapter {
                GroupBox("Chapter") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("Title", text: binding(for: chapter.title) { chapter.title = $0; model.updateSelectedChapter(chapter) })
                        TextField("Subtitle", text: binding(for: chapter.subtitle) { chapter.subtitle = $0; model.updateSelectedChapter(chapter) })
                        Picker("Status", selection: binding(for: chapter.status) { chapter.status = $0; model.updateSelectedChapter(chapter) }) {
                            ForEach(ChapterStatus.allCases) { status in
                                Text(status.label).tag(status)
                            }
                        }
                        Picker("Form", selection: binding(for: chapter.metadata.chapterForm ?? .sceneToPrinciple) {
                            chapter.metadata.chapterForm = $0
                            model.updateSelectedChapter(chapter)
                        }) {
                            ForEach(ChapterForm.allCases) { form in
                                Text(form.label).tag(form)
                            }
                        }
                    }
                }

                GroupBox("Brief Fields") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextArea(label: "Thesis", value: binding(for: chapter.metadata.thesis) {
                            chapter.metadata.thesis = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Situation", value: binding(for: chapter.situation) {
                            chapter.situation = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Constraint", value: binding(for: chapter.constraint) {
                            chapter.constraint = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Build", value: binding(for: chapter.build) {
                            chapter.build = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Pattern", value: binding(for: chapter.pattern) {
                            chapter.pattern = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Field Note", value: binding(for: chapter.fieldNote) {
                            chapter.fieldNote = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Next Build", value: binding(for: chapter.nextBuild) {
                            chapter.nextBuild = $0
                            model.updateSelectedChapter(chapter)
                        })
                        TextArea(label: "Evaluation", value: binding(for: chapter.metadata.evaluationNotes) {
                            chapter.metadata.evaluationNotes = $0
                            model.updateSelectedChapter(chapter)
                        })
                    }
                }
            }
        }
    }

    private var draftsInspector: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Draft Versions") {
                VStack(spacing: 6) {
                    ForEach(model.draftPayload.versions) { version in
                        HStack {
                            VStack(alignment: .leading) {
                                Text("v\(version.versionNumber)")
                                    .font(BookMakerType.interface(12, weight: .semibold))
                                    .foregroundStyle(BookMakerColor.paper)
                                Text(version.editorNotes)
                                    .font(BookMakerType.interface(10))
                                    .foregroundStyle(BookMakerColor.muted)
                                    .lineLimit(1)
                            }
                            Spacer()
                            Button {
                                Task { await model.restore(version: version) }
                            } label: {
                                Image(systemName: "arrow.uturn.backward")
                            }
                            .buttonStyle(IconButtonStyle())
                            .help("Restore")
                        }
                        .padding(8)
                        .background(BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))
                    }
                }
            }

            if let compiled = model.compiledBook {
                GroupBox("Compiled Book") {
                    VStack(alignment: .leading, spacing: 6) {
                        statRow("Chapters", compiled.chapterCount)
                        statRow("Words", compiled.wordCount)
                        TextEditor(text: .constant(compiled.rawMarkdown))
                            .font(BookMakerType.mono(11))
                            .frame(minHeight: 180)
                    }
                }
            }
        }
    }

    private func briefField(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(BookMakerType.interface(11, weight: .semibold))
                .foregroundStyle(BookMakerColor.muted)
            Text(value.nilIfBlank ?? "-")
                .font(BookMakerType.interface(12))
                .foregroundStyle(BookMakerColor.paper)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func briefMessageBubble(_ message: ChapterBriefMessage) -> some View {
        let isUser = message.role == .user
        return HStack {
            if isUser { Spacer(minLength: 24) }
            VStack(alignment: .leading, spacing: 4) {
                Text(message.role.label)
                    .font(BookMakerType.mono(10, weight: .semibold))
                    .foregroundStyle(isUser ? BookMakerColor.gold : BookMakerColor.olive)
                Text(message.text)
                    .font(BookMakerType.interface(12))
                    .foregroundStyle(BookMakerColor.paper)
                    .fixedSize(horizontal: false, vertical: true)
                if !message.mediaRefs.isEmpty {
                    ForEach(message.mediaRefs, id: \.self) { ref in
                        HStack(spacing: 5) {
                            Image(systemName: "paperclip")
                            Text(mediaRefLabel(ref))
                                .lineLimit(1)
                        }
                        .font(BookMakerType.mono(10))
                        .foregroundStyle(BookMakerColor.muted)
                    }
                }
            }
            .padding(8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(isUser ? BookMakerColor.cardSelected : BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))
            if !isUser { Spacer(minLength: 24) }
        }
    }

    private func mediaRefLabel(_ ref: String) -> String {
        if let url = URL(string: ref), let last = url.lastPathComponent.nilIfBlank {
            return last
        }
        return (ref as NSString).lastPathComponent.nilIfBlank ?? ref
    }

    private func terminalChunkRow(_ chunk: TerminalOutputChunk) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(chunk.stream.label)
                .font(BookMakerType.mono(10, weight: .semibold))
                .foregroundStyle(terminalStreamColor(chunk.stream))
                .frame(width: 28, alignment: .leading)
            Text(chunk.text)
                .font(BookMakerType.mono(11))
                .foregroundStyle(terminalStreamColor(chunk.stream))
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func terminalStatusColor(_ status: TerminalRunStatus) -> Color {
        switch status {
        case .idle:
            BookMakerColor.muted
        case .running:
            BookMakerColor.gold
        case .succeeded:
            BookMakerColor.olive
        case .failed:
            BookMakerColor.danger
        case .cancelled:
            BookMakerColor.muted
        }
    }

    private func terminalStreamColor(_ stream: TerminalOutputStream) -> Color {
        switch stream {
        case .stdout:
            BookMakerColor.paper
        case .stderr:
            BookMakerColor.danger
        case .system:
            BookMakerColor.gold
        }
    }

    private func statRow(_ label: String, _ value: Int) -> some View {
        HStack {
            Text(label)
                .font(BookMakerType.interface(11))
                .foregroundStyle(BookMakerColor.muted)
            Spacer()
            Text(String(value))
                .font(BookMakerType.mono(11))
                .foregroundStyle(BookMakerColor.paper)
        }
    }

    private func binding<T>(for value: T, update: @escaping (T) -> Void) -> Binding<T> {
        Binding(get: { value }, set: update)
    }
}

private extension AppModel {
    var repositoryUnavailable: Bool {
        !canUseWorkspace && projects.isEmpty
    }
}

struct ConfigSheet: View {
    @ObservedObject var model: AppModel
    @State private var apiKey = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Configuration")
                    .font(BookMakerType.title(24))
                    .foregroundStyle(BookMakerColor.paper)
                Spacer()
                Button {
                    model.isConfigPresented = false
                } label: { Image(systemName: "xmark") }
                    .buttonStyle(IconButtonStyle())
            }

            VStack(alignment: .leading, spacing: 10) {
                TextField("DB_URL", text: $model.config.databaseURL)
                    .textFieldStyle(.roundedBorder)
                SecureField("OpenAI API Key", text: $apiKey)
                    .textFieldStyle(.roundedBorder)
                TextField("OpenAI Model", text: $model.config.openAIModel)
                    .textFieldStyle(.roundedBorder)
                TextField("Workspace Root", text: $model.config.workspaceRoot)
                    .textFieldStyle(.roundedBorder)
                TextField("Render Command", text: $model.config.renderCommand)
                    .textFieldStyle(.roundedBorder)
                Picker("Default Template", selection: $model.config.defaultTemplateID) {
                    ForEach(model.templates) { template in
                        Text(template.name).tag(template.id)
                    }
                }
            }

            HStack {
                Text("API key: \(model.apiKeySource.rawValue)")
                    .font(BookMakerType.interface(12))
                    .foregroundStyle(BookMakerColor.muted)
                Spacer()
                Button("Save & Connect") {
                    Task { await model.saveConfig(apiKey: apiKey.nilIfBlank) }
                }
                .buttonStyle(PrimaryButtonStyle())
            }
        }
        .padding(18)
        .frame(width: 560)
        .background(BookMakerColor.sidebar, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(BookMakerColor.gold.opacity(0.6)))
        .shadow(radius: 18)
    }
}

struct TextArea: View {
    var label: String
    @Binding var value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label)
                .font(BookMakerType.interface(11, weight: .semibold))
                .foregroundStyle(BookMakerColor.muted)
            TextEditor(text: $value)
                .font(BookMakerType.interface(12))
                .frame(minHeight: 76)
                .scrollContentBackground(.hidden)
                .padding(6)
                .background(BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))
        }
    }
}

enum BookMakerColor {
    static let room = Color(red: 0.08, green: 0.08, blue: 0.07)
    static let sidebar = Color(red: 0.11, green: 0.10, blue: 0.09)
    static let rail = Color(red: 0.14, green: 0.13, blue: 0.11)
    static let card = Color(red: 0.19, green: 0.17, blue: 0.14)
    static let cardSelected = Color(red: 0.29, green: 0.22, blue: 0.12)
    static let paper = Color(red: 0.94, green: 0.89, blue: 0.80)
    static let paperWell = Color(red: 0.86, green: 0.80, blue: 0.69)
    static let paperRule = Color(red: 0.67, green: 0.58, blue: 0.43)
    static let ink = Color(red: 0.10, green: 0.08, blue: 0.06)
    static let inkMuted = Color(red: 0.34, green: 0.29, blue: 0.22)
    static let muted = Color(red: 0.62, green: 0.58, blue: 0.50)
    static let gold = Color(red: 0.75, green: 0.57, blue: 0.22)
    static let olive = Color(red: 0.56, green: 0.65, blue: 0.40)
    static let danger = Color(red: 0.86, green: 0.33, blue: 0.27)
}

enum BookMakerType {
    static func title(_ size: CGFloat) -> Font {
        .system(size: size, weight: .semibold, design: .serif)
    }

    static func interface(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .default)
    }

    static func mono(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(BookMakerType.interface(13, weight: .semibold))
            .foregroundStyle(BookMakerColor.ink)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(configuration.isPressed ? BookMakerColor.paper : BookMakerColor.gold, in: RoundedRectangle(cornerRadius: 7))
            .opacity(isEnabled ? 1 : 0.45)
    }
}

struct PrimaryLightButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(BookMakerType.interface(12, weight: .semibold))
            .foregroundStyle(BookMakerColor.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(configuration.isPressed ? BookMakerColor.paperRule : BookMakerColor.gold, in: RoundedRectangle(cornerRadius: 7))
            .opacity(isEnabled ? 1 : 0.45)
    }
}

struct SecondaryLightButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(BookMakerType.interface(12, weight: .semibold))
            .foregroundStyle(BookMakerColor.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(configuration.isPressed ? BookMakerColor.paperRule.opacity(0.55) : Color.clear, in: RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(BookMakerColor.paperRule))
            .opacity(isEnabled ? 1 : 0.45)
    }
}

struct SecondaryDarkButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(BookMakerType.interface(12, weight: .semibold))
            .foregroundStyle(BookMakerColor.paper)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(configuration.isPressed ? BookMakerColor.cardSelected : BookMakerColor.card, in: RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(BookMakerColor.cardSelected.opacity(0.7)))
            .opacity(isEnabled ? 1 : 0.45)
    }
}

struct IconButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(BookMakerType.interface(12, weight: .semibold))
            .foregroundStyle(configuration.isPressed ? BookMakerColor.gold : BookMakerColor.paper)
            .padding(6)
            .background(configuration.isPressed ? BookMakerColor.card : Color.clear, in: RoundedRectangle(cornerRadius: 6))
            .opacity(isEnabled ? 1 : 0.45)
    }
}
