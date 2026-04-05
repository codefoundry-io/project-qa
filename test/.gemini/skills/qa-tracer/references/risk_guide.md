# Risk Classification Guide

Classify every code change into one of four levels based on the criteria below.
Judge by **what the diff actually changes**, not by file name alone.

## CRITICAL

Changes that can cause data loss, app crashes, or security vulnerabilities.

- Data persistence schema changes (Room @Entity, SQLite, SharedPreferences keys, DataStore)
- Data deletion or purging logic
- Security, encryption, or authentication logic
- Permission request or enforcement changes (runtime permissions, manifest permissions)
- Payment or billing logic (Google Play Billing, in-app purchase)
- Thread safety changes (synchronized, mutex, atomic, coroutine context switches)
- Crash-path changes (try/catch removal, forced non-null assertions `!!`)
- Serialization/deserialization schema changes (Proto, Parcelable, JSON model)
- Cross-platform common logic changes (KMP `commonMain`)

How to detect: diff touches `@Entity`, `ALTER TABLE`, `MIGRATION`, `Cipher`, `encrypt`, `decrypt`, `BiometricPrompt`, `!!`, `synchronized`, `Mutex`, `BillingClient`, removes null/error checks, or includes `[SCOPE: KMP_COMMON]`.

## HIGH

Changes to core business logic, network communication, or background processing.

- Background worker/service logic (WorkManager, Service, AlarmManager, JobScheduler)
- Network request/response handling (Retrofit, OkHttp, GraphQL, gRPC)
- Push notification handling (FCM, notification channels)
- Deep link or intent routing logic
- ContentProvider or content resolver changes
- Core domain logic (the app's primary business rules)
- File I/O operations (read/write to external storage, cache)

How to detect: diff touches classes ending with `Worker`, `Service`, `Repository`, `DataSource`, `Api`, `Client`, or files in `data/`, `network/`, `domain/`, `di/` directories.

## MEDIUM

Changes to UI behavior, navigation, or presentation logic.

- Fragment/Activity logic changes (not just layout binding)
- ViewModel or state management changes
- Navigation graph or routing changes
- Dialog/BottomSheet/Snackbar behavior
- RecyclerView adapter or ViewHolder logic
- User input validation or form logic
- Accessibility changes (contentDescription, focus order)

How to detect: diff touches classes ending with `Fragment`, `Activity`, `ViewModel`, `Adapter`, `Screen` (Compose), or files in `ui/`, `presentation/`, `feature/` directories.

## LOW

Changes with minimal runtime impact.

- Layout XML (dimensions, margins, padding, constraints)
- Drawable, vector, or animation resources
- Color, style, theme, or dimens resources
- String resources (without logic changes)
- Build configuration (Gradle scripts, version catalog, ProGuard rules)
- Dependency version bumps (without API changes)
- Code formatting, import ordering, or comment changes
- Design-time preview attributes (tools:*)

How to detect: files under `res/drawable/`, `res/layout/`, `res/values/`, `res/anim/`, or files matching `*.gradle*`, `*.toml`, `*.pro`.
