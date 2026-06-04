import Foundation

struct OpenAIUsage: Codable, Hashable {
    var inputTokens: Int?
    var outputTokens: Int?
    var totalTokens: Int?
}

struct OpenAITextResult: Hashable {
    var responseId: String
    var model: String
    var text: String
    var usage: OpenAIUsage
}

private struct OpenAIResponseBody: Codable {
    var id: String
    var model: String?
    var output: [OpenAIOutputItem]
    var usage: OpenAIUsage?
    var error: OpenAIErrorBody?
}

private struct OpenAIOutputItem: Codable {
    var type: String
    var content: [OpenAIContentItem]?
}

private struct OpenAIContentItem: Codable {
    var type: String
    var text: String?
    var refusal: String?
}

private struct OpenAIErrorBody: Codable {
    var message: String
}

struct OpenAIResponsesClient {
    var apiKey: String
    var endpoint = URL(string: "https://api.openai.com/v1/responses")!

    func generateText(model: String, instructions: String, input: String, verbosity: String = "medium") async throws -> OpenAITextResult {
        let body: [String: Any] = [
            "model": model,
            "store": false,
            "reasoning": ["effort": "low"],
            "text": ["verbosity": verbosity],
            "input": [
                [
                    "role": "system",
                    "content": [["type": "input_text", "text": instructions]]
                ],
                [
                    "role": "user",
                    "content": [["type": "input_text", "text": input]]
                ]
            ]
        ]
        return try await request(body: body, fallbackModel: model)
    }

    func generateStructuredText(model: String, instructions: String, input: String, schemaName: String, schema: [String: Any]) async throws -> OpenAITextResult {
        let body: [String: Any] = [
            "model": model,
            "store": false,
            "reasoning": ["effort": "low"],
            "text": [
                "verbosity": "medium",
                "format": [
                    "type": "json_schema",
                    "name": schemaName,
                    "strict": true,
                    "schema": schema
                ]
            ],
            "input": [
                [
                    "role": "system",
                    "content": [["type": "input_text", "text": instructions]]
                ],
                [
                    "role": "user",
                    "content": [["type": "input_text", "text": input]]
                ]
            ]
        ]
        return try await request(body: body, fallbackModel: model)
    }

    func makeRewriteInput(mode: String, chapterTitle: String, body: String) -> (instructions: String, input: String) {
        let instructions = """
        You are BookMaker, a field-note editor for source-grounded books. Preserve the writer's concrete artifacts, scene logic, and useful distinctions. Return only replacement Markdown.
        """
        let input = """
        Mode: \(mode)
        Chapter: \(chapterTitle)

        Markdown:
        \(body)
        """
        return (instructions, input)
    }

    func generateChapterBriefTurn(
        model: String,
        chapter: ChapterRecord,
        activeBrief: StructuredChapterBrief,
        recentMessages: [ChapterBriefMessage],
        draftExcerpt: String,
        writingSystem: String,
        userMessage: String
    ) async throws -> (result: ChapterBriefTurnResult, response: OpenAITextResult) {
        let packet = try makeChapterBriefTurnInput(
            chapter: chapter,
            activeBrief: activeBrief,
            recentMessages: recentMessages,
            draftExcerpt: draftExcerpt,
            writingSystem: writingSystem,
            userMessage: userMessage
        )
        let response = try await generateStructuredText(
            model: model,
            instructions: packet.instructions,
            input: packet.input,
            schemaName: "chapter_brief_turn",
            schema: try loadJSONSchema("Schemas/chapter_brief_turn.schema.json")
        )
        guard let data = response.text.data(using: .utf8) else {
            throw BookMakerError.invalidOpenAIResponse
        }
        do {
            let result = try JSONCoding.decoder.decode(ChapterBriefTurnResult.self, from: data)
            return (result, response)
        } catch {
            throw BookMakerError.processFailed("OpenAI brief JSON could not be decoded: \(error.localizedDescription)")
        }
    }

    func makeChapterBriefTurnInput(
        chapter: ChapterRecord,
        activeBrief: StructuredChapterBrief,
        recentMessages: [ChapterBriefMessage],
        draftExcerpt: String,
        writingSystem: String,
        userMessage: String
    ) throws -> (instructions: String, input: String) {
        let instructions = """
        You are BookMaker's chapter-brief editor. Use chat naturally, but treat the structured chapter brief as the product state.

        Return a conversational assistant_text and a complete replacement brief. Do not return a patch. Preserve concrete scene/source grounding, keep uncertainty in open_questions, and avoid generic futurism or hype cadence. The brief is for downstream chapter drafting, not for publication prose.
        """
        let activeBriefJSON = try prettyJSONString(activeBrief)
        let messagesJSON = try prettyJSONString(recentMessages.suffix(12).map(BriefPromptMessage.init(message:)))
        let input = """
        Writing system:
        \(writingSystem.nilIfBlank ?? "Field-note witness for a technically curious builder-reader.")

        Chapter:
        Title: \(chapter.title)
        Subtitle: \(chapter.subtitle)
        Current form: \((chapter.metadata.chapterForm ?? .sceneToPrinciple).rawValue)

        Current canonical brief:
        \(activeBriefJSON)

        Recent chat:
        \(messagesJSON)

        Current draft excerpt:
        \(draftExcerpt.nilIfBlank ?? "(No draft prose yet.)")

        New user message:
        \(userMessage)
        """
        return (instructions, input)
    }

    private func request(body: [String: Any], fallbackModel: String) async throws -> OpenAITextResult {
        let requestData = try JSONSerialization.data(withJSONObject: body)
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.httpBody = requestData

        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let bodyText = String(data: data, encoding: .utf8) ?? ""
            throw BookMakerError.processFailed("OpenAI request failed (\(status)): \(bodyText)")
        }
        let decoded = try JSONCoding.decoder.decode(OpenAIResponseBody.self, from: data)
        if let error = decoded.error {
            throw BookMakerError.processFailed(error.message)
        }
        return OpenAITextResult(
            responseId: decoded.id,
            model: decoded.model ?? fallbackModel,
            text: try outputText(from: decoded),
            usage: decoded.usage ?? OpenAIUsage(inputTokens: 0, outputTokens: 0, totalTokens: 0)
        )
    }

    private func outputText(from response: OpenAIResponseBody) throws -> String {
        var parts: [String] = []
        for item in response.output where item.type == "message" {
            for content in item.content ?? [] {
                if let refusal = content.refusal {
                    throw BookMakerError.processFailed(refusal)
                }
                if let text = content.text {
                    parts.append(text)
                }
            }
        }
        let text = parts.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw BookMakerError.invalidOpenAIResponse }
        return text
    }

    private func loadJSONSchema(_ path: String) throws -> [String: Any] {
        let data = try Data(contentsOf: packagedResourceURL(path))
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw BookMakerError.missingResource(path)
        }
        return object
    }

    private func prettyJSONString<T: Encodable>(_ value: T) throws -> String {
        let data = try JSONCoding.prettyEncoder.encode(value)
        return String(data: data, encoding: .utf8) ?? "{}"
    }
}

private struct BriefPromptMessage: Encodable {
    var role: String
    var text: String
    var mediaRefs: [String]
    var turnIndex: Int

    init(message: ChapterBriefMessage) {
        role = message.role.rawValue
        text = message.text
        mediaRefs = message.mediaRefs
        turnIndex = message.turnIndex
    }
}
