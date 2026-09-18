package net.abovebeyond.codieai.tools

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class McpToolDefinition(
    val name: String,
    val description: String,
    val inputSchema: String
)

data class McpServerDefinition(
    val name: String,
    val endpoint: String,
    val authType: String = "none",
    val secretAlias: String = "",
    val authHeader: String = "",
    val tools: List<McpToolDefinition> = emptyList()
)

object McpServerStore {
    private const val PREFS = "codie_ai_mcp_servers"
    private const val KEY_SERVERS = "servers"
    private const val MAX_SERVERS = 12
    private const val MAX_TOOLS_PER_SERVER = 100

    fun importManifest(context: Context, raw: String): String {
        val json = JSONObject(raw)
        val name = normalizeName(json.getString("name"))
        val endpoint = json.getString("endpoint").trim()
        WebTools.validatePublicHttpsEndpoint(endpoint)

        val auth = json.optJSONObject("auth")
        val authType = auth?.optString("type", "none")?.trim()?.lowercase() ?: "none"
        val secretAlias = auth?.optString("secret_alias", "")?.trim()?.lowercase().orEmpty()
        val authHeader = auth?.optString("header", "")?.trim().orEmpty()

        require(authType in setOf("none", "bearer", "api_key")) {
            "MCP auth.type must be none, bearer, or api_key"
        }
        if (authType != "none") {
            require(secretAlias.isNotBlank()) {
                "Authenticated MCP servers require auth.secret_alias"
            }
            require(SecretStore.exists(context, secretAlias)) {
                "Secret alias '" + secretAlias + "' is not stored yet"
            }
        }
        if (authType == "api_key") {
            val header = authHeader.ifBlank { "X-API-Key" }
            require(header.matches(Regex("""[A-Za-z0-9-]{1,64}"""))) {
                "Invalid MCP API-key header"
            }
        }

        val current = list(context).associateBy { it.name }.toMutableMap()
        val previousTools = current[name]?.tools.orEmpty()
        current[name] = McpServerDefinition(
            name = name,
            endpoint = endpoint,
            authType = authType,
            secretAlias = secretAlias,
            authHeader = if (authType == "api_key") {
                authHeader.ifBlank { "X-API-Key" }
            } else "",
            tools = previousTools
        )
        require(current.size <= MAX_SERVERS) { "Maximum MCP servers reached" }
        write(context, current.values.sortedBy { it.name })
        return "Installed MCP server '" + name + "'. Refresh its tool list before use."
    }

    fun list(context: Context): List<McpServerDefinition> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_SERVERS, "[]")
            .orEmpty()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    val toolArray = obj.optJSONArray("tools") ?: JSONArray()
                    val tools = buildList {
                        for (j in 0 until toolArray.length()) {
                            val t = toolArray.getJSONObject(j)
                            add(
                                McpToolDefinition(
                                    name = t.getString("name"),
                                    description = t.optString("description", ""),
                                    inputSchema = t.optString("input_schema", "{}")
                                )
                            )
                        }
                    }
                    add(
                        McpServerDefinition(
                            name = obj.getString("name"),
                            endpoint = obj.getString("endpoint"),
                            authType = obj.optString("auth_type", "none"),
                            secretAlias = obj.optString("secret_alias", ""),
                            authHeader = obj.optString("auth_header", ""),
                            tools = tools
                        )
                    )
                }
            }
        }.getOrElse { emptyList() }
    }

    fun render(context: Context): String {
        val servers = list(context)
        if (servers.isEmpty()) return "No MCP servers installed."
        return buildString {
            append("MCP servers:")
            servers.forEach { server ->
                append("\n- ").append(server.name)
                    .append(": ").append(server.endpoint)
                    .append(" auth=").append(server.authType)
                    .append(" cached_tools=").append(server.tools.size)
            }
        }
    }

    fun refresh(context: Context, serverName: String): String {
        val server = find(context, serverName)
            ?: throw IllegalArgumentException("MCP server not found: " + serverName)

        val discovered = McpClient.listTools(context, server)
            .take(MAX_TOOLS_PER_SERVER)

        val updated = list(context).map {
            if (it.name == server.name) it.copy(tools = discovered) else it
        }
        write(context, updated)

        return "Refreshed MCP server '" + server.name + "': " +
            discovered.size + " tool(s)."
    }

    fun remove(context: Context, serverName: String): String {
        val normalized = normalizeName(serverName)
        val current = list(context)
        val filtered = current.filterNot { it.name == normalized }
        require(filtered.size != current.size) { "MCP server not found: " + normalized }
        write(context, filtered)
        return "Removed MCP server '" + normalized + "'"
    }

    fun catalogLines(context: Context): List<String> {
        val lines = ArrayList<String>()
        list(context).forEach { server ->
            server.tools.forEach { tool ->
                val exposed = exposedName(server.name, tool.name)
                lines.add(
                    exposed + "(arguments): MCP " + server.name + " — " +
                        tool.description.take(500) +
                        " inputSchema=" + tool.inputSchema.take(900)
                )
            }
        }
        return lines
    }

    fun callExposed(
        context: Context,
        exposedName: String,
        argumentsJson: String
    ): String {
        val match = parseExposedName(exposedName)
            ?: throw IllegalArgumentException("Invalid MCP tool name: " + exposedName)
        val server = find(context, match.first)
            ?: throw IllegalArgumentException("MCP server not found: " + match.first)

        require(server.tools.any { it.name == match.second }) {
            "MCP tool is not in the cached tool list. Refresh server '" +
                server.name + "' first."
        }

        return McpClient.callTool(context, server, match.second, argumentsJson)
    }

    fun isExposedTool(name: String): Boolean =
        parseExposedName(name) != null

    private fun find(context: Context, name: String): McpServerDefinition? {
        val normalized = normalizeName(name)
        return list(context).firstOrNull { it.name == normalized }
    }

    private fun exposedName(server: String, remoteTool: String): String =
        "mcp__" + server + "__" + remoteTool

    private fun parseExposedName(value: String): Pair<String, String>? {
        if (!value.startsWith("mcp__")) return null
        val rest = value.removePrefix("mcp__")
        val separator = rest.indexOf("__")
        if (separator <= 0 || separator >= rest.length - 2) return null
        val server = rest.substring(0, separator)
        val tool = rest.substring(separator + 2)
        if (server.isBlank() || tool.isBlank()) return null
        return server to tool
    }

    private fun normalizeName(raw: String): String {
        val name = raw.trim().lowercase()
        require(name.matches(Regex("""[a-z][a-z0-9_-]{1,32}"""))) {
            "MCP server name must match [a-z][a-z0-9_-]{1,32}"
        }
        return name
    }

    private fun write(context: Context, servers: Collection<McpServerDefinition>) {
        val array = JSONArray()
        servers.forEach { server ->
            val tools = JSONArray()
            server.tools.forEach { tool ->
                tools.put(
                    JSONObject()
                        .put("name", tool.name)
                        .put("description", tool.description)
                        .put("input_schema", tool.inputSchema)
                )
            }

            array.put(
                JSONObject()
                    .put("name", server.name)
                    .put("endpoint", server.endpoint)
                    .put("auth_type", server.authType)
                    .put("secret_alias", server.secretAlias)
                    .put("auth_header", server.authHeader)
                    .put("tools", tools)
            )
        }

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_SERVERS, array.toString())
            .apply()
    }
}
