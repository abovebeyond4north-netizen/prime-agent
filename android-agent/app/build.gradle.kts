plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "net.abovebeyond.codieai"
    compileSdk = 36

    defaultConfig {
        applicationId = "net.abovebeyond.codieai"
        minSdk = 30
        targetSdk = 36
        versionCode = 2
        versionName = "0.2.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += setOf("META-INF/AL2.0", "META-INF/LGPL2.1")
        }
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.17.1")
}
