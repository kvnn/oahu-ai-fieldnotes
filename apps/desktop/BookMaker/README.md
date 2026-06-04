# BookMaker

Native macOS writing cockpit for source-grounded books.

BookMaker is a pure Swift desktop app. It connects directly to a configured `DB_URL`, stores the OpenAI API key in Keychain, creates books from writing-system templates, edits versioned chapter Markdown, compiles book Markdown, and can run a configured render command.

## Build

```bash
swift build
```

When running inside restricted sandboxes, set a writable Clang module cache:

```bash
CLANG_MODULE_CACHE_PATH=/private/tmp/bookmaker-clang-cache swift build
```

## Run

```bash
swift run BookMaker
```

## Bundle

```bash
scripts/build_bookmaker_app.sh
open dist/BookMaker.app
```

## Database

Supported `DB_URL` forms:

- `sqlite:///absolute/path/to/bookmaker.db`
- `postgres://...`
- `postgresql://...`
- `postgresql+psycopg://...`

SQLite is implemented through the macOS SQLite library. Postgres v0 uses the `psql` command through a Swift driver boundary so the app remains independent from the Python server.

