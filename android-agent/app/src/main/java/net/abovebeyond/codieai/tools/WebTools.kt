package net.abovebeyond.codieai.tools

import android.net.Uri
import android.text.Html
import java.net.HttpURLConnection
import java.net.Inet6Address
import java.net.InetAddress
import java.net.URL
import java.net.URLEncoder
import org.json.JSONObject

object WebTools {
    private const val MAX_BYTES = 512_000
    private const val MAX_TEXT_CHARS = 30_000

    fun search(query: String): String {
        val cleaned = query.trim()
        require(cleaned.isNotBlank()) { "Search query is blank" }

        val url = "https://html.duckduckgo.com/html/?q=" +
            URLEncoder.encode(cleaned, Charsets.UTF_8.name())
        val html = request(url, rawHtml = true)

        val resultRegex = Regex(
            """<a[^>]+class=["'][^"']*result__a[^"']*["'][^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)
        )
        val snippetRegex = Regex(
            """class=["'][^"']*result__snippet[^"']*["'][^>]*>(.*?)</(?:a|div|span)>""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)
        )

        val matches = resultRegex.findAll(html).take(6).toList()
        if (matches.isEmpty()) {
            return "Search results page text:\n" + htmlToText(html).take(12_000)
        }

        val snippets = snippetRegex.findAll(html)
            .map { htmlToText(it.groupValues[1]).trim() }
            .toList()

        return buildString {
            append("Public web search results for: ").append(cleaned)
            matches.forEachIndexed { index, match ->
                val rawHref = decodeHtml(match.groupValues[1])
                val resolved = resolveDuckDuckGoUrl(rawHref)
                val title = htmlToText(match.groupValues[2]).trim()
                append("\n\n").append(index + 1).append(". ").append(title)
                append("\n").append(resolved)
                snippets.getOrNull(index)?.takeIf { it.isNotBlank() }?.let {
                    append("\n").append(it.take(700))
                }
            }
        }
    }

    fun fetch(url: String): String =
        request(url.trim(), rawHtml = false).take(MAX_TEXT_CHARS)

    fun validatePublicHttpsEndpoint(url: String) {
        validatePublicHttps(URL(url))
    }

    fun postJsonPublic(
        url: String,
        bodyJson: String,
        headers: Map<String, String> = emptyMap()
    ): String {
        val bytes = bodyJson.toByteArray(Charsets.UTF_8)
        require(bytes.size <= 128_000) { "Custom tool request body is too large" }

        return customRequest(
            url = url,
            method = "POST",
            headers = headers,
            body = bytes
        )
    }

    fun getJsonPublic(
        url: String,
        argumentsJson: String,
        headers: Map<String, String> = emptyMap()
    ): String {
        val args = JSONObject(argumentsJson.ifBlank { "{}" })
        val target = appendQuery(url, args)
        return customRequest(
            url = target,
            method = "GET",
            headers = headers,
            body = null
        )
    }

    private fun customRequest(
        url: String,
        method: String,
        headers: Map<String, String>,
        body: ByteArray?
    ): String {
        val target = validatePublicHttps(URL(url))
        val connection = (target.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 30_000
            instanceFollowRedirects = false
            setRequestProperty("User-Agent", "CodieAI/1.3 (+Android local assistant)")
            setRequestProperty("Accept", "application/json,text/plain,text/html;q=0.6")
            if (method == "POST") {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
            applySafeHeaders(this, headers)
        }

        if (body != null) {
            connection.outputStream.use { it.write(body) }
        }

        val status = connection.responseCode
        require(status !in 300..399) {
            "Custom tool redirects are blocked; configure the final HTTPS endpoint"
        }

        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val response = readLimited(stream, "Custom tool response")
        connection.disconnect()

        require(status in 200..299) {
            "Custom tool returned HTTP " + status + ": " + response.take(2_000)
        }
        return response.take(MAX_TEXT_CHARS)
    }

    private fun applySafeHeaders(
        connection: HttpURLConnection,
        headers: Map<String, String>
    ) {
        val forbidden = setOf(
            "host",
            "content-length",
            "connection",
            "transfer-encoding",
            "proxy-authorization",
            "proxy-connection"
        )

        headers.forEach { (rawName, value) ->
            val name = rawName.trim()
            require(name.matches(Regex("""[A-Za-z0-9-]{1,64}"""))) {
                "Invalid HTTP header name"
            }
            require(name.lowercase() !in forbidden) {
                "Header is not allowed: " + name
            }
            require(value.length <= 16_000) { "HTTP header value is too large" }
            connection.setRequestProperty(name, value)
        }
    }

    private fun appendQuery(url: String, args: JSONObject): String {
        if (args.length() == 0) return url

        val parts = ArrayList<String>()
        val keys = args.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val value = args.opt(key)
            if (value == null || value == JSONObject.NULL) continue
            val rendered = when (value) {
                is String, is Number, is Boolean -> value.toString()
                else -> value.toString()
            }
            parts.add(
                URLEncoder.encode(key, Charsets.UTF_8.name()) + "=" +
                    URLEncoder.encode(rendered, Charsets.UTF_8.name())
            )
        }

        if (parts.isEmpty()) return url
        val separator = if (url.contains("?")) "&" else "?"
        return url + separator + parts.joinToString("&")
    }

    private fun request(rawUrl: String, rawHtml: Boolean): String {
        var current = validatePublicHttps(URL(rawUrl))

        repeat(4) { redirectCount ->
            val connection = (current.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 15_000
                readTimeout = 20_000
                instanceFollowRedirects = false
                setRequestProperty("User-Agent", "CodieAI/1.3 (+Android local assistant)")
                setRequestProperty(
                    "Accept",
                    "text/html,text/plain,application/json,application/xml;q=0.8,*/*;q=0.3"
                )
            }

            val status = connection.responseCode
            if (status in 300..399) {
                val location = connection.getHeaderField("Location")
                    ?: throw IllegalStateException("Redirect had no Location header")
                connection.disconnect()
                current = validatePublicHttps(URL(current, location))
                if (redirectCount == 3) throw IllegalStateException("Too many redirects")
                return@repeat
            }

            require(status in 200..299) { "HTTP " + status + " from " + current.host }

            val contentType = connection.contentType.orEmpty().lowercase()
            val allowed =
                contentType.startsWith("text/") ||
                    contentType.contains("json") ||
                    contentType.contains("xml") ||
                    contentType.isBlank()
            require(allowed) { "Unsupported web content type: " + contentType }

            val decoded = readLimited(connection.inputStream, "Web response")
            connection.disconnect()

            if (rawHtml) return decoded

            return if (
                contentType.contains("html") ||
                decoded.trimStart().startsWith("<!DOCTYPE", true) ||
                decoded.trimStart().startsWith("<html", true)
            ) {
                htmlToText(decoded)
            } else {
                decoded
            }
        }

        throw IllegalStateException("Web request did not complete")
    }

    private fun readLimited(
        input: java.io.InputStream?,
        label: String
    ): String {
        if (input == null) return ""
        return input.use { stream ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            var total = 0
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                total += count
                require(total <= MAX_BYTES) { label + " exceeds " + MAX_BYTES + " bytes" }
                output.write(buffer, 0, count)
            }
            output.toByteArray().toString(Charsets.UTF_8)
        }
    }

