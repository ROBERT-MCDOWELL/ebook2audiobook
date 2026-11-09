package com.ebook2audiobook.app

import android.app.ActivityManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.system.Os
import com.ebook2audiobook.app.E2aState.Phase
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/**
 * Foreground service owning the e2a process: rootfs install on first run, then proot -> bash -> the e2a launcher,
 * which provisions python/uv/engines itself and serves gradio on 127.0.0.1:7860.
 */
class E2aService : Service() {

    companion object {
        const val ACTION_START = "com.ebook2audiobook.app.START"
        const val ACTION_STOP = "com.ebook2audiobook.app.STOP"
        const val ACTION_RESTART = "com.ebook2audiobook.app.RESTART"
        const val ACTION_UPDATE = "com.ebook2audiobook.app.UPDATE"
        const val ACTION_RESET = "com.ebook2audiobook.app.RESET"
        const val SERVER_URL = "http://127.0.0.1:7860/"
        private const val CHANNEL_ID = "e2a"
        private const val NOTIFICATION_ID = 1
        private const val GUEST_SCRIPT = "/usr/local/bin/e2a-android"
        private val ANSI = Regex("\u001B\\[[0-9;?]*[ -/]*[@-~]|\u001B[()][0-9A-B]")

        fun send(context:Context, action:String) {
            context.startForegroundService(Intent(context, E2aService::class.java).setAction(action))
        }
    }

    private val ui = Handler(Looper.getMainLooper())
    @Volatile private var worker:Thread? = null
    @Volatile private var process:Process? = null
    @Volatile private var pid:Int = -1
    @Volatile private var stopRequested:Boolean = false
    private var pendingAction:String? = null
    private var wakeLock:PowerManager.WakeLock? = null
    private var wifiLock:WifiManager.WifiLock? = null
    private var lastNotification:Long = 0

