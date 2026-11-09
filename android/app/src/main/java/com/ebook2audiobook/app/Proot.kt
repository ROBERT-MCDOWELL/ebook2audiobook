package com.ebook2audiobook.app

import android.content.Context
import android.system.ErrnoException
import android.system.Os
import java.io.File
import java.io.FileInputStream

/**
 * Command line and environment for Termux's proot (android/tools/fetch_proot.sh), packaged as lib*.so so Android
 * extracts it to nativeLibraryDir, the one app location it allows to execute from. Flags follow proot-distro.
 */
class Proot(context:Context, private val rootfs:File) {

    private val nativeDir = File(context.applicationInfo.nativeLibraryDir)
    private val libDir = File(context.filesDir, "lib")
    private val tmpDir = File(context.cacheDir, "proot")

    /** proot links libtalloc.so.2, a name jniLibs cannot hold: point it at the packaged libtalloc.so. */
    fun prepare() {
        libDir.mkdirs()
        tmpDir.mkdirs()
        val link = File(libDir, "libtalloc.so.2")
        val target = File(nativeDir, "libtalloc.so").path
        // nativeLibraryDir moves on every app update: refresh the link when it points elsewhere
        val current = try { Os.readlink(link.path) } catch (e:ErrnoException) { null }
        if (current != target) {
            link.delete()
            Os.symlink(target, link.path)
        }
    }

    fun hostEnv():Map<String, String> {
        val env = mutableMapOf(
            "PROOT_LOADER" to File(nativeDir, "libproot-loader.so").path,
            "PROOT_TMP_DIR" to tmpDir.path,
            "LD_LIBRARY_PATH" to "${libDir.path}:${nativeDir.path}",
        )
        val loader32 = File(nativeDir, "libproot-loader32.so")
        if (loader32.isFile) {
            env["PROOT_LOADER_32"] = loader32.path
        }
        return env
    }

    fun command(guest:List<String>, guestEnv:Map<String, String>):List<String> {
        val args = mutableListOf(
            File(nativeDir, "libproot.so").path,
            "--kill-on-exit",
            "--link2symlink",
            "--sysvipc",
            "-L",
            "-0",
            "-r", rootfs.path,
            "-w", "/root",
        )
        val binds = mutableListOf(
            "/dev",
            "/proc",
            "/sys",
            "/dev/urandom:/dev/random",
            "/proc/self/fd:/dev/fd",
            "/proc/self/fd/0:/dev/stdin",
            "/proc/self/fd/1:/dev/stdout",
            "/proc/self/fd/2:/dev/stderr",
            "${rootfs.path}/tmp:/dev/shm",
        )
        for (name in RootfsInstaller.FAKE_PROC_FILES) {
            if (!readable("/proc/$name")) {
                binds.add("${rootfs.path}/${RootfsInstaller.FAKE_PROC_DIR}/$name:/proc/$name")
            }
        }
        // shared storage, when the user granted it to the app (power users: ebooks in /sdcard for --headless)
        if (File("/storage/emulated/0").list() != null) {
            binds.add("/storage")
            binds.add("/storage/emulated/0:/sdcard")
        }
        for (bind in binds) {
            args.add("-b")
            args.add(bind)
        }
        args.add("/usr/bin/env")
        args.add("-i")
        for ((key, value) in guestEnv) {
            args.add("$key=$value")
        }
        args.addAll(guest)
        return args
    }

    private fun readable(path:String):Boolean = try {
        FileInputStream(path).use { it.read() }
        true
    } catch (e:Exception) {
        false
    }
}
