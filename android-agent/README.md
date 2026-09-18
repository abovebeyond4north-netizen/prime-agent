# Codie AI Android Agent

## Bounty bot (0.5.0)

**For existing Codie AI users:** install the separate **Codie Bounty Bot**
companion APK (`net.abovebeyond.codieai.bountybot`). It opens directly to the
dashboard and shares the same discovery implementation without the model or
phone-control dependencies. It can coexist with Codie AI 0.4.0 and does not
access that app's private data. This build's signing certificate differs from
the supplied 0.4.0 APK, so the full Codie AI 0.5.0 build cannot update that APK
in place. Use the companion instead of uninstalling your current app.

Build the companion with `gradle -p android-agent :bounty-bot:assembleDebug`.
The output is `android-agent/bounty-bot/build/outputs/apk/debug/bounty-bot-debug.apk`.

Open **Bounty bot dashboard** from the home screen, then **Scan now** and
**Start background discovery**. No token, model download, subscription, or
accessibility permission is needed for discovery. Network/data charges may
still apply. Background scans require unmetered internet and a battery that
Android does not consider low.

The bot queries public GitHub issues using `is:issue is:open label:bounty
archived:false`, ranks the newest 100 results, deduplicates by validated issue
URL, caches the results privately, and prepares an issue-specific work brief.
This is a bounded discovery and preparation bot, not an autonomous coding,
submission, or payout agent. It does not claim bounties, send messages, execute
repository code, spend money, or claim that a listed reward has been earned.

Scheduled discovery runs approximately every six hours; Android may defer it
for battery, connectivity, idle state, or app restrictions. The job persists
across reboot, but Android force-stop suspends it until the app is reopened.
Manual scans have a 15-minute cooldown. GitHub rate-limit headers extend that
cooldown. Failed requests preserve the last successful snapshot and show the
failure, rather than presenting old data as newly fetched.

Priority is a transparent heuristic: unassigned +20, money mention +20,
reproduction details +15, tests/acceptance criteria +15, documentation/typo +10,
Python/Kotlin/TypeScript +10, deposit/upfront-fee wording -40, bounded to 0–100.
Amounts are literal text matches, not verified rewards or converted currencies.
Comments, competing claims, funding, eligibility, and platform terms require
review at the linked source. A bounty label alone does not establish payment.
The work brief includes these checks and reproducing/testing the eventual fix.

Parsing is linear in the bounded response size; ranking is O(n log n), with
n <= 100. The response is capped at 4 MiB; cached descriptions at 12,000
characters per candidate. No GitHub credentials are stored.

Policy verification (JDK 17):

    mkdir -p /tmp/bounty-tests
    javac -d /tmp/bounty-tests android-agent/app/src/main/java/net/abovebeyond/codieai/bounty/BountyPolicy.java android-agent/tests/BountyPolicyTest.java
    java -cp /tmp/bounty-tests BountyPolicyTest

The Android APK workflow builds the feature branch and runs these tests.
Installing an update requires the same signing key as the installed APK.
Do not uninstall your existing app merely to bypass a signing mismatch: that
would remove private app data. A device install and background-scheduling test
are still necessary before treating this as deployed on a particular phone.

References: [GitHub search API](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests)
and [Android JobScheduler](https://developer.android.com/reference/android/app/job/JobScheduler).

Codie AI is a local-first Android control client built for the Galaxy S25 FE / Android 16 class of devices.

It separates reasoning from execution:

1. The accessibility service observes the current Android UI.
2. A planner chooses exactly one next action.
3. The service executes that action.
4. The UI is observed again before the planner continues.
5. Completion must be verified from the current phone state.

This avoids long blind action scripts and makes recovery from changed screens possible.

## Capabilities

The current client can:

- inspect visible Android accessibility nodes, text, descriptions, resource ids, bounds, and state
- tap nodes, with coordinate-gesture fallback
- enter text into editable controls
- scroll forward and backward
- perform Back, Home, Recents, Notifications, and Quick Settings global actions
- launch installed apps by launcher label
- open Wi-Fi, Bluetooth, Accessibility, notification-access, app, and general settings
- expose recent notification summaries to the planner after the user enables notification access
- accept typed or voice-entered goals
- stop a running goal
- run a bounded 32-step observe/reason/act loop
- download and use a phone-resident LiteRT-LM model
- use GPT-OSS or another model through an OpenAI-compatible local/LAN/HTTPS endpoint
- fall back to deterministic one-step commands when no model is configured

## Model strategy

The Galaxy S25 FE variant targeted here has 8 GB RAM. GPT-OSS-20B is therefore treated as the high-capability external planner rather than the default phone-resident model.

For phone-only operation, the app can directly download Gemma 4 E2B for LiteRT-LM. This model is sized for 8 GB devices and gives the phone an offline reasoning path without API charges.

For maximum reasoning quality with zero recurring API cost, run GPT-OSS-20B on a computer on the same private network and enter its OpenAI-compatible chat-completions endpoint in the app. The Android client sends only the current accessibility text state, recent notification summaries, the user goal, and the previous action result.

If a GPT-OSS endpoint is configured, it takes priority. Otherwise the phone-local model is used. If neither is available, deterministic one-step controls remain available.

Cleartext HTTP endpoints are accepted only for localhost, .local hosts, and private RFC1918 LAN addresses. Remote planners must use HTTPS.

## Build

The repository contains a GitHub Actions workflow named Android Agent APK. Pushes to the feature branch build the APK automatically.

For a local build:

    gradle -p android-agent :app:assembleDebug

The APK is produced at:

    android-agent/app/build/outputs/apk/debug/app-debug.apk

## First-run setup

Android deliberately requires the phone owner to approve privileged control services.

After installing the APK:

1. Open Codie AI.
2. Tap Enable phone control and enable Codie AI phone control.
3. Optionally tap Enable notification context and approve Codie AI.
4. Tap Download recommended Gemma 4 E2B for phone-only AI, or enter an OpenAI-compatible GPT-OSS endpoint.
5. Enter a goal and tap Run.

No root access is required.

## Planner protocol

Every model response must contain exactly one action object. Example:

    {"action":"TAP_NODE","node":17,"reason":"Bluetooth is visible and currently off"}

The app re-observes the phone after the action and asks for the next action. The model cannot silently execute arbitrary native code; Android actions are limited to the explicit action vocabulary implemented by the accessibility service.

## Privacy

Phone-only LiteRT inference keeps model prompts on the device.

When a LAN or HTTPS planner is configured, the current accessibility snapshot and recent notification summaries are sent to that endpoint. Use an endpoint you control if the phone contains private information.
