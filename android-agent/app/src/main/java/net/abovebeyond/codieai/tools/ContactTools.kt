package net.abovebeyond.codieai.tools

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract

data class ContactMatch(
    val name: String,
    val phone: String = "",
    val email: String = ""
)

object ContactTools {
    fun lookup(context: Context, query: String): Result<ContactMatch> {
        val cleaned = query.trim()
        if (cleaned.isBlank()) {
            return Result.failure(IllegalArgumentException("Contact name is blank"))
        }
        if (context.checkSelfPermission(Manifest.permission.READ_CONTACTS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return Result.failure(
                SecurityException("Contacts permission is required. Use 'Allow contact lookup' in Codie AI.")
            )
        }

        val phones = findPhones(context, cleaned)
        val emails = findEmails(context, cleaned)
        val names = (phones.map { it.first } + emails.map { it.first })
            .distinctBy { it.lowercase() }

        if (names.isEmpty()) {
            return Result.failure(IllegalArgumentException("No contact matched '" + cleaned + "'"))
        }

        val exact = names.firstOrNull { it.equals(cleaned, ignoreCase = true) }
        val chosen = exact ?: if (names.size == 1) names.first() else {
            val preview = names.take(5).joinToString(", ")
            return Result.failure(
                IllegalArgumentException("Multiple contacts matched '" + cleaned + "': " + preview)
            )
        }

        val phone = phones.firstOrNull { it.first.equals(chosen, ignoreCase = true) }?.second.orEmpty()
        val email = emails.firstOrNull { it.first.equals(chosen, ignoreCase = true) }?.second.orEmpty()

        return Result.success(ContactMatch(chosen, phone, email))
    }

    fun describe(context: Context, query: String): Result<String> =
        lookup(context, query).map { match ->
            buildString {
                append("Contact: ").append(match.name)
                if (match.phone.isNotBlank()) append("; phone=").append(match.phone)
                if (match.email.isNotBlank()) append("; email=").append(match.email)
                if (match.phone.isBlank() && match.email.isBlank()) {
                    append("; no phone number or email was available")
                }
            }
        }

    fun dial(context: Context, query: String): Result<String> =
        lookup(context, query).fold(
            onSuccess = { match ->
                if (match.phone.isBlank()) {
                    Result.failure(IllegalStateException(match.name + " has no phone number"))
                } else {
                    runCatching {
                        context.startActivity(
                            Intent(
                                Intent.ACTION_DIAL,
                                Uri.parse("tel:" + Uri.encode(match.phone))
                            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        )
                        "Opened dialer for " + match.name
                    }
                }
            },
            onFailure = { Result.failure(it) }
        )

    fun composeSms(context: Context, query: String, text: String): Result<String> =
        lookup(context, query).fold(
            onSuccess = { match ->
                if (match.phone.isBlank()) {
                    Result.failure(IllegalStateException(match.name + " has no phone number"))
                } else {
                    runCatching {
                        context.startActivity(
                            Intent(
                                Intent.ACTION_SENDTO,
                                Uri.parse("smsto:" + Uri.encode(match.phone))
                            )
                                .putExtra("sms_body", text)
                                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        )
                        "Opened message composer for " + match.name
                    }
                }
            },
            onFailure = { Result.failure(it) }
        )

    fun composeEmail(
        context: Context,
        query: String,
        subject: String,
        text: String
    ): Result<String> =
        lookup(context, query).fold(
            onSuccess = { match ->
                if (match.email.isBlank()) {
                    Result.failure(IllegalStateException(match.name + " has no email address"))
                } else {
                    runCatching {
                        context.startActivity(
                            Intent(
                                Intent.ACTION_SENDTO,
                                Uri.parse("mailto:" + Uri.encode(match.email))
                            )
                                .putExtra(Intent.EXTRA_SUBJECT, subject)
                                .putExtra(Intent.EXTRA_TEXT, text)
                                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        )
                        "Opened email composer for " + match.name
                    }
                }
            },
            onFailure = { Result.failure(it) }
        )

    private fun findPhones(context: Context, query: String): List<Pair<String, String>> {
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        val selection = ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?"
        val args = arrayOf("%" + query + "%")
        val out = ArrayList<Pair<String, String>>()

        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection,
            selection,
            args,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " COLLATE NOCASE ASC"
        )?.use { cursor ->
            val nameIndex = cursor.getColumnIndexOrThrow(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME
            )
            val numberIndex = cursor.getColumnIndexOrThrow(
                ContactsContract.CommonDataKinds.Phone.NUMBER
            )
            while (cursor.moveToNext() && out.size < 20) {
                val name = cursor.getString(nameIndex).orEmpty()
                val number = cursor.getString(numberIndex).orEmpty()
                if (name.isNotBlank() && number.isNotBlank()) out.add(name to number)
            }
        }
        return out.distinct()
    }

    private fun findEmails(context: Context, query: String): List<Pair<String, String>> {
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Email.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Email.ADDRESS
        )
        val selection = ContactsContract.CommonDataKinds.Email.DISPLAY_NAME + " LIKE ?"
        val args = arrayOf("%" + query + "%")
        val out = ArrayList<Pair<String, String>>()

        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Email.CONTENT_URI,
            projection,
            selection,
            args,
            ContactsContract.CommonDataKinds.Email.DISPLAY_NAME + " COLLATE NOCASE ASC"
        )?.use { cursor ->
            val nameIndex = cursor.getColumnIndexOrThrow(
                ContactsContract.CommonDataKinds.Email.DISPLAY_NAME
            )
            val emailIndex = cursor.getColumnIndexOrThrow(
                ContactsContract.CommonDataKinds.Email.ADDRESS
            )
            while (cursor.moveToNext() && out.size < 20) {
                val name = cursor.getString(nameIndex).orEmpty()
                val email = cursor.getString(emailIndex).orEmpty()
                if (name.isNotBlank() && email.isNotBlank()) out.add(name to email)
            }
        }
        return out.distinct()
    }
}
