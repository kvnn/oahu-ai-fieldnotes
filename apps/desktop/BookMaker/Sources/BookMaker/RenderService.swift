import Foundation

struct RenderResult: Hashable {
    var status: String
    var outputPath: String
    var logs: String
}

struct RenderService {
    func render(command: String, workspaceRoot: String) async throws -> RenderResult {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw BookMakerError.processFailed("Render command is empty.")
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", trimmed]
        process.currentDirectoryURL = URL(fileURLWithPath: (workspaceRoot as NSString).expandingTildeInPath, isDirectory: true)
        let output = Pipe()
        let error = Pipe()
        process.standardOutput = output
        process.standardError = error
        try process.run()
        process.waitUntilExit()

        let stdout = String(data: output.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let stderr = String(data: error.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let logs = [stdout, stderr].filter { !$0.isEmpty }.joined(separator: "\n")
        let status = process.terminationStatus == 0 ? "succeeded" : "failed"
        return RenderResult(status: status, outputPath: "dist", logs: logs)
    }
}

