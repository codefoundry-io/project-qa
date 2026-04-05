# Risk Classification Guide

Classify every code change into one of four levels based on what the diff actually changes, not only the file name.

## `CRITICAL`

Changes that can cause data loss, app crashes, or security vulnerabilities.

- Data persistence schema changes such as Room entities, SQLite migrations, SharedPreferences keys, or DataStore
- Data deletion or purging logic
- Security, encryption, or authentication logic
- Permission request or enforcement changes
- Payment or billing logic
- Thread-safety changes such as `synchronized`, mutex, atomic, or coroutine-context changes
- Crash-path changes such as removed guards or forced non-null assertions
- Serialization or deserialization schema changes
- Cross-platform common logic changes such as KMP `commonMain`

Common signals:

- `@Entity`
- `ALTER TABLE`
- `MIGRATION`
- `Cipher`
- `encrypt`
- `decrypt`
- `BiometricPrompt`
- `!!`
- `synchronized`
- `Mutex`
- `BillingClient`
- removed null or error checks
- `[SCOPE: KMP_COMMON]`

## `HIGH`

Changes to core business logic, network communication, or background processing.

- Worker or service logic
- Network request or response handling
- Push-notification handling
- Deep link or intent routing
- ContentProvider or content-resolver behavior
- Core domain logic
- File I/O behavior

Common signals:

- classes ending in `Worker`, `Service`, `Repository`, `DataSource`, `Api`, or `Client`
- files under `data/`, `network/`, `domain/`, or `di/`

## `MEDIUM`

Changes to UI behavior, navigation, or presentation logic.

- Fragment or Activity logic beyond simple binding
- ViewModel or state-management changes
- Navigation graph or routing changes
- Dialog, BottomSheet, or Snackbar behavior
- RecyclerView adapter or ViewHolder logic
- Input validation or form logic
- Accessibility changes such as `contentDescription` or focus order

Common signals:

- classes ending in `Fragment`, `Activity`, `ViewModel`, `Adapter`, or `Screen`
- files under `ui/`, `presentation/`, or `feature/`

## `LOW`

Changes with minimal runtime impact.

- Layout XML changes such as dimensions, margins, padding, or constraints
- Drawable, vector, or animation resources
- Color, style, theme, or dimens resources
- String resources without logic changes
- Build configuration
- Dependency version bumps without API changes
- Formatting, import ordering, or comments
- Design-time preview attributes such as `tools:*`

Common signals:

- files under `res/drawable/`, `res/layout/`, `res/values/`, or `res/anim/`
- files matching `*.gradle*`, `*.toml`, or `*.pro`
