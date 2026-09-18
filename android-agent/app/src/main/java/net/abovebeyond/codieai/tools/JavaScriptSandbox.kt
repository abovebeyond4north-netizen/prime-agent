package net.abovebeyond.codieai.tools

import org.mozilla.javascript.ClassShutter
import org.mozilla.javascript.Context
import org.mozilla.javascript.ContextFactory
import org.mozilla.javascript.EvaluatorException
import org.mozilla.javascript.ScriptableObject
import org.mozilla.javascript.Undefined

object JavaScriptSandbox {
    private const val MAX_CODE_CHARS = 20_000
    private const val MAX_OUTPUT_CHARS = 12_000
    private const val TIMEOUT_NANOS = 2_000_000_000L

    fun execute(code: String): String {
        require(code.length <= MAX_CODE_CHARS) {
            "JavaScript exceeds " + MAX_CODE_CHARS + " characters"
        }

        val deadline = System.nanoTime() + TIMEOUT_NANOS
        val factory = TimedContextFactory(deadline)

        return factory.call { cx ->
            val scope = cx.initSafeStandardObjects(null, true)

            listOf(
                "Packages",
                "java",
                "javax",
                "org",
                "com",
                "edu",
                "net",
                "android",
                "importClass",
                "importPackage",
                "JavaAdapter",
                "getClass"
            ).forEach { ScriptableObject.deleteProperty(scope, it) }

            val result = cx.evaluateString(
                scope,
                code,
                "codie-ai-js-sandbox",
                1,
                null
            )

            ScriptableObject.putProperty(scope, "__codie_result", result)
            val jsonResult = runCatching {
                cx.evaluateString(
                    scope,
                    "JSON.stringify(__codie_result)",
                    "codie-ai-js-result",
                    1,
                    null
                )
            }.getOrNull()

            val rendered = when {
                jsonResult == null || jsonResult === Undefined.instance ->
                    Context.toString(result)
                Context.toString(jsonResult) == "undefined" ->
                    Context.toString(result)
                else -> Context.toString(jsonResult)
            }

            rendered.take(MAX_OUTPUT_CHARS)
        }
    }

    private class TimedContextFactory(
        private val deadlineNanos: Long
    ) : ContextFactory() {
        override fun makeContext(): Context {
            val context = super.makeContext()
            context.optimizationLevel = -1
            context.instructionObserverThreshold = 10_000
            context.setClassShutter(ClassShutter { false })
            return context
        }

        override fun observeInstructionCount(context: Context, instructionCount: Int) {
            if (System.nanoTime() > deadlineNanos) {
                throw EvaluatorException("JavaScript execution exceeded 2 seconds")
            }
        }
    }
}