    override fun onBind(intent:Intent?):IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val channel = NotificationChannel(CHANNEL_ID, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW)
        getSystemService(NotificationManager::class.java)!!.createNotificationChannel(channel)
    }

    override fun onStartCommand(intent:Intent?, flags:Int, startId:Int):Int {
        startForeground(NOTIFICATION_ID, notification(phaseText()))
        when (intent?.action ?: ACTION_START) {
            ACTION_STOP -> stop(null)
            ACTION_RESTART -> if (isRunning()) stop(ACTION_START) else launch(ACTION_START)
            ACTION_UPDATE -> if (isRunning()) stop(ACTION_UPDATE) else launch(ACTION_UPDATE)
            ACTION_RESET -> if (isRunning()) stop(ACTION_RESET) else launch(ACTION_RESET)
            else -> if (!isRunning()) launch(ACTION_START)
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        releaseLocks()
        super.onDestroy()
    }

    private fun isRunning():Boolean = worker?.isAlive == true

    private fun launch(action:String) {
        stopRequested = false
        acquireLocks()
        worker = Thread({ run(action) }, "e2a-runner").also { it.start() }
    }

    private fun stop(next:String?) {
        pendingAction = next
        if (!isRunning()) {
            onWorkerDone()
            return
        }
        stopRequested = true
        E2aState.setPhase(Phase.STOPPING)
        val target = pid
        Thread({
            // SIGQUIT makes proot kill every process of the rootfs before exiting (SIGKILL would orphan them)
            if (target > 0) {
                android.os.Process.sendSignal(target, android.os.Process.SIGNAL_QUIT)
            }
            val proc = process
            if (proc != null && !proc.waitFor(15, TimeUnit.SECONDS)) {
                proc.destroyForcibly()
            }
        }, "e2a-stop").start()
    }

    private fun onWorkerDone() {
        releaseLocks()
        val next = pendingAction
        pendingAction = null
        if (next != null) {
            launch(next)
        } else {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private fun run(action:String) {
        val logFile = LogFile(File(filesDir, "logs"))
        val log:(String)->Unit = { line ->
            E2aState.log(line)
            logFile.write(line)
        }
        try {
            E2aState.setPhase(Phase.PREPARING)
            val rootfs = File(filesDir, "rootfs")
            if (action == ACTION_RESET) {
                log("Removing the Linux environment…")
                RootfsInstaller.deleteTree(rootfs)
                RootfsInstaller.deleteTree(File(filesDir, "rootfs.partial"))
            }
            val machine = Os.uname().machine
            val arch = when (machine) {
                "aarch64" -> "arm64"
                "x86_64" -> "amd64"
                else -> throw IOException(getString(R.string.error_arch, machine))
            }
            checkResources(log)
            val installer = RootfsInstaller(rootfs, cacheDir, log, { msg -> setProgress(Phase.INSTALLING, msg) }, { stopRequested })
            if (!installer.isInstalled()) {
                log(getString(R.string.log_installing_rootfs, arch))
                setProgress(Phase.INSTALLING, getString(R.string.phase_installing))
                installer.install(arch)
            }
            installer.configure(dnsServers(), Runtime.getRuntime().availableProcessors())
            installGuestScript(rootfs)
            if (stopRequested) {
                E2aState.setPhase(Phase.STOPPED)
                return
            }
            val proot = Proot(this, rootfs)
            proot.prepare()
            // sh prints its pid then execs proot in place: that pid is proot's, needed to stop it cleanly
            val cmd = listOf("/system/bin/sh", "-c", "echo \"E2A_PID=\$\$\"; exec \"\$@\"", "e2a") + proot.command(listOf("/bin/bash", GUEST_SCRIPT), guestEnv(action == ACTION_UPDATE))
            val builder = ProcessBuilder(cmd).redirectErrorStream(true).directory(filesDir)
            builder.environment().putAll(proot.hostEnv())
            setProgress(Phase.STARTING, getString(R.string.phase_starting_detail))
            val proc = builder.start()
            process = proc
            watchServer(proc)
            readOutput(proc.inputStream, log)
            val code = proc.waitFor()
            if (stopRequested) {
                E2aState.setPhase(Phase.STOPPED)
            } else {
                E2aState.setPhase(Phase.FAILED, getString(R.string.error_exit, code))
            }
        } catch (e:Exception) {
            if (stopRequested) {
                E2aState.setPhase(Phase.STOPPED)
            } else {
                log("ERROR: ${e.message ?: e.javaClass.simpleName}")
                E2aState.setPhase(Phase.FAILED, e.message ?: e.javaClass.simpleName)
            }
        } finally {
            process = null
            pid = -1
            logFile.close()
            ui.post { onWorkerDone() }
        }
    }

    private fun guestEnv(update:Boolean):Map<String, String> = mapOf(
        "HOME" to "/root",
        "USER" to "root",
        "LOGNAME" to "root",
        "SHELL" to "/bin/bash",
        "LANG" to "C.UTF-8",
        "TERM" to "dumb",
        "TMPDIR" to "/tmp",
        "PATH" to "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "DEBIAN_FRONTEND" to "noninteractive",
        "PYTHONUNBUFFERED" to "1",
        "E2A_ANDROID" to "1",
        // gradio on the loopback only: the phone may sit on a public Wi-Fi
        "E2A_INTERFACE_HOST" to "127.0.0.1",
        "E2A_REPO" to BuildConfig.E2A_REPO,
        "E2A_BRANCH" to BuildConfig.E2A_BRANCH,
        "E2A_UPDATE" to if (update) "1" else "0",
    )

    private fun installGuestScript(rootfs:File) {
        val script = File(rootfs, GUEST_SCRIPT.removePrefix("/"))
        script.parentFile?.mkdirs()
        assets.open("e2a-android.sh").use { input -> FileOutputStream(script).use { input.copyTo(it) } }
        Os.chmod(script.path, "755".toInt(8))
    }

    private fun watchServer(proc:Process) {
        Thread({
            while (proc.isAlive && !stopRequested) {
                if (E2aState.phase != Phase.READY && serverUp()) {
                    E2aState.setPhase(Phase.READY)
                    updateNotification(getString(R.string.phase_ready), force = true)
                }
                SystemClock.sleep(2000)
            }
        }, "e2a-watch").apply {
            isDaemon = true
            start()
        }
    }

    private fun serverUp():Boolean = try {
        val conn = URL(SERVER_URL).openConnection() as HttpURLConnection
        conn.connectTimeout = 1500
        conn.readTimeout = 5000
        conn.instanceFollowRedirects = false
        val code = conn.responseCode
        conn.disconnect()
        code in 200..399
    } catch (e:IOException) {
        false
    }

    /** Splits on \n and \r (progress lines), drops ANSI colors, catches the pid line printed by the sh wrapper. */
    private fun readOutput(input:InputStream, log:(String)->Unit) {
        val reader = InputStreamReader(input, Charsets.UTF_8)
        val line = StringBuilder()
        val buf = CharArray(8192)
        fun emit() {
            val text = ANSI.replace(line.toString(), "").trimEnd()
            line.setLength(0)
            if (pid < 0 && text.startsWith("E2A_PID=")) {
                pid = text.substringAfter('=').trim().toIntOrNull() ?: -1
            } else if (text.isNotBlank()) {
                log(text)
            }
        }
        while (true) {
            val n = reader.read(buf)
            if (n < 0) {
                break
            }
            for (i in 0 until n) {
                val ch = buf[i]
                if (ch == '\n' || ch == '\r') {
                    if (line.isNotEmpty()) {
                        emit()
                    }
                } else if (line.length < 4000) {
                    line.append(ch)
                }
            }
        }
        if (line.isNotEmpty()) {
            emit()
        }
    }

    private fun checkResources(log:(String)->Unit) {
        val freeGb = (filesDir.usableSpace shr 30).toInt()
        if (freeGb < 15) {
            log(getString(R.string.warn_storage, freeGb))
        }
        val mem = ActivityManager.MemoryInfo()
        getSystemService(ActivityManager::class.java)!!.getMemoryInfo(mem)
        val ramGb = ((mem.totalMem + (1L shl 29)) shr 30).toInt()
        if (ramGb < 8) {
            log(getString(R.string.warn_ram, ramGb))
        }
    }

    private fun dnsServers():List<String> = try {
        val cm = getSystemService(ConnectivityManager::class.java)!!
        val props = cm.activeNetwork?.let { cm.getLinkProperties(it) }
        props?.dnsServers.orEmpty().mapNotNull { it.hostAddress }.filter { !it.contains('%') }
    } catch (e:Exception) {
        emptyList()
    }

    private fun setProgress(phase:Phase, text:String) {
        E2aState.setPhase(phase, text)
        updateNotification(text)
    }

    private fun phaseText():String = when (E2aState.phase) {
        Phase.READY -> getString(R.string.phase_ready)
        Phase.INSTALLING -> getString(R.string.phase_installing)
        else -> getString(R.string.phase_starting)
    }

    private fun updateNotification(text:String, force:Boolean = false) {
        val now = SystemClock.elapsedRealtime()
        if (!force && now - lastNotification < 1000) {
            return
        }
        lastNotification = now
        getSystemService(NotificationManager::class.java)!!.notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text:String):Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop = PendingIntent.getService(this, 1, Intent(this, E2aService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(Notification.Action.Builder(null as Icon?, getString(R.string.action_stop), stop).build())
            .build()
    }

    @Suppress("DEPRECATION")
    private fun acquireLocks() {
        if (wakeLock == null) {
            wakeLock = getSystemService(PowerManager::class.java)!!.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "e2a:runner").apply {
                setReferenceCounted(false)
                acquire()
            }
        }
        if (wifiLock == null) {
            wifiLock = (applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager).createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "e2a:runner").apply {
                setReferenceCounted(false)
                acquire()
            }
        }
    }

    private fun releaseLocks() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        wifiLock?.let { if (it.isHeld) it.release() }
        wifiLock = null
    }

    /** Full log on disk (the UI keeps the last lines only), rotated at 5 MB. */
    private class LogFile(dir:File) {
        private val writer:PrintWriter?

        init {
            dir.mkdirs()
            val file = File(dir, "e2a.log")
            if (file.length() > 5L shl 20) {
                file.renameTo(File(dir, "e2a.log.1"))
            }
            writer = try { PrintWriter(FileOutputStream(file, true).bufferedWriter(), true) } catch (e:IOException) { null }
        }

        fun write(line:String) {
            writer?.println(line)
        }

        fun close() {
            writer?.close()
        }
    }
}
