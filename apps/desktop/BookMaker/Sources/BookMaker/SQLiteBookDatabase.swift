import Foundation
import SQLite3

actor SQLiteBookDatabase: BookDatabase {
    let kind: DatabaseKind = .sqlite
    private let path: String
    private var db: OpaquePointer?

    init(path: String) {
        self.path = path
    }

    func connect() async throws {
        if db != nil { return }
        let expanded = (path as NSString).expandingTildeInPath
        let url = URL(fileURLWithPath: expanded)
        try ensureDirectory(url.deletingLastPathComponent())
        var handle: OpaquePointer?
        guard sqlite3_open_v2(expanded, &handle, SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX, nil) == SQLITE_OK else {
            let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "Unknown SQLite open error"
            throw BookMakerError.database(message)
        }
        db = handle
        try await execute(SQLStatement("PRAGMA foreign_keys = ON"))
    }

    func close() async {
        if let db {
            sqlite3_close(db)
        }
        db = nil
    }

    func query(_ statement: SQLStatement) async throws -> [SQLRow] {
        let handle = try requireHandle()
        var prepared: OpaquePointer?
        guard sqlite3_prepare_v2(handle, statement.sql, -1, &prepared, nil) == SQLITE_OK else {
            throw BookMakerError.database(String(cString: sqlite3_errmsg(handle)))
        }
        guard let prepared else { return [] }
        defer { sqlite3_finalize(prepared) }
        try bind(statement.parameters, to: prepared)

        var rows: [SQLRow] = []
        while true {
            let result = sqlite3_step(prepared)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw BookMakerError.database(String(cString: sqlite3_errmsg(handle)))
            }
            rows.append(readRow(prepared))
        }
        return rows
    }

    func execute(_ statement: SQLStatement) async throws {
        _ = try await query(statement)
    }

    func transaction<T: Sendable>(_ work: @Sendable () async throws -> T) async throws -> T {
        try await execute(SQLStatement("BEGIN"))
        do {
            let result = try await work()
            try await execute(SQLStatement("COMMIT"))
            return result
        } catch {
            try? await execute(SQLStatement("ROLLBACK"))
            throw error
        }
    }

    private func requireHandle() throws -> OpaquePointer {
        guard let db else {
            throw BookMakerError.database("SQLite database is not connected.")
        }
        return db
    }

    private func bind(_ parameters: [SQLValue], to statement: OpaquePointer) throws {
        for (index, value) in parameters.enumerated() {
            let position = Int32(index + 1)
            switch value {
            case .null:
                sqlite3_bind_null(statement, position)
            case .string(let string):
                sqlite3_bind_text(statement, position, string, -1, SQLITE_TRANSIENT)
            case .int(let int):
                sqlite3_bind_int64(statement, position, sqlite3_int64(int))
            case .double(let double):
                sqlite3_bind_double(statement, position, double)
            case .bool(let bool):
                sqlite3_bind_int(statement, position, bool ? 1 : 0)
            case .uuid(let uuid):
                sqlite3_bind_text(statement, position, uuid.sqlalchemySQLiteString, -1, SQLITE_TRANSIENT)
            case .json(let data):
                let text = String(data: data, encoding: .utf8) ?? "{}"
                sqlite3_bind_text(statement, position, text, -1, SQLITE_TRANSIENT)
            case .date(let date):
                sqlite3_bind_text(statement, position, DateCoding.string(from: date), -1, SQLITE_TRANSIENT)
            }
        }
    }

    private func readRow(_ statement: OpaquePointer) -> SQLRow {
        let columnCount = sqlite3_column_count(statement)
        var values: [String: SQLValue] = [:]
        for index in 0..<columnCount {
            let name = sqlite3_column_name(statement, index).map { String(cString: $0) } ?? "column_\(index)"
            switch sqlite3_column_type(statement, index) {
            case SQLITE_INTEGER:
                values[name] = .int(Int(sqlite3_column_int64(statement, index)))
            case SQLITE_FLOAT:
                values[name] = .double(sqlite3_column_double(statement, index))
            case SQLITE_NULL:
                values[name] = .null
            case SQLITE_BLOB:
                let bytes = sqlite3_column_blob(statement, index)
                let count = Int(sqlite3_column_bytes(statement, index))
                if let bytes, count > 0 {
                    values[name] = .json(Data(bytes: bytes, count: count))
                } else {
                    values[name] = .json(Data())
                }
            default:
                if let cString = sqlite3_column_text(statement, index) {
                    values[name] = .string(String(cString: cString))
                } else {
                    values[name] = .string("")
                }
            }
        }
        return SQLRow(values: values)
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

