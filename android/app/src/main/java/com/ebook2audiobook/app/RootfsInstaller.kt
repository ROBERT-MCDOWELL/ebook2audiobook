package com.ebook2audiobook.app

import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.io.InterruptedIOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.GZIPInputStream

/**
 * Downloads and unpacks the official Ubuntu 24.04 base rootfs (glibc userland: uv's python and every manylinux
 * wheel e2a installs run there, which Android's own libc cannot), then keeps it configured for proot.
 */
class RootfsInstaller(private val rootfs:File, private val cacheDir:File, private val log:(String)->Unit, private val progress:(String)->Unit, private val isCancelled:()->Boolean) {

    companion object {
        const val UBUNTU_BASE_URL = "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/"
        const val MARKER = ".e2a_rootfs"
        const val FAKE_PROC_DIR = ".e2a/proc"
        val FAKE_PROC_FILES = listOf("loadavg", "stat", "uptime", "version", "vmstat")
        private val MODE_FILE = "777".toInt(8)
        private val MODE_DIR = "1777".toInt(8)
        private val MODE_OWNER_RWX = "700".toInt(8)
        private val MODE_EXEC = "755".toInt(8)
        private const val BUFFER = 1 shl 16

        /** rm -rf that never follows symlinks out of the tree. */
        fun deleteTree(file:File) {
            val st = try { Os.lstat(file.path) } catch (e:ErrnoException) { return }
            if (OsConstants.S_ISDIR(st.st_mode)) {
                try { Os.chmod(file.path, MODE_OWNER_RWX) } catch (_:ErrnoException) {}
                file.list()?.forEach { deleteTree(File(file, it)) }
            }
            file.delete()
        }
    }

    fun isInstalled():Boolean = File(rootfs, MARKER).isFile

    fun install(arch:String) {
        val (name, sha256) = latestTarball(arch)
        log("Ubuntu base: $name")
        val tarball = download(name, sha256)
        val partial = File(rootfs.parentFile, rootfs.name + ".partial")
        deleteTree(partial)
        extract(tarball, partial)
        deleteTree(rootfs)
        if (!partial.renameTo(rootfs)) {
            throw IOException("cannot move $partial to $rootfs")
        }
        File(rootfs, MARKER).writeText(name + "\n")
        tarball.delete()
        log("Linux environment installed.")
    }

    /** Called before every start: the network (DNS) can change between runs and app updates refresh the helpers. */
    fun configure(dnsServers:List<String>, cpuCount:Int) {
        val etc = File(rootfs, "etc")
        // ubuntu-base ships resolv.conf as a link to systemd-resolved, which does not exist here
        val resolv = File(etc, "resolv.conf")
        resolv.delete()
        val servers = (dnsServers + listOf("8.8.8.8", "1.1.1.1")).distinct().take(3)
        resolv.writeText(servers.joinToString("") { "nameserver $it\n" })
        File(etc, "hosts").writeText("127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n")
        File(etc, "hostname").writeText("localhost\n")
        // apt drops privileges to _apt, which a fake root cannot do
        File(etc, "apt/apt.conf.d/99-e2a-android").apply {
            parentFile?.mkdirs()
            writeText("APT::Sandbox::User \"root\";\nAcquire::Retries \"3\";\nDPkg::Use-Pty \"0\";\n")
        }
        // everything already runs as root: sudo is a pass-through, so any launcher version works
        File(rootfs, "usr/local/bin/sudo").apply {
            parentFile?.mkdirs()
            writeText(SUDO_SHIM)
            Os.chmod(path, MODE_EXEC)
        }
        File(rootfs, "tmp").apply {
            mkdirs()
            Os.chmod(path, MODE_DIR)
        }
        // replacements for the /proc entries Android hides from apps, bound only when unreadable (see Proot)
        val fakeProc = File(rootfs, FAKE_PROC_DIR)
        fakeProc.mkdirs()
        File(fakeProc, "loadavg").writeText("0.12 0.07 0.02 2/165 765\n")
        File(fakeProc, "uptime").writeText("124.08 932.80\n")
        File(fakeProc, "version").writeText("Linux version ${System.getProperty("os.version") ?: "6.1.0"} (e2a@android) #1 SMP PREEMPT\n")
        File(fakeProc, "vmstat").writeText(FAKE_VMSTAT)
        File(fakeProc, "stat").writeText(buildString {
            append("cpu  1957 0 2877 93280 262 342 254 87 0 0\n")
            for (cpu in 0 until cpuCount) {
                append("cpu$cpu 31 0 226 12027 82 10 4 9 0 0\n")
            }
            append("intr 63361 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\nctxt 38014093\nbtime 1694292441\nprocesses 26442\nprocs_running 1\nprocs_blocked 0\nsoftirq 75663 0 5903 6 25375 10774 0 243 11685 0 21677\n")
        })
    }

    private fun latestTarball(arch:String):Pair<String, String> {
        val sums = retry("SHA256SUMS") { httpText(UBUNTU_BASE_URL + "SHA256SUMS") }
        val pattern = Regex("^([0-9a-f]{64}) \\*?(ubuntu-base-24\\.04(?:\\.(\\d+))?-base-${Regex.escape(arch)}\\.tar\\.gz)$")
        val best = sums.lineSequence()
            .mapNotNull { pattern.find(it.trim()) }
            .maxByOrNull { it.groupValues[3].toIntOrNull() ?: 0 }
            ?: throw IOException("no Ubuntu base tarball for $arch in $UBUNTU_BASE_URL")
        return best.groupValues[2] to best.groupValues[1]
    }

