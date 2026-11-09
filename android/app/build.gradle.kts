plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// app version follows e2a: 26.11.1 -> versionName 26.11.1, versionCode 261101
val e2aVersion:String = rootProject.file("../VERSION.txt").readText().trim()
val e2aVersionCode:Int = e2aVersion.split('.').map { it.toIntOrNull() ?: 0 }.plus(listOf(0, 0, 0)).let { it[0] * 10000 + it[1] * 100 + it[2] }
val e2aRepo:String = providers.gradleProperty("e2aRepo").get()
val e2aBranch:String = providers.gradleProperty("e2aBranch").get()
// release signing comes from the environment (CI secrets); without it the release apk is signed with the debug key
val keystorePath:String? = System.getenv("E2A_KEYSTORE")?.takeIf { it.isNotBlank() && file(it).isFile }

android {
    namespace = "com.ebook2audiobook.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.ebook2audiobook.app"
        minSdk = 26
        // 28 on purpose, as Termux: the app runs a full Linux userland (proot) which newer target levels restrict
        // (W^X exec of app files, netlink, ...). It is distributed outside the Play Store
        targetSdk = 28
        versionCode = e2aVersionCode
        versionName = e2aVersion
        buildConfigField("String", "E2A_REPO", "\"$e2aRepo\"")
        buildConfigField("String", "E2A_BRANCH", "\"$e2aBranch\"")
        ndk {
            // torch and every other wheel e2a installs exist for 64-bit only
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        if (keystorePath != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("E2A_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("E2A_KEY_ALIAS")
                keyPassword = System.getenv("E2A_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    packaging {
        jniLibs {
            // proot, its loader and libs are executables/libs run from nativeLibraryDir: they must be extracted
            // on install (not mmapped from the apk) and left untouched (the loader is a hand-linked static binary)
            useLegacyPackaging = true
            keepDebugSymbols += "**/*.so"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    lint {
        disable += listOf("ExpiredTargetSdkVersion", "OldTargetApi")
        abortOnError = false
        checkReleaseBuilds = false
    }
}

dependencies {
    implementation("org.apache.commons:commons-compress:1.27.1")
}

// the proot runtime is not in git: android/tools/fetch_proot.sh puts it in src/main/jniLibs
tasks.register("checkProotRuntime") {
    val jniDir = file("src/main/jniLibs")
    doLast {
        for (abi in listOf("arm64-v8a", "x86_64")) {
            for (lib in listOf("libproot.so", "libproot-loader.so", "libtalloc.so", "libandroid-shmem.so")) {
                if (!File(jniDir, "$abi/$lib").isFile) {
                    throw GradleException("missing $abi/$lib: run android/tools/fetch_proot.sh first")
                }
            }
        }
    }
}
tasks.named("preBuild") {
    dependsOn("checkProotRuntime")
}
