import CryptoKit
import Foundation

enum BookMakerError: LocalizedError {
    case invalidDatabaseURL(String)
    case unsupportedDatabase(String)
    case database(String)
    case missingSelection
    case missingAPIKey
    case invalidOpenAIResponse
    case processFailed(String)
    case missingResource(String)

    var errorDescription: String? {
        switch self {
        case .invalidDatabaseURL(let value):
            "Invalid DB_URL: \(value)"
        case .unsupportedDatabase(let value):
            "Unsupported database URL: \(value)"
        case .database(let value):
            value
        case .missingSelection:
            "Select a book and chapter first."
        case .missingAPIKey:
            "OpenAI API key is not configured."
        case .invalidOpenAIResponse:
            "OpenAI returned a response BookMaker could not read."
        case .processFailed(let value):
            value
        case .missingResource(let value):
            "Missing resource: \(value)"
        }
    }
}

enum DateCoding {
    static func string(from date: Date = Date()) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }
}

enum JSONCoding {
    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    static let prettyEncoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
}

func stableSlug(_ value: String, fallback: String = "item") -> String {
    let lowered = value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    let allowed = CharacterSet.alphanumerics
    var scalars: [UnicodeScalar] = []
    var previousDash = false

    for scalar in lowered.unicodeScalars {
        if allowed.contains(scalar) {
            scalars.append(scalar)
            previousDash = false
        } else if !previousDash {
            scalars.append("-")
            previousDash = true
        }
    }

    let slug = String(String.UnicodeScalarView(scalars))
        .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
    return slug.isEmpty ? fallback : slug
}

func sha256Hex(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

extension UUID {
    var sqlalchemySQLiteString: String {
        uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    }

    init(bookMakerDatabaseString value: String) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if let uuid = UUID(uuidString: trimmed) {
            self = uuid
            return
        }
        guard trimmed.count == 32 else {
            throw BookMakerError.database("Invalid UUID value: \(value)")
        }
        let parts = [
            trimmed.prefix(8),
            trimmed.dropFirst(8).prefix(4),
            trimmed.dropFirst(12).prefix(4),
            trimmed.dropFirst(16).prefix(4),
            trimmed.dropFirst(20)
        ]
        let hyphenated = parts.map(String.init).joined(separator: "-")
        guard let uuid = UUID(uuidString: hyphenated) else {
            throw BookMakerError.database("Invalid UUID value: \(value)")
        }
        self = uuid
    }
}

extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

func bookMakerApplicationSupportDirectory() -> URL {
    let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
        ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
    return base.appendingPathComponent("BookMaker", isDirectory: true)
}

func ensureDirectory(_ url: URL) throws {
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
}

func packagedResourceURL(_ path: String) throws -> URL {
    let components = path.split(separator: "/").map(String.init)
    guard let first = components.first else {
        throw BookMakerError.missingResource(path)
    }
    var candidates: [URL] = []
    if let resourceURL = Bundle.module.resourceURL {
        candidates.append(resourceURL)
        candidates.append(resourceURL.appendingPathComponent("Resources", isDirectory: true))
    }
    candidates.append(URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("Sources/BookMaker/Resources", isDirectory: true))

    for base in candidates {
        var candidate = base
        for component in components {
            candidate = candidate.appendingPathComponent(component)
        }
        if FileManager.default.fileExists(atPath: candidate.path) {
            return candidate
        }
    }

    if let url = Bundle.module.url(forResource: first, withExtension: nil) {
        return url
    }
    throw BookMakerError.missingResource(path)
}
