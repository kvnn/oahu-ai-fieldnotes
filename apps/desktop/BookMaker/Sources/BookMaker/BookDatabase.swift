import Foundation

enum SQLValue: Hashable {
    case null
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case uuid(UUID)
    case json(Data)
    case date(Date = Date())

    var stringValue: String {
        switch self {
        case .null:
            ""
        case .string(let value):
            value
        case .int(let value):
            String(value)
        case .double(let value):
            String(value)
        case .bool(let value):
            value ? "1" : "0"
        case .uuid(let value):
            value.uuidString
        case .json(let data):
            String(data: data, encoding: .utf8) ?? "{}"
        case .date(let value):
            DateCoding.string(from: value)
        }
    }
}

struct SQLStatement: Hashable {
    var sql: String
    var parameters: [SQLValue]

    init(_ sql: String, _ parameters: [SQLValue] = []) {
        self.sql = sql
        self.parameters = parameters
    }
}

struct SQLRow: Hashable {
    var values: [String: SQLValue]

    func string(_ key: String, default defaultValue: String = "") -> String {
        values[key]?.stringValue ?? defaultValue
    }

    func int(_ key: String, default defaultValue: Int = 0) -> Int {
        guard let value = values[key] else { return defaultValue }
        switch value {
        case .int(let int):
            return int
        case .string(let string):
            return Int(string) ?? defaultValue
        default:
            return Int(value.stringValue) ?? defaultValue
        }
    }

    func uuid(_ key: String) throws -> UUID {
        try UUID(bookMakerDatabaseString: string(key))
    }
}

protocol BookDatabase: Sendable {
    var kind: DatabaseKind { get }
    func connect() async throws
    func close() async
    func query(_ statement: SQLStatement) async throws -> [SQLRow]
    func execute(_ statement: SQLStatement) async throws
    func transaction<T: Sendable>(_ work: @Sendable () async throws -> T) async throws -> T
}

func jsonData<T: Encodable>(_ value: T) throws -> Data {
    try JSONCoding.encoder.encode(value)
}

func decodeJSON<T: Decodable>(_ type: T.Type, from value: String, fallback: T) -> T {
    guard let data = value.data(using: .utf8), !value.isEmpty else { return fallback }
    return (try? JSONCoding.decoder.decode(T.self, from: data)) ?? fallback
}

func makeBookDatabase(from url: ParsedDatabaseURL) -> any BookDatabase {
    switch url.kind {
    case .sqlite:
        return SQLiteBookDatabase(path: url.sqlitePath ?? "")
    case .postgres:
        return PostgresProcessBookDatabase(databaseURL: url.postgresURL ?? url.original)
    }
}
