import Foundation

enum ManuscriptCompiler {
    static func compile(bodies: [(ChapterRecord, String)]) -> CompiledBook {
        let raw = bodies.map { _, body in body.trimmingCharacters(in: .whitespacesAndNewlines) }
            .joined(separator: "\n\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let vivliostyle = bodies.map(vivliostyleChapter).joined(separator: "\n\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return CompiledBook(
            rawMarkdown: raw,
            vivliostyleMarkdown: vivliostyle,
            wordCount: wordCount(raw),
            chapterCount: bodies.count
        )
    }

    static func wordCount(_ text: String) -> Int {
        text.split { $0.isWhitespace }.count
    }

    private static func vivliostyleChapter(chapter: ChapterRecord, body: String) -> String {
        let title = escapeHTML(chapter.title.nilIfBlank ?? "Untitled Chapter")
        let subtitle = chapter.subtitle.nilIfBlank.map(escapeHTML)
        let roman = romanNumeral(chapter.sequenceOrder)
        var lines = [
            "<section class=\"chapter-opener opener-title\" data-chapter-slug=\"\(escapeHTML(chapter.slug))\">",
            "<header class=\"opener-header\"><p class=\"opener-chapter-label\">Chapter \(chapter.sequenceOrder)</p><div class=\"opener-rule\"></div></header>",
            "<p class=\"opener-kicker\">FIELD NOTE</p>",
            "<p class=\"opener-roman\" aria-hidden=\"true\">\(roman)</p>",
            "<h1>\(title)</h1>"
        ]
        if let subtitle {
            lines.append("<p class=\"opener-subtitle\">\(subtitle)</p>")
        }
        lines.append("</section>")
        lines.append("<div class=\"chapter-body-marker\" aria-hidden=\"true\"></div>")
        lines.append(stripLeadingChapterMatter(body))
        return lines.joined(separator: "\n")
    }

    private static func stripLeadingChapterMatter(_ body: String) -> String {
        var lines = body.components(separatedBy: .newlines)
        while let first = lines.first {
            let trimmed = first.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty || trimmed.hasPrefix("# ") || trimmed.hasPrefix("<p class=\"chapter-subtitle\"") {
                lines.removeFirst()
                continue
            }
            break
        }
        return lines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func romanNumeral(_ value: Int) -> String {
        guard value > 0 else { return "" }
        let numerals = [
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
        ]
        var number = value
        var result = ""
        for (amount, numeral) in numerals {
            while number >= amount {
                result += numeral
                number -= amount
            }
        }
        return result
    }

    private static func escapeHTML(_ value: String) -> String {
        value
            .replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }
}

