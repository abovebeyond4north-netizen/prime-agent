package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest

object DataTools {
    fun textSearch(context: Context, fileName: String, query: String): String {
        val text = WorkspaceTools.read(context, fileName)
        val cleaned = query.trim()
        require(cleaned.isNotBlank()) { "Search query is blank" }

        val lines = text.lineSequence().toList()
        val matches = lines.mapIndexedNotNull { index, line ->
            if (line.contains(cleaned, ignoreCase = true)) {
                (index + 1) to line.take(500)
            } else null
        }.take(50)

        if (matches.isEmpty()) return "No matches for '" + cleaned + "'."
        return buildString {
            append("Matches for '").append(cleaned).append("':")
            matches.forEach { (lineNumber, line) ->
                append("\n").append(lineNumber).append(": ").append(line)
            }
        }
    }

    fun csvSummary(context: Context, fileName: String): String {
        val text = WorkspaceTools.read(context, fileName)
        val rows = parseCsv(text).take(2_000)
        require(rows.isNotEmpty()) { "CSV is empty" }

        val header = rows.first()
        val data = rows.drop(1)
        return buildString {
            append("CSV rows=").append(data.size)
                .append(" columns=").append(header.size)
                .append("\nColumns:")
            header.forEachIndexed { index, name ->
                val values = data.mapNotNull { it.getOrNull(index)?.trim()?.takeIf(String::isNotBlank) }
                val numeric = values.mapNotNull { it.toDoubleOrNull() }
                append("\n- ").append(name.ifBlank { "column_" + (index + 1) })
                    .append(": nonempty=").append(values.size)
                    .append(" unique=").append(values.distinct().size)
                if (numeric.isNotEmpty()) {
                    append(" min=").append(numeric.minOrNull())
                        .append(" max=").append(numeric.maxOrNull())
                        .append(" mean=").append(numeric.average())
                }
            }
        }
    }

    fun jsonQuery(context: Context, fileName: String, path: String): String {
        val raw = WorkspaceTools.read(context, fileName)
        var value: Any = if (raw.trimStart().startsWith("[")) JSONArray(raw) else JSONObject(raw)
        val tokens = path.trim().split('.').filter { it.isNotBlank() }

        for (token in tokens) {
            value = when (value) {
                is JSONObject -> {
                    require(value.has(token)) { "JSON object has no key: " + token }
                    value.get(token)
                }
                is JSONArray -> {
                    val index = token.toIntOrNull()
                        ?: throw IllegalArgumentException("Expected array index, got: " + token)
                    value.get(index)
                }
                else -> throw IllegalArgumentException("Cannot descend into scalar at: " + token)
            }
        }

        return when (value) {
            is JSONObject -> value.toString(2).take(20_000)
            is JSONArray -> value.toString(2).take(20_000)
            else -> value.toString().take(20_000)
        }
    }

    fun sha256(context: Context, fileName: String): String {
        val file = java.io.File(WorkspaceTools.directory(context), sanitize(fileName))
        require(file.isFile) { "Workspace file not found: " + fileName }
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun parseCsv(text: String): List<List<String>> {
        val rows = ArrayList<List<String>>()
        val row = ArrayList<String>()
        val field = StringBuilder()
        var quoted = false
        var i = 0

        fun endField() {
            row.add(field.toString())
            field.setLength(0)
        }

        fun endRow() {
            endField()
            rows.add(ArrayList(row))
            row.clear()
        }

        while (i < text.length) {
            val ch = text[i]
            when {
                quoted && ch == '"' && i + 1 < text.length && text[i + 1] == '"' -> {
                    field.append('"')
                    i += 2
                    continue
                }
                ch == '"' -> quoted = !quoted
                ch == ',' && !quoted -> endField()
                ch == '\n' && !quoted -> endRow()
                ch == '\r' && !quoted -> Unit
                else -> field.append(ch)
            }
            i++
        }
        if (field.isNotEmpty() || row.isNotEmpty()) endRow()
        return rows
    }

    private fun sanitize(name: String): String =
        name.trim().replace(Regex("""[^A-Za-z0-9._ -]"""), "_").trim('.', ' ')
}

object SkillStore {
    private const val PREFS = "codie_ai_skills"
    private const val MAX_SKILLS = 50
    private const val MAX_INSTRUCTIONS = 4_000

    fun save(context: Context, name: String, instructions: String): String {
        val key = normalize(name)
        require(instructions.isNotBlank() && instructions.length <= MAX_INSTRUCTIONS) {
            "Skill instructions must be 1.." + MAX_INSTRUCTIONS + " characters"
        }
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains(key) && prefs.all.size >= MAX_SKILLS) {
            throw IllegalStateException("Skill store is full")
        }
        prefs.edit().putString(key, instructions).apply()
        return "Saved skill '" + key + "'"
    }

    fun get(context: Context, name: String): String {
        val key = normalize(name)
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(key, null)
            ?: throw IllegalArgumentException("Skill not found: " + key)
    }

    fun list(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.all.isEmpty()) return "No saved skills."
        return buildString {
            append("Saved skills:")
            prefs.all.keys.sorted().forEach { key ->
                val preview = prefs.getString(key, "").orEmpty()
                    .replace('\n', ' ')
                    .take(160)
                append("\n- ").append(key).append(": ").append(preview)
            }
        }
    }

    fun delete(context: Context, name: String): String {
        val key = normalize(name)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        require(prefs.contains(key)) { "Skill not found: " + key }
        prefs.edit().remove(key).apply()
        return "Deleted skill '" + key + "'"
    }

    private fun normalize(name: String): String {
        val key = name.trim().lowercase().replace(Regex("""[^a-z0-9_ -]"""), "_").take(80)
        require(key.isNotBlank()) { "Skill name is blank" }
        return key
    }
}