    private fun download(name:String, sha256:String):File {
        val dir = File(cacheDir, "rootfs")
        dir.mkdirs()
        val file = File(dir, name)
        if (file.isFile && sha256Of(file) == sha256) {
            return file
        }
        dir.listFiles()?.filter { it.name != "$name.part" }?.forEach { it.delete() }
        val part = File(dir, "$name.part")
        retry(name) { fetch(UBUNTU_BASE_URL + name, part) }
        if (sha256Of(part) != sha256) {
            part.delete()
            throw IOException("checksum mismatch for $name")
        }
        if (!part.renameTo(file)) {
            throw IOException("cannot rename $part")
        }
        return file
    }

    private fun <T> retry(what:String, block:()->T):T {
        var attempt = 0
        while (true) {
            try {
                return block()
            } catch (e:InterruptedIOException) {
                throw e
            } catch (e:IOException) {
                attempt++
                if (attempt >= 5) {
                    throw e
                }
                log("Download of $what interrupted (${e.message}), retry $attempt/4…")
                Thread.sleep(3000L * attempt)
            }
        }
    }

    private fun httpText(url:String):String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 30000
        conn.readTimeout = 60000
        try {
            if (conn.responseCode != 200) {
                throw IOException("HTTP ${conn.responseCode} for $url")
            }
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    private fun fetch(url:String, part:File) {
        val have = if (part.isFile) part.length() else 0L
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 30000
        conn.readTimeout = 60000
        if (have > 0) {
            conn.setRequestProperty("Range", "bytes=$have-")
        }
        try {
            val code = conn.responseCode
            if (code != 200 && code != 206) {
                throw IOException("HTTP $code for $url")
            }
            val append = code == 206
            var done = if (append) have else 0L
            val total = done + conn.contentLengthLong
            var reported = 0L
            FileOutputStream(part, append).use { out ->
                conn.inputStream.use { input ->
                    val buf = ByteArray(BUFFER)
                    while (true) {
                        if (isCancelled()) {
                            throw InterruptedIOException("cancelled")
                        }
                        val n = input.read(buf)
                        if (n < 0) {
                            break
                        }
                        out.write(buf, 0, n)
                        done += n
                        if (total > 0 && done - reported >= 1_000_000) {
                            reported = done
                            progress("Downloading Ubuntu base… ${done * 100 / total}% (${done shr 20} MB)")
                        }
                    }
                }
            }
        } finally {
            conn.disconnect()
        }
    }

    private fun sha256Of(file:File):String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buf = ByteArray(BUFFER)
            while (true) {
                val n = input.read(buf)
                if (n < 0) {
                    break
                }
                digest.update(buf, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun extract(tarball:File, dest:File) {
        dest.mkdirs()
        // directory modes are applied last: a read-only dir would block its own children
        val dirModes = mutableListOf<Pair<File, Int>>()
        var count = 0
        TarArchiveInputStream(GZIPInputStream(BufferedInputStream(FileInputStream(tarball), BUFFER))).use { tar ->
            while (true) {
                val entry = tar.nextEntry ?: break
                if (isCancelled()) {
                    throw InterruptedIOException("cancelled")
                }
                val name = entry.name.removePrefix("./").trimEnd('/')
                if (name.isEmpty()) {
                    continue
                }
                val out = guestFile(dest, name)
                when {
                    entry.isDirectory -> {
                        out.mkdirs()
                        dirModes.add(out to ((entry.mode and MODE_DIR) or MODE_OWNER_RWX))
                    }
                    entry.isSymbolicLink -> {
                        out.parentFile?.mkdirs()
                        deleteTree(out)
                        Os.symlink(entry.linkName, out.path)
                    }
                    entry.isLink -> {
                        // hard links are not allowed in app storage: keep a copy
                        out.parentFile?.mkdirs()
                        deleteTree(out)
                        guestFile(dest, entry.linkName.removePrefix("./")).copyTo(out, overwrite = true)
                        Os.chmod(out.path, (entry.mode and MODE_FILE) or "600".toInt(8))
                    }
                    entry.isFile -> {
                        out.parentFile?.mkdirs()
                        deleteTree(out)
                        FileOutputStream(out).use { tar.copyTo(it, BUFFER) }
                        Os.chmod(out.path, (entry.mode and MODE_FILE) or "600".toInt(8))
                    }
                    // device nodes and fifos: proot binds the host /dev
                    else -> continue
                }
                count++
                if (count % 500 == 0) {
                    progress("Extracting Ubuntu base… $count files")
                }
            }
        }
        dirModes.asReversed().forEach { (dir, mode) -> Os.chmod(dir.path, mode) }
    }

    private fun guestFile(root:File, name:String):File {
        if (name.startsWith("/") || name.split('/').any { it == ".." }) {
            throw IOException("unsafe path in archive: $name")
        }
        return File(root, name)
    }

    private val SUDO_SHIM = """#!/bin/sh
# ebook2audiobook Android: single-user rootfs, everything already runs as root
while [ ${'$'}# -gt 0 ]; do
	case "${'$'}1" in
		-n|-E|-H|-S|-k) shift ;;
		-u|-g) shift 2 ;;
		--) shift; break ;;
		*) break ;;
	esac
done
[ ${'$'}# -eq 0 ] && exit 0
exec "${'$'}@"
"""

    private val FAKE_VMSTAT = """nr_free_pages 136576
nr_zone_inactive_anon 196744
nr_zone_active_anon 0
nr_zone_inactive_file 0
nr_zone_active_file 0
nr_zone_unevictable 0
nr_mlock 0
nr_bounce 0
nr_free_cma 0
pgpgin 890508
pgpgout 0
pswpin 0
pswpout 0
pgfault 176973
pgmajfault 488
"""
}
