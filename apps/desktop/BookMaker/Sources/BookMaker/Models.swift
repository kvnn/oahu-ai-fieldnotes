import Foundation

enum ChapterStatus: String, Codable, CaseIterable, Identifiable {
    case draft
    case ready

    var id: String { rawValue }
    var label: String { self == .ready ? "Visible" : "Draft" }
}

enum ChapterForm: String, Codable, CaseIterable, Identifiable {
    case sceneToPrinciple = "scene_to_principle"
    case conceptFirst = "concept_first"
    case notebookMosaic = "notebook_mosaic"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .sceneToPrinciple:
            "Scene To Principle"
        case .conceptFirst:
            "Concept First"
        case .notebookMosaic:
            "Notebook Mosaic"
        }
    }
}

struct BookMakerMetadata: Codable, Hashable {
    var templateId: String?
    var writingSystem: String
    var voiceRules: [String]
    var chapterForms: [ChapterForm]
    var visualCadence: String
    var rubric: [String]

    static let empty = BookMakerMetadata(
        templateId: nil,
        writingSystem: "",
        voiceRules: [],
        chapterForms: [],
        visualCadence: "",
        rubric: []
    )
}

struct ProjectRecord: Identifiable, Hashable {
    var id: UUID
    var name: String
    var slug: String
    var description: String
    var status: String
    var metadata: BookMakerMetadata
}

struct VolumeRecord: Identifiable, Hashable {
    var id: UUID
    var projectId: UUID
    var title: String
    var subtitle: String
    var slug: String
    var status: String
    var metadata: BookMakerMetadata
}

struct ChapterRecord: Identifiable, Hashable {
    var id: UUID
    var projectId: UUID
    var volumeId: UUID?
    var title: String
    var subtitle: String
    var slug: String
    var sequenceOrder: Int
    var status: ChapterStatus
    var intendedPageCount: Int?
    var targetWordCount: Int?
    var situation: String
    var constraint: String
    var build: String
    var pattern: String
    var oahuLayer: String
    var fieldNote: String
    var nextBuild: String
    var metadata: ChapterMetadata

    var displayNumber: String {
        sequenceOrder > 0 ? String(sequenceOrder) : "-"
    }
}

struct ChapterMetadata: Codable, Hashable {
    var chapterForm: ChapterForm?
    var thesis: String
    var sourceCluster: [String]
    var pageRhythm: [String]
    var visualSlots: [String]
    var keyClaims: [String]
    var evaluationNotes: String

    static let empty = ChapterMetadata(
        chapterForm: nil,
        thesis: "",
        sourceCluster: [],
        pageRhythm: [],
        visualSlots: [],
        keyClaims: [],
        evaluationNotes: ""
    )
}

enum BriefMessageRole: String, Codable, CaseIterable, Identifiable {
    case user
    case assistant

    var id: String { rawValue }

    var label: String {
        switch self {
        case .user:
            "You"
        case .assistant:
            "BookMaker"
        }
    }
}

struct ChapterBriefMessage: Identifiable, Hashable {
    var id: UUID
    var projectId: UUID
    var chapterId: UUID
    var role: BriefMessageRole
    var text: String
    var mediaRefs: [String]
    var turnIndex: Int
    var createdAt: String
}

struct StructuredChapterBrief: Codable, Hashable {
    var chapterForm: ChapterForm
    var goal: String
    var reader: String
    var thesis: String
    var situation: String
    var constraint: String
    var build: String
    var pattern: String
    var fieldNote: String
    var nextBuild: String
    var sourceCluster: [String]
    var visualSlots: [String]
    var successCriteria: [String]
    var openQuestions: [String]
    var confidence0To1: Double

    static let blank = StructuredChapterBrief(
        chapterForm: .sceneToPrinciple,
        goal: "",
        reader: "Technically curious builder-reader",
        thesis: "",
        situation: "",
        constraint: "",
        build: "",
        pattern: "",
        fieldNote: "",
        nextBuild: "",
        sourceCluster: [],
        visualSlots: [],
        successCriteria: [],
        openQuestions: [],
        confidence0To1: 0
    )

    static func seed(from chapter: ChapterRecord) -> StructuredChapterBrief {
        let thesis = chapter.metadata.thesis.nilIfBlank ?? chapter.fieldNote.nilIfBlank ?? chapter.title
        let form = chapter.metadata.chapterForm ?? .sceneToPrinciple
        let criteria = chapter.metadata.keyClaims.isEmpty
            ? ["Clear chapter thesis", "Concrete source grounding", "Usable field note", "Print-ready visual rhythm"]
            : chapter.metadata.keyClaims
        let visualSlots = chapter.metadata.visualSlots.isEmpty
            ? ["Meaningful illustration, diagram, screenshot, or motif"]
            : chapter.metadata.visualSlots
        return StructuredChapterBrief(
            chapterForm: form,
            goal: thesis,
            reader: "Technically curious builder-reader",
            thesis: thesis,
            situation: chapter.situation,
            constraint: chapter.constraint,
            build: chapter.build,
            pattern: chapter.pattern,
            fieldNote: chapter.fieldNote.nilIfBlank ?? thesis,
            nextBuild: chapter.nextBuild,
            sourceCluster: chapter.metadata.sourceCluster,
            visualSlots: visualSlots,
            successCriteria: criteria,
            openQuestions: [],
            confidence0To1: chapter.metadata.thesis.nilIfBlank == nil ? 0.35 : 0.62
        )
    }

