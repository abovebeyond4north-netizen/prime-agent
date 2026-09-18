package net.abovebeyond.codieai.agent

import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.LogSeverity
import java.io.File

class LiteRtPlanner(
    private val modelFile: File,
    private val cacheDir: File
) : Planner {
    @Volatile
    private var engine: Engine? = null

    override fun nextAction(goal: String, snapshot: String, step: Int): AgentAction {
        val activeEngine = getOrCreateEngine()
        val config = ConversationConfig(systemInstruction = Contents.of(PlannerPrompt.system))
        val compactSnapshot = snapshot.take(MAX_STATE_CHARS)
        val response = activeEngine.createConversation(config).use { conversation ->
            conversation.sendMessage(PlannerPrompt.user(goal, compactSnapshot, step)).toString()
        }
        return AgentAction.parse(response)
    }

    @Synchronized
    private fun getOrCreateEngine(): Engine {
        engine?.let { return it }
        require(modelFile.isFile) { "Local model not found: " + modelFile.absolutePath }
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)

        val gpu = Engine(
            EngineConfig(
                modelPath = modelFile.absolutePath,
                backend = Backend.GPU(),
                maxNumTokens = MAX_CONTEXT_TOKENS,
                cacheDir = cacheDir.absolutePath
            )
        )
        try {
            gpu.initialize()
            engine = gpu
            return gpu
        } catch (_: Throwable) {
            val cpu = Engine(
                EngineConfig(
                    modelPath = modelFile.absolutePath,
                    backend = Backend.CPU(),
                    maxNumTokens = MAX_CONTEXT_TOKENS,
                    cacheDir = cacheDir.absolutePath
                )
            )
            cpu.initialize()
            engine = cpu
            return cpu
        }
    }

    companion object {
        private const val MAX_CONTEXT_TOKENS = 8192
        private const val MAX_STATE_CHARS = 8_000
    }
}
