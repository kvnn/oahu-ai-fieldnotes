import Foundation

enum DatabaseKind: String, Hashable {
    case postgres
    case sqlite
}

struct ParsedDatabaseURL: Hashable {
    var original: String
    var kind: DatabaseKind
    var sqlitePath: String?
    var postgresURL: String?

    init(_ rawValue: String) throws {
        let value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else {
            throw BookMakerError.invalidDatabaseURL(rawValue)
        }

        if value.hasPrefix("sqlite:///") {
            original = value
            kind = .sqlite
            sqlitePath = String(value.dropFirst("sqlite:///".count))
            postgresURL = nil
            return
        }

        if value.hasPrefix("sqlite://") {
            original = value
            kind = .sqlite
            sqlitePath = String(value.dropFirst("sqlite://".count))
            postgresURL = nil
            return
        }

        if value.hasPrefix("postgres://")
            || value.hasPrefix("postgresql://")
            || value.hasPrefix("postgresql+psycopg://")
            || value.hasPrefix("postgresql+asyncpg://") {
            original = value
                .replacingOccurrences(of: "postgresql+psycopg://", with: "postgresql://")
                .replacingOccurrences(of: "postgresql+asyncpg://", with: "postgresql://")
            kind = .postgres
            sqlitePath = nil
            postgresURL = original
            return
        }

        throw BookMakerError.unsupportedDatabase(rawValue)
    }
}
