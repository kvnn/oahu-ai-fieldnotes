import AppKit
import SwiftUI

@main
struct BookMakerApp: App {
    @StateObject private var model = AppModel()

    init() {
        NSApplication.shared.setActivationPolicy(.regular)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    var body: some Scene {
        WindowGroup {
            RootView(model: model)
                .frame(minWidth: 1180, idealWidth: 1380, minHeight: 760, idealHeight: 860)
                .task {
                    if !model.config.databaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        await model.connect()
                    }
                }
        }
        .windowStyle(.titleBar)
    }
}