    private fun validatePublicHttps(url: URL): URL {
        require(url.protocol.equals("https", ignoreCase = true)) {
            "Only public HTTPS URLs are allowed"
        }

        val host = url.host.trim().lowercase()
        require(host.isNotBlank()) { "URL host is blank" }
        require(host != "localhost" && !host.endsWith(".local")) {
            "Local/private hosts are blocked"
        }

        val addresses = InetAddress.getAllByName(host)
        require(addresses.isNotEmpty()) { "Could not resolve host" }
        addresses.forEach { address ->
            require(!isPrivate(address)) { "Private/local network addresses are blocked" }
        }

        return url
    }

    private fun isPrivate(address: InetAddress): Boolean {
        if (
            address.isAnyLocalAddress ||
            address.isLoopbackAddress ||
            address.isLinkLocalAddress ||
            address.isSiteLocalAddress ||
            address.isMulticastAddress
        ) return true

        val bytes = address.address
        if (address is Inet6Address && bytes.isNotEmpty()) {
            val first = bytes[0].toInt() and 0xFF
            if ((first and 0xFE) == 0xFC) return true
        }
        return false
    }

    private fun htmlToText(html: String): String =
        Html.fromHtml(html, Html.FROM_HTML_MODE_LEGACY)
            .toString()
            .replace(Regex("""[\t\x0B\f\r ]+"""), " ")
            .replace(Regex("""\n{3,}"""), "\n\n")
            .trim()

    private fun decodeHtml(value: String): String =
        Html.fromHtml(value, Html.FROM_HTML_MODE_LEGACY).toString()

    private fun resolveDuckDuckGoUrl(raw: String): String {
        val normalized = when {
            raw.startsWith("//") -> "https:" + raw
            raw.startsWith("/") -> "https://duckduckgo.com" + raw
            else -> raw
        }
        return runCatching {
            val uri = Uri.parse(normalized)
            uri.getQueryParameter("uddg") ?: normalized
        }.getOrElse { normalized }
    }
}
