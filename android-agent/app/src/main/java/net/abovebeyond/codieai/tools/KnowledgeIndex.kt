package net.abovebeyond.codieai.tools

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.io.File
import java.util.Locale

object KnowledgeIndex {
    private const val PREFS = "codie_ai_knowledge"
    private const val KEY_DIRTY = "dirty"
    private const val CHUNK_SIZE = 1800
    private const val CHUNK_OVERLAP = 180
    private const val MAX_INDEX_CHARS_PER_FILE = 1_000_000

    private val textExtensions = setOf(
        "txt", "md", "json", "csv", "xml", "html", "htm", "log",
        "kt", "kts", "java", "py", "js", "ts", "tsx", "jsx",
        "sh", "bash", "gradle", "yaml", "yml", "sql", "toml", "ini"
    )

    fun markDirty(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_DIRTY, true)
            .apply()
    }

    fun reindex(context: Context): String {
        val db = Helper(context.applicationContext).writableDatabase
        db.beginTransaction()
        var fileCount = 0
        var chunkCount = 0

        try {
            db.delete("knowledge", null, null)

            WorkspaceTools.directory(context)
                .listFiles()
                .orEmpty()
                .filter { it.isFile && isIndexable(it) }
                .sortedBy { it.name.lowercase(Locale.getDefault()) }
                .forEach { file ->
                    val text = runCatching {
                        file.readText(Charsets.UTF_8).take(MAX_INDEX_CHARS_PER_FILE)
                    }.getOrNull() ?: return@forEach

                    if (text.isBlank()) return@forEach
                    fileCount++

                    chunkText(text).forEachIndexed { index, chunk ->
                        db.execSQL(
                            "INSERT INTO knowledge(file, chunk_index, content) VALUES(?,?,?)",
                            arrayOf(file.name, index, chunk)
                        )
                        chunkCount++
                    }
                }

            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
            db.close()
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_DIRTY, false)
            .apply()

        return "Knowledge index rebuilt: " + fileCount +
            " file(s), " + chunkCount + " chunk(s)."
    }

    fun search(context: Context, query: String, limit: Int = 8): String {
        val cleaned = query.trim()
        require(cleaned.isNotBlank()) { "Knowledge search query is blank" }

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_DIRTY, true)) {
            reindex(context)
        }

        val terms = Regex("""[\p{L}\p{N}_-]{2,40}""")
            .findAll(cleaned)
            .map { it.value.replace(""", "") }
            .distinct()
            .take(12)
            .toList()

        require(terms.isNotEmpty()) { "Knowledge search has no searchable terms" }

        val match = terms.joinToString(" OR ") { """ + it + """ }
        val bounded = limit.coerceIn(1, 20)
        val db = Helper(context.applicationContext).readableDatabase
        val results = ArrayList<String>()

        db.rawQuery(
            "SELECT file, chunk_index, content FROM knowledge " +
                "WHERE knowledge MATCH ? LIMIT ?",
            arrayOf(match, bounded.toString())
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val file = cursor.getString(0)
                val index = cursor.getInt(1)
                val content = cursor.getString(2)
                    .replace(Regex("""\s+"""), " ")
                    .trim()
                    .take(900)
                results.add(
                    file + " [chunk " + index + "]: " + content
                )
            }
        }
        db.close()

        if (results.isEmpty()) {
            return "No indexed workspace matches for: " + cleaned
        }

        return buildString {
            append("Knowledge matches for: ").append(cleaned)
            results.forEachIndexed { index, result ->
                append("\n\n").append(index + 1).append(". ").append(result)
            }
        }
    }

    private fun isIndexable(file: File): Boolean {
        if (file.length() <= 0L || file.length() > 2_000_000L) return false
        val ext = file.extension.lowercase(Locale.getDefault())
        return ext in textExtensions
    }

    private fun chunkText(text: String): List<String> {
        val chunks = ArrayList<String>()
        var start = 0

        while (start < text.length) {
            var end = (start + CHUNK_SIZE).coerceAtMost(text.length)
            if (end < text.length) {
                val newline = text.lastIndexOf('\n', end)
                if (newline > start + CHUNK_SIZE / 2) end = newline
            }

            val chunk = text.substring(start, end).trim()
            if (chunk.isNotBlank()) chunks.add(chunk)

            if (end >= text.length) break
            start = (end - CHUNK_OVERLAP).coerceAtLeast(start + 1)
        }

        return chunks
    }

    private class Helper(context: Context) :
        SQLiteOpenHelper(context, "codie_knowledge.db", null, 1) {

        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                "CREATE VIRTUAL TABLE knowledge USING fts4(" +
                    "file, chunk_index, content, tokenize=unicode61)"
            )
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            db.execSQL("DROP TABLE IF EXISTS knowledge")
            onCreate(db)
        }
    }
}
