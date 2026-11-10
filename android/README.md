# ebook2audiobook for Android

A small Kotlin app that installs and runs the regular e2a on the phone. Users install the apk and open it,
nothing else.

## How it works

1. **Linux userland.** Android's libc (bionic) cannot run uv's Python nor the manylinux wheels e2a installs
   (torch, onnxruntime, …). On first start the app downloads the official Ubuntu 24.04 base rootfs
   (`cdimage.ubuntu.com/ubuntu-base`, latest point release, SHA-256 checked) and unpacks it in its private
   storage (`RootfsInstaller.kt`).
2. **proot.** Termux's proot (bundled, see below) runs that rootfs as a fake root with the same flags as
   proot-distro (`Proot.kt`). Missing `/proc` entries Android hides from apps are replaced by static ones.
3. **Bootstrap.** `assets/e2a-android.sh` runs inside the rootfs: it installs the base packages a minimal Ubuntu
   lacks (the Dockerfile list), clones e2a (`e2aRepo`/`e2aBranch` in `gradle.properties`), then runs
   `./ebook2audiobook.sh` unchanged. The launcher provisions uv, Python, the system programs and the engines like
   on any Linux arm64 / x86_64 host. `E2A_INTERFACE_HOST=127.0.0.1` keeps gradio off the local network.
4. **App.** `E2aService` is a foreground service (wake lock + Wi-Fi lock) owning the process and the full log
   (`files/logs/e2a.log`). `MainActivity` shows the progress/log until `http://127.0.0.1:7860` answers, then the
   interface in a WebView (Android file picker for uploads, save-as for downloads).

`targetSdk` stays at 28, as Termux, because newer target levels restrict what a Linux userland needs (exec of
app files, netlink, …). That rules out the Play Store, so the apk ships with the GitHub releases.

## Tested

The **Android app end-to-end** workflow installs the debug apk on an Android 14 x86_64 emulator and waits for the
e2a UI: fresh install to gradio answering on the device in 55 minutes, 13 GB of app storage. Same code paths as an
arm64 phone except the ABI; not yet run on a physical device.

## Build

```bash
bash android/tools/fetch_proot.sh
```
```bash
cd android && ./gradlew assembleRelease
```

`fetch_proot.sh` downloads `proot`, `libtalloc` and `libandroid-shmem` for aarch64 and x86_64 from the Termux
package repository and puts them in `app/src/main/jniLibs/<abi>/` as `lib*.so`: an app may only execute files from
its native library directory, which Android fills from jniLibs at install time. They are not committed.

CI: the **Build Android app** workflow builds on every push touching `android/`, attaches the apk to published
releases, and can publish a prerelease (`workflow_dispatch`, `publish`). **Android app end-to-end** is run by hand.
For stable signing (updates in place) add the repository secrets `ANDROID_KEYSTORE_BASE64`,
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`; without them the apk is signed with a
throwaway debug key.

## Licenses

The bundled proot (GPL-2.0, https://github.com/termux/proot), talloc (LGPL-3.0) and libandroid-shmem (BSD-3-Clause,
https://github.com/termux/libandroid-shmem) are unmodified Termux builds, executed as separate programs.
Ubuntu and e2a are downloaded on the device.
