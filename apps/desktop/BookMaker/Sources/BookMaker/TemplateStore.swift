import Foundation

struct TemplateStore {
    func loadTemplates() throws -> [BookTemplate] {
        let paths = [
            "Templates/field-notes-essay.json",
            "Templates/blank-builder-book.json"
        ]
        return try paths.map { path in
            let data = try Data(contentsOf: packagedResourceURL(path))
            return try JSONCoding.decoder.decode(BookTemplate.self, from: data)
        }
    }
}

