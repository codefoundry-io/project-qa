# Android Entry Point Patterns

Use these patterns when interpreting precomputed `[ENTRY: ...]` tags in `[References]`.

## UI Entry Points

### Activity

Declared in `AndroidManifest.xml` and acts as a top-level UI container.

```kotlin
class FooActivity : AppCompatActivity()
class FooActivity : ComponentActivity()
class FooActivity : FragmentActivity()
```

### Fragment

Hosted inside Activities and declared through navigation XML or added programmatically.

```kotlin
class FooFragment : Fragment()
class FooFragment : DialogFragment()
class FooFragment : BottomSheetDialogFragment()
```

### Compose Screen

Declared through a navigation destination such as `composable("route") { ... }`.

```kotlin
composable("home") { HomeScreen() }
```

## Background Entry Points

### Service

Long-running background behavior, usually declared in `AndroidManifest.xml`.

```kotlin
class FooService : Service()
class FooService : LifecycleService()
class FooService : IntentService("name")
```

### Worker

Scheduled background work through WorkManager.

```kotlin
class FooWorker : Worker(context, params)
class FooWorker : CoroutineWorker(context, params)
class FooWorker : ListenableWorker(context, params)
```

### BroadcastReceiver

System or app event handler declared in `AndroidManifest.xml` or registered dynamically.

```kotlin
class FooReceiver : BroadcastReceiver()
```

## How To Use `[ENTRY]` Tags

For a references block like this:

```text
MemberLabel:
  - app/.../MemberLabelFragment.kt [ENTRY: Fragment, VIEW_MODEL: MemberLabelViewModel]
  - app/.../MemberLabelViewModel.kt
```

- `MemberLabelFragment.kt` is the entry point.
- `entry_point_file` should be that Fragment path.
- `trigger_point` should be a UI trigger rooted in that screen.
- The `VIEW_MODEL` tag means the ViewModel changes directly affect that screen.

If no `[ENTRY: ...]` tag exists for the relevant caller chain, do not stop immediately. Follow `qa-tracer` Step 2 and attempt iterative caller tracing before returning `null`.
