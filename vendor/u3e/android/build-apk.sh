#!/usr/bin/env bash
# build-apk.sh — build the U3E Android app.
#
# ⭐ IT REUSES A TOOLCHAIN RATHER THAN INSTALLING A SECOND ONE.
#   The sibling project already self-installs ~1.5GB of JDK + Android SDK +
#   Gradle into its own `android-toolchain/`. Downloading that again into this
#   project would cost the same 1.5GB and 20 minutes to end up with an identical
#   copy. So this script looks, in order, for:
#     1. ANDROID_HOME / ANDROID_SDK_ROOT already set
#     2. the sibling project's android-toolchain/
#     3. nothing — and it says exactly what to run, rather than guessing
#
#   ⚠ This is a BUILD-TIME tool dependency, not a runtime one. The no-cross-
#   project-imports law is about what the shipped code links against; borrowing
#   a compiler is not that. Nothing from the sibling ends up inside this APK.
#
# Usage:  bash android/build-apk.sh

set -u
cd "$(dirname "$0")"
HERE="$PWD"
SIBLING="$(cd .. && cd .. && pwd)/android-toolchain"

echo
echo "  U3E — BUILD THE ANDROID APP (.apk)"
echo "  =================================================="

# ── locate a toolchain ──────────────────────────────────────────────────────
JDK=""; SDK=""; GRADLE=""

if [ -n "${ANDROID_HOME:-}" ] && [ -d "${ANDROID_HOME}" ]; then
  SDK="$ANDROID_HOME"
elif [ -n "${ANDROID_SDK_ROOT:-}" ] && [ -d "${ANDROID_SDK_ROOT}" ]; then
  SDK="$ANDROID_SDK_ROOT"
fi

if [ -d "$SIBLING" ]; then
  [ -z "$SDK" ] && [ -d "$SIBLING/sdk" ] && SDK="$SIBLING/sdk"
  [ -d "$SIBLING/jdk" ] && JDK="$SIBLING/jdk"
  [ -d "$SIBLING/gradle" ] && GRADLE="$SIBLING/gradle"
  echo "  [ok] reusing the toolchain at $SIBLING"
fi

[ -z "$JDK" ] && [ -n "${JAVA_HOME:-}" ] && JDK="$JAVA_HOME"

if [ -z "$SDK" ] || [ ! -d "$SDK" ]; then
  cat <<'EOF'

  [!] No Android SDK found.

      This project deliberately does NOT install its own 1.5GB toolchain —
      the sibling project already has one. Either:

        1. Run the sibling's installer once:
             bash "../../linux/build_apk.sh"
           then re-run this script; or

        2. Point at your own SDK:
             export ANDROID_HOME=/path/to/android/sdk
             export JAVA_HOME=/path/to/jdk17

EOF
  exit 1
fi

[ -n "$JDK" ] && export JAVA_HOME="$JDK" && export PATH="$JDK/bin:$PATH"
export ANDROID_HOME="$SDK"; export ANDROID_SDK_ROOT="$SDK"

GRADLE_BIN="gradle"
if [ -n "$GRADLE" ] && [ -x "$GRADLE/bin/gradle" ]; then GRADLE_BIN="$GRADLE/bin/gradle"; fi
if ! command -v "$GRADLE_BIN" >/dev/null 2>&1 && [ ! -x "$GRADLE_BIN" ]; then
  echo "  [!] gradle not found. Run the sibling installer once (see above)."
  exit 1
fi

echo "  java   : ${JAVA_HOME:-<system>}"
echo "  sdk    : $ANDROID_HOME"
echo "  gradle : $GRADLE_BIN"
echo

# ── build ───────────────────────────────────────────────────────────────────
echo "  [*] building…"
"$GRADLE_BIN" --project-dir "$HERE" assembleRelease --no-daemon || {
  echo
  echo "  [!] build failed. The output above is the real error; do not guess."
  exit 1
}

APK="$HERE/app/build/outputs/apk/release/app-release.apk"
if [ ! -f "$APK" ]; then
  # ⛔ Gradle can exit 0 having produced nothing useful. Verify the ARTIFACT.
  echo "  [!] gradle succeeded but no APK is at $APK"
  exit 1
fi

OUT="$(cd .. && pwd)/Unity3D.apk"
cp "$APK" "$OUT"
SIZE=$(du -h "$OUT" | cut -f1)

cat <<EOF

  [ok] built: $OUT  ($SIZE)

  TO INSTALL
    1. Start the server with the phone able to reach it:
         node serve/server.mjs --host 0.0.0.0
       It prints the LAN address — you will need it.
    2. Copy Unity3D.apk to the phone and open it (allow install from this source).
    3. On first launch, paste the address the server printed.

  ⚠ Debug-signed on purpose: a private app for your own phone. Not for a store.
  ⚠ It asks for microphone and camera. Both are REFUSABLE — the orb still works
    typed and says what is unavailable.

EOF
