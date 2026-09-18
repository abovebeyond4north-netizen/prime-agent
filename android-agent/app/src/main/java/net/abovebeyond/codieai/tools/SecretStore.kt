package net.abovebeyond.codieai.tools

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object SecretStore {
    private const val PREFS = "codie_ai_secret_vault"
    private const val KEY_ALIAS = "codie_ai_tool_vault_key"
    private const val MAX_SECRET_CHARS = 16_000
    private const val MAX_SECRETS = 40

    fun put(context: Context, alias: String, secret: String): String {
        val cleaned = normalizeAlias(alias)
        require(secret.isNotBlank()) { "Secret value is blank" }
        require(secret.length <= MAX_SECRET_CHARS) {
            "Secret exceeds " + MAX_SECRET_CHARS + " characters"
        }

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains(cleaned) && prefs.all.size >= MAX_SECRETS) {
            throw IllegalStateException("Secret vault is full")
        }

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val ciphertext = cipher.doFinal(secret.toByteArray(Charsets.UTF_8))
        val stored = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" +
            Base64.encodeToString(ciphertext, Base64.NO_WRAP)

        prefs.edit().putString(cleaned, stored).apply()
        return "Stored encrypted secret alias '" + cleaned + "'"
    }

    fun listAliases(context: Context): String {
        val keys = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .all.keys.sorted()
        return if (keys.isEmpty()) "No connector secrets stored."
        else "Stored secret aliases:\n" + keys.joinToString("\n") { "- " + it }
    }

    fun delete(context: Context, alias: String): String {
        val cleaned = normalizeAlias(alias)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        require(prefs.contains(cleaned)) { "Secret alias not found: " + cleaned }
        prefs.edit().remove(cleaned).apply()
        return "Deleted secret alias '" + cleaned + "'"
    }

    fun exists(context: Context, alias: String): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .contains(normalizeAlias(alias))

    internal fun resolve(context: Context, alias: String): String {
        val cleaned = normalizeAlias(alias)
        val stored = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(cleaned, null)
            ?: throw IllegalArgumentException("Secret alias not found: " + cleaned)

        val parts = stored.split(':', limit = 2)
        require(parts.size == 2) { "Stored secret is corrupted" }

        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[1], Base64.NO_WRAP)

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        return cipher.doFinal(ciphertext).toString(Charsets.UTF_8)
    }

    private fun normalizeAlias(alias: String): String {
        val cleaned = alias.trim().lowercase()
        require(cleaned.matches(Regex("""[a-z][a-z0-9_.-]{1,63}"""))) {
            "Secret alias must match [a-z][a-z0-9_.-]{1,63}"
        }
        return cleaned
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing = store.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) return existing

        val generator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore"
        )
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }
}
