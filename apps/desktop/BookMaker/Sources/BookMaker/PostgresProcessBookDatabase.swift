import Foundation

actor PostgresProcessBookDatabase: BookDatabase {
    let kind: DatabaseKind = .postgres
    private let databaseURL: String

    init(databaseURL: String) {
        self.databaseURL = databaseURL
    }

    func connect() async throws {
        _ = try await query(SQLStatement("select 1 as ok"))
    }

    func close() async {}

    func query(_ statement: SQLStatement) async throws -> [SQLRow] {
        let sql = try inlineParameters(statement)
        let wrapped = "select coalesce(json_agg(row_to_json(bookmaker_query)), '[]'::json) from (\(sql)) bookmaker_query"
        let output = try runPSQL(arguments: ["-X", "-q", "-t", "-A", databaseURL, "-c", wrapped])
        guard let data = output.trimmingCharacters(in: .whitespacesAndNewlines).data(using: .utf8),
              let objects = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return []
        }
        return objects.map { object in
            SQLRow(values: object.mapValues(Self.sqlValue(from:)))
        }
    }

    func execute(_ statement: SQLStatement) async throws {
        let sql = try inlineParameters(statement)
        _ = try runPSQL(arguments: ["-X", "-q", "-v", "ON_ERROR_STOP=1", databaseURL, "-c", sql])
    }

    func transaction<T: Sendable>(_ work: @Sendable () async throws -> T) async throws -> T {
        try await execute(SQLStatement("begin"))
        do {
            let result = try await work()
            try await execute(SQLStatement("commit"))
            return result
        } catch {
            try? await execute(SQLStatement("rollback"))
            throw error
        }
    }

    private func inlineParameters(_ statement: SQLStatement) throws -> String {
        var result = ""
        var parameters = statement.parameters[...]
        for character in statement.sql {
            if character == "?" {
                guard let parameter = parameters.popFirst() else {
                    throw BookMakerError.database("Missing SQL parameter.")
                }
                result.append(Self.postgresLiteral(parameter))
            } else {
                result.append(character)
            }
        }
        if !parameters.isEmpty {
            throw BookMakerError.database("Too many SQL parameters.")
        }
        return result
    }

    private func runPSQL(arguments: [String]) throws -> String {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["psql"] + arguments
        let output = Pipe()
        let error = Pipe()
        process.standardOutput = output
        process.standardError = error
        try process.run()
        process.waitUntilExit()

        let outputData = output.fileHandleForReading.readDataToEndOfFile()
        let errorData = error.fileHandleForReading.readDataToEndOfFile()
        let stdout = String(data: outputData, encoding: .utf8) ?? ""
        let stderr = String(data: errorData, encoding: .utf8) ?? ""
        guard process.terminationStatus == 0 else {
            throw BookMakerError.database(stderr.nilIfBlank ?? stdout.nilIfBlank ?? "psql failed")
        }
        return stdout
    }

    private static func postgresLiteral(_ value: SQLValue) -> String {
        switch value {
        case .null:
            "NULL"
        case .string(let string):
            "'\(string.replacingOccurrences(of: "'", with: "''"))'"
        case .int(let int):
            String(int)
        case .double(let double):
            String(double)
        case .bool(let bool):
            bool ? "TRUE" : "FALSE"
        case .uuid(let uuid):
            "'\(uuid.uuidString)'::uuid"
        case .json(let data):
            "'\((String(data: data, encoding: .utf8) ?? "{}").replacingOccurrences(of: "'", with: "''"))'::jsonb"
        case .date(let date):
            "'\(DateCoding.string(from: date))'::timestamptz"
        }
    }

    private static func sqlValue(from value: Any) -> SQLValue {
        switch value {
        case is NSNull:
            .null
        case let value as String:
            .string(value)
        case let value as Int:
            .int(value)
        case let value as Double:
            .double(value)
        case let value as Bool:
            .bool(value)
        case let value as [String: Any]:
            .json((try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])) ?? Data("{}".utf8))
        case let value as [Any]:
            .json((try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])) ?? Data("[]".utf8))
        default:
            .string(String(describing: value))
        }
    }
}

