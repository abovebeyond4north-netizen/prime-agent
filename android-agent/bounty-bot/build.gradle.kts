plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "net.abovebeyond.codieai.bounty"
    compileSdk = 36

    defaultConfig {
        applicationId = "net.abovebeyond.codieai.bountybot"
        minSdk = 30
        targetSdk = 36
        versionCode = 5
        versionName = "0.5.0"
    }

    sourceSets.getByName("main").java.srcDir(
        "../app/src/main/java/net/abovebeyond/codieai/bounty"
    )

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
}
