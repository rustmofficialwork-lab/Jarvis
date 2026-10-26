# JARVIS release hardening.
# Keep ML Kit text recognition model metadata and Android components discoverable.
-keep class com.google.mlkit.** { *; }
-keep class androidx.startup.** { *; }

# Preserve Kotlin metadata used by reflection-based libraries.
-keep class kotlin.Metadata { *; }

# Do not log sensitive application state in release builds.
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
}
