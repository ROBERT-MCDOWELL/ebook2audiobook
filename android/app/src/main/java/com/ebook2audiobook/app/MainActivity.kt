package com.ebook2audiobook.app

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.view.ViewGroup
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.ebook2audiobook.app.E2aState.Phase
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity(), E2aState.Listener {

    companion object {
        private const val REQ_FILE = 1
        private const val REQ_SAVE = 2
        private const val MENU_TOGGLE = 1
        private const val MENU_UPDATE = 2
        private const val MENU_RESTART = 3
        private const val MENU_STOP = 4
        private const val MENU_COPY_LOG = 5
        private const val MENU_BATTERY = 6
        private const val MENU_RESET = 7
        private const val PREFS = "e2a"
        private const val PREF_PROMPTED = "prompted_v1"
    }

    private val ui = Handler(Looper.getMainLooper())
    private lateinit var panel:LinearLayout
    private lateinit var statusView:TextView
    private lateinit var detailView:TextView
    private lateinit var progressBar:ProgressBar
    private lateinit var scrollView:ScrollView
    private lateinit var logView:TextView
    private lateinit var startButton:Button
    private lateinit var webView:WebView
    private var webLoaded:Boolean = false
    private var showLog:Boolean = false
    private var shownLogVersion:Long = -1
    private var fileCallback:ValueCallback<Array<Uri>>? = null
    private var pendingDownload:String? = null

    private val logTicker = object : Runnable {
        override fun run() {
            refreshLog()
            ui.postDelayed(this, 500)
        }
    }

    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildViews())
        E2aState.addListener(this)
        onPhase(E2aState.phase, E2aState.detail)
        if (!E2aState.isBusy) {
            E2aService.send(this, E2aService.ACTION_START)
        }
        firstRunPrompts()
    }

    override fun onResume() {
        super.onResume()
        ui.post(logTicker)
    }

    override fun onPause() {
        ui.removeCallbacks(logTicker)
        super.onPause()
    }

    override fun onDestroy() {
        E2aState.removeListener(this)
        webView.destroy()
        super.onDestroy()
    }

    private fun dp(value:Int):Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    @SuppressLint("SetJavaScriptEnabled")
    private fun buildViews():View {
        val root = FrameLayout(this)
        panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        statusView = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            setTypeface(typeface, Typeface.BOLD)
        }
        detailView = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setPadding(0, dp(4), 0, dp(8))
        }
        progressBar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = true
        }
        logView = TextView(this).apply {
            typeface = Typeface.MONOSPACE
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 11f)
            setTextIsSelectable(true)
        }
        scrollView = ScrollView(this).apply {
            addView(logView)
        }
        startButton = Button(this).apply {
            text = getString(R.string.action_retry)
            setOnClickListener { E2aService.send(this@MainActivity, E2aService.ACTION_START) }
        }
        panel.addView(statusView)
        panel.addView(detailView)
        panel.addView(progressBar, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        panel.addView(scrollView, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f).apply { topMargin = dp(8) })
        panel.addView(startButton, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { gravity = Gravity.END })

        webView = WebView(this).apply {
            visibility = View.GONE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.allowFileAccess = false
            settings.builtInZoomControls = true
            settings.displayZoomControls = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view:WebView, request:WebResourceRequest):Boolean {
                    val host = request.url.host
                    if (host == "127.0.0.1" || host == "localhost") {
                        return false
                    }
                    // documentation, model pages, ...: the browser
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, request.url))
                    } catch (_:ActivityNotFoundException) {
                    }
                    return true
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(view:WebView, callback:ValueCallback<Array<Uri>>, params:FileChooserParams):Boolean {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = callback
                    // gradio passes extensions (.epub, ...) Android cannot map to mime types: offer every file
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
                    if (params.mode == FileChooserParams.MODE_OPEN_MULTIPLE) {
                        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    }
                    return try {
                        startActivityForResult(intent, REQ_FILE)
                        true
                    } catch (_:ActivityNotFoundException) {
                        fileCallback = null
                        false
                    }
                }
            }
            setDownloadListener { url, _, contentDisposition, mimetype, _ -> download(url, contentDisposition, mimetype) }
        }
        root.addView(panel, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        root.addView(webView, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        return root
    }

    override fun onPhase(phase:Phase, detail:String) {
        statusView.text = getString(when (phase) {
            Phase.IDLE -> R.string.phase_idle
            Phase.PREPARING -> R.string.phase_preparing
            Phase.INSTALLING -> R.string.phase_installing
            Phase.STARTING -> R.string.phase_starting
            Phase.READY -> R.string.phase_ready
            Phase.STOPPING -> R.string.phase_stopping
            Phase.STOPPED -> R.string.phase_stopped
            Phase.FAILED -> R.string.phase_failed
        })
        detailView.text = detail
        progressBar.visibility = if (phase in setOf(Phase.PREPARING, Phase.INSTALLING, Phase.STARTING, Phase.STOPPING)) View.VISIBLE else View.GONE
        startButton.visibility = if (phase in setOf(Phase.IDLE, Phase.STOPPED, Phase.FAILED)) View.VISIBLE else View.GONE
        if (phase == Phase.READY) {
            if (!webLoaded) {
                webView.loadUrl(E2aService.SERVER_URL)
                webLoaded = true
            }
        } else {
            // the server is gone: the page is dead, reload it on the next READY
            webLoaded = false
            showLog = false
        }
        updateVisibility()
        invalidateOptionsMenu()
    }

    private fun updateVisibility() {
        val web = E2aState.phase == Phase.READY && !showLog
        webView.visibility = if (web) View.VISIBLE else View.GONE
        panel.visibility = if (web) View.GONE else View.VISIBLE
        if (!web) {
            refreshLog()
        }
    }

    private fun refreshLog() {
        if (panel.visibility != View.VISIBLE || shownLogVersion == E2aState.logVersion) {
            return
        }
        shownLogVersion = E2aState.logVersion
        val atBottom = !scrollView.canScrollVertically(1)
        logView.text = E2aState.snapshot()
        if (atBottom) {
            scrollView.post { scrollView.fullScroll(View.FOCUS_DOWN) }
        }
    }

    override fun onCreateOptionsMenu(menu:Menu):Boolean {
        if (E2aState.phase == Phase.READY) {
            menu.add(0, MENU_TOGGLE, 0, if (showLog) R.string.action_show_ui else R.string.action_show_log)
        }
        menu.add(0, MENU_UPDATE, 1, R.string.action_update)
        menu.add(0, MENU_RESTART, 2, R.string.action_restart)
        if (E2aState.isBusy) {
            menu.add(0, MENU_STOP, 3, R.string.action_stop)
        }
        menu.add(0, MENU_COPY_LOG, 4, R.string.action_copy_log)
        menu.add(0, MENU_BATTERY, 5, R.string.action_battery)
        menu.add(0, MENU_RESET, 6, R.string.action_reset)
        return true
    }

    override fun onPrepareOptionsMenu(menu:Menu):Boolean {
        menu.clear()
        return onCreateOptionsMenu(menu)
    }

    override fun onOptionsItemSelected(item:MenuItem):Boolean {
        when (item.itemId) {
            MENU_TOGGLE -> {
                showLog = !showLog
                updateVisibility()
                invalidateOptionsMenu()
            }
            MENU_UPDATE -> E2aService.send(this, E2aService.ACTION_UPDATE)
            MENU_RESTART -> E2aService.send(this, E2aService.ACTION_RESTART)
            MENU_STOP -> E2aService.send(this, E2aService.ACTION_STOP)
            MENU_COPY_LOG -> {
                getSystemService(ClipboardManager::class.java)!!.setPrimaryClip(ClipData.newPlainText("ebook2audiobook log", E2aState.snapshot()))
                Toast.makeText(this, R.string.log_copied, Toast.LENGTH_SHORT).show()
            }
            MENU_BATTERY -> openBatterySettings()
            MENU_RESET -> AlertDialog.Builder(this)
                .setTitle(R.string.dialog_reset_title)
                .setMessage(R.string.dialog_reset_msg)
                .setPositiveButton(R.string.dialog_ok) { _, _ -> E2aService.send(this, E2aService.ACTION_RESET) }
                .setNegativeButton(R.string.dialog_cancel, null)
                .show()
            else -> return super.onOptionsItemSelected(item)
        }
        return true
    }

    @Deprecated("Activity back handling, kept for API 26+")
    override fun onBackPressed() {
        when {
            webView.visibility == View.VISIBLE && webView.canGoBack() -> webView.goBack()
            showLog && E2aState.phase == Phase.READY -> {
                showLog = false
                updateVisibility()
                invalidateOptionsMenu()
            }
            // the server keeps running in the foreground service
            else -> moveTaskToBack(true)
        }
    }

    private fun download(url:String, contentDisposition:String?, mimetype:String?) {
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            Toast.makeText(this, R.string.download_unsupported, Toast.LENGTH_LONG).show()
            return
        }
        val name = URLUtil.guessFileName(url, contentDisposition, mimetype)
        pendingDownload = url
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType(mimetype?.takeIf { it.isNotBlank() } ?: "application/octet-stream")
            .putExtra(Intent.EXTRA_TITLE, name)
        try {
            startActivityForResult(intent, REQ_SAVE)
        } catch (_:ActivityNotFoundException) {
            pendingDownload = null
            Toast.makeText(this, R.string.download_unsupported, Toast.LENGTH_LONG).show()
        }
    }

    /** Streams the file from the e2a server into the document the user picked (no storage permission needed). */
    private fun save(url:String, target:Uri) {
        Thread({
            val result = try {
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.connectTimeout = 10000
                conn.readTimeout = 120000
                try {
                    if (conn.responseCode != 200) {
                        throw IOException("HTTP ${conn.responseCode}")
                    }
                    val out = contentResolver.openOutputStream(target) ?: throw IOException("cannot open $target")
                    out.use { stream -> conn.inputStream.use { it.copyTo(stream, 1 shl 16) } }
                } finally {
                    conn.disconnect()
                }
                getString(R.string.download_saved, target.lastPathSegment ?: "")
            } catch (e:Exception) {
                getString(R.string.download_failed, e.message ?: e.javaClass.simpleName)
            }
            ui.post { Toast.makeText(this, result, Toast.LENGTH_LONG).show() }
        }, "e2a-save").start()
    }

    override fun onActivityResult(requestCode:Int, resultCode:Int, data:Intent?) {
        when (requestCode) {
            REQ_FILE -> {
                var uris:Array<Uri>? = null
                if (resultCode == RESULT_OK && data != null) {
                    val clip = data.clipData
                    uris = if (clip != null) Array(clip.itemCount) { clip.getItemAt(it).uri } else data.data?.let { arrayOf(it) }
                }
                fileCallback?.onReceiveValue(uris)
                fileCallback = null
            }
            REQ_SAVE -> {
                val url = pendingDownload
                pendingDownload = null
                val target = data?.data
                if (resultCode == RESULT_OK && url != null && target != null) {
                    save(url, target)
                }
            }
            else -> super.onActivityResult(requestCode, resultCode, data)
        }
    }

    private fun firstRunPrompts() {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        if (prefs.getBoolean(PREF_PROMPTED, false)) {
            return
        }
        prefs.edit().putBoolean(PREF_PROMPTED, true).apply()
        val power = getSystemService(PowerManager::class.java)!!
        val phantom = {
            if (Build.VERSION.SDK_INT >= 31 && Settings.Global.getString(contentResolver, "settings_enable_monitor_phantom_procs") != "false") {
                AlertDialog.Builder(this)
                    .setTitle(R.string.dialog_phantom_title)
                    .setMessage(R.string.dialog_phantom_msg)
                    .setPositiveButton(R.string.dialog_open_settings) { _, _ -> openSettings(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS) }
                    .setNegativeButton(R.string.dialog_later, null)
                    .show()
            }
        }
        if (!power.isIgnoringBatteryOptimizations(packageName)) {
            AlertDialog.Builder(this)
                .setTitle(R.string.dialog_battery_title)
                .setMessage(R.string.dialog_battery_msg)
                .setPositiveButton(R.string.dialog_ok) { _, _ -> openBatterySettings() }
                .setNegativeButton(R.string.dialog_later, null)
                .setOnDismissListener { phantom() }
                .show()
        } else {
            phantom()
        }
    }

    @SuppressLint("BatteryLife")
    private fun openBatterySettings() {
        val power = getSystemService(PowerManager::class.java)!!
        if (!power.isIgnoringBatteryOptimizations(packageName)) {
            try {
                startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
                return
            } catch (_:ActivityNotFoundException) {
            }
        }
        openSettings(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))
    }

    private fun openSettings(action:String, uri:Uri? = null) {
        try {
            val intent = Intent(action)
            if (uri != null) {
                intent.data = uri
            }
            startActivity(intent)
        } catch (_:ActivityNotFoundException) {
            startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }
}
