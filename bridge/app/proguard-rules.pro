# ProGuard rules for the JARVIS Bridge APK.
#
# minifyEnabled is false in build.gradle, so these rules only matter if
# minification is ever enabled. The bridge talks to the Python brain over
# localhost JSON-RPC with plain hand-written JSON, and it uses no reflection
# on class or method names, so nothing needs to be kept by name. The rules
# below are the standard safe keeps for AndroidX and the accessibility
# service declaration.

# Keep the accessibility service entry points; Android instantiates them
# by the names declared in AndroidManifest.xml.
-keep public class com.assistant.bridge.** {
    public *;
}

# Standard AndroidX rules (applied automatically by the library AARs);
# kept explicit here for safety.
-dontwarn androidx.**
-keep class androidx.core.view.accessibility.** { *; }
