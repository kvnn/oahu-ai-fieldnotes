import Foundation

enum BookMakerPathResolver {
    static func sourceRoot(currentDirectory: URL = URL(fileURLWithPath: FileManager.default.currentDirectoryPath), workspaceRoot: String) -> String {
        let current = currentDirectory.standardizedFileURL
        if FileManager.default.fileExists(atPath: current.appendingPathComponent("Package.swift").path) {
            return current.path
        }

        let workspace = directoryURL(workspaceRoot, fallback: current)
        let nested = workspace.appendingPathComponent("apps/desktop/BookMaker", isDirectory: true)
        if FileManager.default.fileExists(atPath: nested.appendingPathComponent("Package.swift").path) {
            return nested.standardizedFileURL.path
        }

        return workspace.standardizedFileURL.path
    }

    static func workspaceRoot(_ value: String, fallback: URL = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)) -> String {
        directoryURL(value, fallback: fallback).standardizedFileURL.path
    }

    static func workingDirectory(for mode: TerminalWorkingDirectoryMode, workspaceRoot: String, custom: String? = nil) -> String {
        switch mode {
        case .sourceRoot:
            sourceRoot(workspaceRoot: workspaceRoot)
        case .workspaceRoot:
            self.workspaceRoot(workspaceRoot)
        case .custom:
            directoryURL(custom ?? workspaceRoot, fallback: URL(fileURLWithPath: self.workspaceRoot(workspaceRoot))).standardizedFileURL.path
        }
    }

    private static func directoryURL(_ value: String, fallback: URL) -> URL {
        guard let trimmed = value.nilIfBlank else {
            return fallback.standardizedFileURL
        }
        return URL(fileURLWithPath: (trimmed as NSString).expandingTildeInPath, isDirectory: true)
            .standardizedFileURL
    }
}

final class ShellCommandRunner: @unchecked Sendable {
    private let lock = NSLock()
    private var activeProcess: Process?
    private var activeRunID: UUID?
    private var cancelledRunIDs: Set<UUID> = []

    func run(command: String, workingDirectory: String) -> AsyncThrowingStream<ShellCommandEvent, Error> {
        AsyncThrowingStream { continuation in
            do {
                try start(command: command, workingDirectory: workingDirectory, continuation: continuation)
            } catch {
                continuation.finish(throwing: error)
            }
        }
    }

    func cancel() {
        lock.withLock {
            guard let process = activeProcess, let activeRunID else { return }
            cancelledRunIDs.insert(activeRunID)
            if process.isRunning {
                process.terminate()
            }
        }
    }

    static func openExternalTerminal(at workingDirectory: String) throws {
        let directory = BookMakerPathResolver.workspaceRoot(workingDirectory)
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        process.arguments = ["-a", "Terminal", directory]
        try process.run()
    }

    private func start(
        command: String,
        workingDirectory: String,
        continuation: AsyncThrowingStream<ShellCommandEvent, Error>.Continuation
    ) throws {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw BookMakerError.processFailed("Command is empty.")
        }

        let directory = BookMakerPathResolver.workspaceRoot(workingDirectory)
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: directory, isDirectory: &isDirectory), isDirectory.boolValue else {
            throw BookMakerError.processFailed("Working directory does not exist: \(directory)")
        }

        let runID = UUID()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", trimmed]
        process.currentDirectoryURL = URL(fileURLWithPath: directory, isDirectory: true)

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        try lock.withLock {
            if activeProcess != nil {
                throw BookMakerError.processFailed("A terminal command is already running.")
            }
            activeProcess = process
            activeRunID = runID
        }

        stdout.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8), !text.isEmpty else { return }
            continuation.yield(.output(.stdout, text))
        }
        stderr.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8), !text.isEmpty else { return }
            continuation.yield(.output(.stderr, text))
        }

        process.terminationHandler = { [weak self] process in
            stdout.fileHandleForReading.readabilityHandler = nil
            stderr.fileHandleForReading.readabilityHandler = nil

            let leftoverOutput = stdout.fileHandleForReading.readDataToEndOfFile()
            if !leftoverOutput.isEmpty, let text = String(data: leftoverOutput, encoding: .utf8), !text.isEmpty {
                continuation.yield(.output(.stdout, text))
            }
            let leftoverError = stderr.fileHandleForReading.readDataToEndOfFile()
            if !leftoverError.isEmpty, let text = String(data: leftoverError, encoding: .utf8), !text.isEmpty {
                continuation.yield(.output(.stderr, text))
            }

            let wasCancelled = self?.finishRun(runID: runID, process: process) ?? false
            let status: TerminalRunStatus = wasCancelled ? .cancelled : (process.terminationStatus == 0 ? .succeeded : .failed)
            continuation.yield(.finished(TerminalRunResult(status: status, exitCode: process.terminationStatus)))
            continuation.finish()
        }

        do {
            try process.run()
        } catch {
            stdout.fileHandleForReading.readabilityHandler = nil
            stderr.fileHandleForReading.readabilityHandler = nil
            _ = finishRun(runID: runID, process: process)
            throw error
        }
    }

    private func finishRun(runID: UUID, process: Process) -> Bool {
        lock.withLock {
            let wasCancelled = cancelledRunIDs.remove(runID) != nil
            if activeRunID == runID {
                activeProcess = nil
                activeRunID = nil
            } else if activeProcess === process {
                activeProcess = nil
            }
            return wasCancelled
        }
    }
}

private extension NSLock {
    func withLock<T>(_ work: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try work()
    }
}
