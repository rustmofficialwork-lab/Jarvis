#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   DRY_RUN=1 ./refactor-subpackages.sh   # print actions without changing files
#   ./refactor-subpackages.sh             # perform changes (creates commit on branch)
#
# Runs from repo root.
# Creates a branch: refactor/subpackages
# Review the git diff and run tests before pushing.

DRY_RUN="${DRY_RUN:-0}"
BRANCH="refactor/subpackages"
ROOT="."
MAIN_SRC="app/src/main/java/com/jarvisassistant/app"
TEST_SRC="app/src/test/java/com/jarvisassistant/app"
MANIFEST="app/src/main/AndroidManifest.xml"

# Map file -> subpackage (relative to com.jarvisassistant.app)
declare -A MAP=(
  ["MainActivity.kt"]="ui"
  ["AssistantServices.kt"]="services"
  ["JarvisNotificationListenerService.kt"]="services"
  ["JarvisAccessibilityService.kt"]="services"
  ["JarvisDeviceAdminReceiver.kt"]="receiver"
  ["JarvisVoiceEngine.kt"]="engine"
  ["JarvisContextEngine.kt"]="engine"
  ["JarvisPriorityEngine.kt"]="engine"
  ["JarvisProactiveEngine.kt"]="engine"
  ["JarvisVisionEngine.kt"]="engine"
  ["CommandNormalizer.kt"]="engine"
  ["CybersecurityAudit.kt"]="security"
  ["SecureVault.kt"]="security"
  ["HistoryStore.kt"]="data"
  ["JarvisTaskStore.kt"]="data"
  ["JarvisRecoveryStore.kt"]="data"
  ["JarvisAgent.kt"]="core"
  ["JarvisAgentRuntime.kt"]="core"
  ["JarvisCapabilities.kt"]="core"
  ["JarvisDiagnostics.kt"]="core"
  ["JarvisIntegrationHub.kt"]="core"
  ["JarvisMemoryManager.kt"]="core"
  ["JarvisNetworkResilience.kt"]="core"
  ["JarvisPhoneControl.kt"]="core"
  ["JarvisProactivePlanner.kt"]="core"
  ["JarvisResourceManager.kt"]="core"
  ["JarvisToolSystem.kt"]="core"
  ["JarvisVision.kt"]="core"
  ["JarvisWakeService.kt"]="core"
  # Add additional files here if needed
)

# Helper: run or echo
run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY RUN: $*"
  else
    echo "+ $*"
    eval "$@"
  fi
}

# 1) Create branch
if [ "$DRY_RUN" = "0" ]; then
  git fetch origin
fi
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "Branch $BRANCH already exists locally; switching to it."
  run git checkout "$BRANCH"
else
  echo "Creating branch $BRANCH from current HEAD."
  run git checkout -b "$BRANCH"
fi

# 2) Ensure test src dir exists
run mkdir -p "$TEST_SRC"

