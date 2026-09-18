package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONObject
import java.io.File

object WorkspaceTools {
    private const val MAX_READ_CHARS = 40_000
    private const val MAX_WRITE_CHARS = 100_000

    fun directory(context: Context): File =
        File(context.filesDir, "tool_workspace").apply { mkdirs() }

    fun list(context: Context): String {
        val files = directory(context).listFiles()
            .orEmpty()
            .filter { it.isFile }
            .sortedBy { it.name.lowercase() }

        if (files.isEmpty()) return "Workspace is empty."

        return buildString {
            append("Workspace files:")
            files.take(100).forEach { file ->
                append("\n- ")
                    .append(file.name)
                    .append(" (")
                    .append(file.length())
                    .append(" bytes)")
            }
        }
    }

    fun read(context: Context, name: String): String {
        val file = resolve(context, name)
        require(file.isFile) { "Workspace file not found: " + file.name }
        require(file.length() <= 2_000_000L) { "File is too large to read as text" }
        return file.readText(Charsets.UTF_8).take(MAX_READ_CHARS)
    }

    fun write(context: Context, name: String, content: String): String {
        require(content.length <= MAX_WRITE_CHARS) {
            "Workspace write exceeds " + MAX_WRITE_CHARS + " characters"
        }
        val file = resolve(context, name)
        file.parentFile?.mkdirs()
        file.writeText(content, Charsets.UTF_8)
        KnowledgeIndex.markDirty(context)
        return "Wrote " + file.name + " (" + file.length() + " bytes)"
    }

    fun delete(context: Context, name: String): String {
        val file = resolve(context, name)
        require(file.isFile) { "Workspace file not found: " + file.name }
        require(file.delete()) { "Could not delete " + file.name }
        KnowledgeIndex.markDirty(context)
        return "Deleted " + file.name
    }

    fun importFile(context: Context, displayName: String, bytes: ByteArray): String {
        require(bytes.size <= 5_000_000) { "Imported file exceeds 5 MB" }
        val file = resolve(context, displayName)
        file.writeBytes(bytes)
        KnowledgeIndex.markDirty(context)
        return file.name
    }

    fun file(context: Context, rawName: String): File = resolve(context, rawName)

    private fun resolve(context: Context, rawName: String): File {
        val cleaned = rawName.trim()
            .replace(Regex("""[^A-Za-z0-9._ -]"""), "_")
            .trim('.', ' ')
            .take(100)
        require(cleaned.isNotBlank()) { "File name is blank" }

        val dir = directory(context).canonicalFile
        val file = File(dir, cleaned).canonicalFile
        require(file.parentFile == dir) { "Invalid workspace path" }
        return file
    }
}

object MemoryTools {
    private const val PREFS = "codie_ai_tool_memory"
    private const val MAX_VALUE_CHARS = 4_000
    private const val MAX_ENTRIES = 100

    fun put(context: Context, key: String, value: String): String {
        val cleanedKey = key.trim().take(100)
        require(cleanedKey.isNotBlank()) { "Memory key is blank" }
        require(value.length <= MAX_VALUE_CHARS) {
            "Memory value exceeds " + MAX_VALUE_CHARS + " characters"
        }

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains(cleanedKey) && prefs.all.size >= MAX_ENTRIES) {
            throw IllegalStateException("Tool memory is full; delete an old key first")
        }
        prefs.edit().putString(cleanedKey, value).apply()
        return "Stored memory key '" + cleanedKey + "'"
    }

    fun get(context: Context, key: String): String {
        val cleanedKey = key.trim()
        require(cleanedKey.isNotBlank()) { "Memory key is blank" }
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(cleanedKey, null)
            ?: throw IllegalArgumentException("Memory key not found: " + cleanedKey)
    }

    fun list(context: Context): String {
        val keys = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .all.keys.sorted()
        return if (keys.isEmpty()) "Tool memory is empty."
        else "Memory keys:\n" + keys.joinToString("\n") { "- " + it }
    }

    fun delete(context: Context, key: String): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        require(prefs.contains(key)) { "Memory key not found: " + key }
        prefs.edit().remove(key).apply()
        return "Deleted memory key '" + key + "'"
    }
}