    func asChapterMetadata(existing: ChapterMetadata = .empty) -> ChapterMetadata {
        ChapterMetadata(
            chapterForm: chapterForm,
            thesis: thesis,
            sourceCluster: sourceCluster,
            pageRhythm: existing.pageRhythm,
            visualSlots: visualSlots,
            keyClaims: successCriteria,
            evaluationNotes: existing.evaluationNotes
        )
    }
}

struct ChapterBriefVersion: Identifiable, Hashable {
    var id: UUID
    var projectId: UUID
    var chapterId: UUID
    var versionNumber: Int
    var turnIndex: Int
    var brief: StructuredChapterBrief
    var changeSummary: String
    var modelProvider: String
    var modelName: String
    var responseId: String
    var usageJSON: String
    var createdAt: String
}

struct ChapterBriefChatState: Hashable {
    var seedBrief: StructuredChapterBrief
    var messages: [ChapterBriefMessage]
    var versions: [ChapterBriefVersion]
    var activeVersionId: UUID?
    var viewedVersionId: UUID?

    static func empty(seed: StructuredChapterBrief) -> ChapterBriefChatState {
        ChapterBriefChatState(
            seedBrief: seed,
            messages: [],
            versions: [],
            activeVersionId: nil,
            viewedVersionId: nil
        )
    }

    var orderedVersions: [ChapterBriefVersion] {
        versions.sorted {
            if $0.versionNumber == $1.versionNumber {
                return $0.createdAt < $1.createdAt
            }
            return $0.versionNumber < $1.versionNumber
        }
    }

    var activeVersion: ChapterBriefVersion? {
        if let activeVersionId, let version = orderedVersions.first(where: { $0.id == activeVersionId }) {
            return version
        }
        return orderedVersions.last
    }

    var viewedVersion: ChapterBriefVersion? {
        if let viewedVersionId, let version = orderedVersions.first(where: { $0.id == viewedVersionId }) {
            return version
        }
        return activeVersion
    }

    var displayedBrief: StructuredChapterBrief {
        viewedVersion?.brief ?? seedBrief
    }

    var viewedIndex: Int? {
        guard let viewedVersion else { return nil }
        return orderedVersions.firstIndex(where: { $0.id == viewedVersion.id })
    }

    var isViewingLatest: Bool {
        guard let activeVersion, let viewedVersion else { return true }
        return activeVersion.id == viewedVersion.id
    }

    var canViewPrevious: Bool {
        guard let viewedIndex else { return false }
        return viewedIndex > 0
    }

    var canViewNext: Bool {
        guard let viewedIndex else { return false }
        return viewedIndex < orderedVersions.count - 1
    }

    var versionLabel: String {
        guard let viewedIndex else { return "0/0" }
        return "\(viewedIndex + 1)/\(orderedVersions.count)"
    }
}

struct ChapterBriefTurnResult: Codable, Hashable {
    var assistantText: String
    var brief: StructuredChapterBrief
    var changeSummary: String
}

struct DraftPayload: Hashable {
    var draftId: UUID?
    var versionNumber: Int
    var body: String
    var source: String
    var versions: [DraftVersion]
}

struct DraftVersion: Identifiable, Hashable {
    var id: UUID
    var versionNumber: Int
    var updatedAt: String
    var editorNotes: String
}

struct SourceStats: Hashable {
    var sources: Int = 0
    var readyChunks: Int = 0
    var blockedChunks: Int = 0
    var needsReview: Int = 0
    var knowledgeNodes: Int = 0
}

struct RenderRecord: Identifiable, Hashable {
    var id: UUID
    var outputPath: String
    var status: String
    var renderedAt: String
    var logs: String
}

struct BookTemplate: Identifiable, Codable, Hashable {
    var id: String
    var name: String
    var subtitle: String
    var description: String
    var defaultVolumeTitle: String
    var defaultVolumeSubtitle: String
    var writingSystem: String
    var voiceRules: [String]
    var chapterForms: [ChapterForm]
    var visualCadence: String
    var rubric: [String]
    var starterChapters: [TemplateChapter]
}

struct TemplateChapter: Codable, Hashable {
    var title: String
    var subtitle: String
    var form: ChapterForm
    var thesis: String
    var body: String
}

struct CompiledBook: Hashable {
    var rawMarkdown: String
    var vivliostyleMarkdown: String
    var wordCount: Int
    var chapterCount: Int
}
