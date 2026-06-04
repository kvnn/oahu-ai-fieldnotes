import Foundation

enum APIKeySource: String, Codable {
    case keychain = "Keychain"
    case environment = "Environment"
    case missing = "Missing"
}

struct BookMakerConfig: Codable, Equatable {
    var databaseURL: String
    var openAIModel: String
    var workspaceRoot: String
    var renderCommand: String
    var defaultTemplateID: String

    static let defaultValue = BookMakerConfig(
        databaseURL: "",
        openAIModel: "gpt-5.5",
        workspaceRoot: FileManager.default.currentDirectoryPath,
        renderCommand: "npm run build:print",
        defaultTemplateID: "field-notes-essay"
    )
}

@MainActor
final class ConfigStore: ObservableObject {
    @Published var config: BookMakerConfig

    let configURL: URL

    init(configURL: URL = bookMakerApplicationSupportDirectory().appendingPathComponent("config.json")) {
        self.configURL = configURL
        if let data = try? Data(contentsOf: configURL),
           let loaded = try? JSONCoding.decoder.decode(BookMakerConfig.self, from: data) {
            config = loaded
        } else {
            config = .defaultValue
        }
    }

    func save() throws {
        try ensureDirectory(configURL.deletingLastPathComponent())
        let data = try JSONCoding.prettyEncoder.encode(config)
        try data.write(to: configURL, options: [.atomic])
    }
}

