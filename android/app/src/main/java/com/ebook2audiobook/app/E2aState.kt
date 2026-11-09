package com.ebook2audiobook.app

import android.os.Handler
import android.os.Looper
import java.util.concurrent.CopyOnWriteArrayList

/** Process-wide state shared by E2aService (writer) and MainActivity (reader). */
object E2aState {

    enum class Phase { IDLE, PREPARING, INSTALLING, STARTING, READY, STOPPING, STOPPED, FAILED }

    fun interface Listener {
        fun onPhase(phase:Phase, detail:String)
    }

    private const val MAX_LINES = 400
    private val main = Handler(Looper.getMainLooper())
    private val listeners = CopyOnWriteArrayList<Listener>()
    private val lines = ArrayDeque<String>()

    @Volatile var phase:Phase = Phase.IDLE
        private set
    @Volatile var detail:String = ""
        private set
    // bumped on every log line: the activity redraws only when it changed
    @Volatile var logVersion:Long = 0
        private set

    val isBusy:Boolean
        get() = phase in setOf(Phase.PREPARING, Phase.INSTALLING, Phase.STARTING, Phase.READY, Phase.STOPPING)

    fun addListener(listener:Listener) {
        listeners.add(listener)
    }

    fun removeListener(listener:Listener) {
        listeners.remove(listener)
    }

    fun setPhase(newPhase:Phase, newDetail:String = "") {
        phase = newPhase
        detail = newDetail
        main.post { listeners.forEach { it.onPhase(newPhase, newDetail) } }
    }

    fun log(line:String) {
        synchronized(lines) {
            lines.addLast(line)
            while (lines.size > MAX_LINES) {
                lines.removeFirst()
            }
            logVersion++
        }
    }

    fun snapshot():String = synchronized(lines) { lines.joinToString("\n") }
}