# 3) Create directories and move source files
for file in "${!MAP[@]}"; do
  sub="${MAP[$file]}"
  src="$MAIN_SRC/$file"
  dest_dir="$MAIN_SRC/$sub"
  dest="$dest_dir/$file"
  test_dest_dir="$TEST_SRC/$sub"

  # create dest dirs
  run mkdir -p "$dest_dir"
  run mkdir -p "$test_dest_dir"

  if [ -f "$src" ]; then
    # git mv will stage rename
    run git mv -f "$src" "$dest"
  else
    echo "NOTE: source file not found (skipping): $src"
  fi

  # Move matching tests from main java to test tree if present
  test_file="${file%.kt}Test.kt"
  test_src="$MAIN_SRC/$test_file"
  if [ -f "$test_src" ]; then
    run git mv -f "$test_src" "$test_dest_dir/$test_file"
  else
    # Some tests are named differently; attempt pattern match
    if compgen -G "$MAIN_SRC/*${file%.kt}*Test*.kt" > /dev/null; then
      for tf in $MAIN_SRC/*${file%.kt}*Test*.kt; do
        run git mv -f "$tf" "$test_dest_dir/$(basename "$tf")"
      done
    fi
  fi
done

# 4) Update package lines in moved source files and tests
# For each moved file, change "package com.jarvisassistant.app" to "package com.jarvisassistant.app.<sub>"
for file in "${!MAP[@]}"; do
  sub="${MAP[$file]}"
  dest="$MAIN_SRC/$sub/$file"
  test_dest="$TEST_SRC/$sub/${file%.kt}Test.kt"

  if [ -f "$dest" ]; then
    # Replace initial package line
    run sed -i.bak -E "0,/^package com\\.jarvisassistant\\.app(\\b|\\.)/s//package com.jarvisassistant.app.${sub}/" "$dest"
    run rm -f "$dest.bak" || true
  fi

  if [ -f "$test_dest" ]; then
    run sed -i.bak -E "0,/^package com\\.jarvisassistant\\.app(\\b|\\.)/s//package com.jarvisassistant.app.${sub}/" "$test_dest"
    run rm -f "$test_dest.bak" || true
  fi
done

# 5) Update imports/usages across the repo for moved classes
# For each class, replace "com.jarvisassistant.app.ClassName" with "com.jarvisassistant.app.<sub>.ClassName"
# And replace import lines "import com.jarvisassistant.app.ClassName" accordingly.
for file in "${!MAP[@]}"; do
  sub="${MAP[$file]}"
  class="${file%.kt}"
  from="com.jarvisassistant.app.${class}"
  to="com.jarvisassistant.app.${sub}.${class}"

  # Replace fully-qualified uses:
  # Use perl -0777 -pe to operate on entire file content to avoid missing multi-line imports
  run git grep -l --line-number --full-name --extended-regexp "com\\.jarvisassistant\\.app\\.${class}" || true
  if [ "$DRY_RUN" = "0" ]; then
    # Update tracked files: find all .kt/.java files (main and test) and replace strings
    files_to_update=$(git ls-files | grep -E '\.(kt|java)$' || true)
    if [ -n "$files_to_update" ]; then
      for f in $files_to_update; do
        # skip moving target files themselves (already patched)
        if [ -f "$f" ]; then
          # Replace occurrences
          perl -0777 -pe "s/\\bcom\\.jarvisassistant\\.app\\.${class}\\b/${to}/g" -i "$f"
        fi
      done
    fi
  else
    echo "DRY RUN: would replace occurrences of '${from}' with '${to}' in .kt/.java files tracked by git"
  fi
done

# 6) Update AndroidManifest.xml android:name attributes for moved classes
# Replace occurrences like android:name=".ClassName" with android:name=".sub.ClassName"
if [ -f "$MANIFEST" ]; then
  for file in "${!MAP[@]}"; do
    sub="${MAP[$file]}"
    class="${file%.kt}"
    # Update xml entries like android:name=".ClassName" -> android:name=".sub.ClassName"
    # Also handle android:name="com.jarvisassistant.app.ClassName" -> full replacement
    run sed -i.bak -E "s/android:name=\"\\.(${class})\"/android:name=\".${sub}.\\1\"/g" "$MANIFEST"
    run sed -i.bak -E "s/android:name=\"com\\.jarvisassistant\\.app\\.(${class})\"/android:name=\"com.jarvisassistant.app.${sub}.\\1\"/g" "$MANIFEST"
    run rm -f "$MANIFEST.bak" || true
  done
else
  echo "Warning: AndroidManifest not found at $MANIFEST; skipping manifest updates."
fi

# 7) Run a git add for any files changed (in DRY_RUN we only printed)
if [ "$DRY_RUN" = "0" ]; then
  git add -A
  git commit -m "Refactor: place sources into subpackages (engine/services/receiver/security/data/core/ui) and move tests; update package and manifest"
  echo "Committed changes on branch $BRANCH."
  echo "Please run your build locally: ./gradlew assembleDebug (or your usual build command)."
else
  echo "DRY RUN complete. Inspect changes with 'git status' and the moved files above."
fi

echo "Done."
