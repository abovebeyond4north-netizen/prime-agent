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
        val compactSnapshot = if (snapshot.length > 10_500) snapshot.take(10_500) else snapshot
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
                maxNumTokens = 4096,
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
                    maxNumTokens = 4096,
                    cacheDir = cacheDir.absolutePath
                )
            )
            cpu.initialize()
            engine = cpu
            return cpu
        }
    }
}
