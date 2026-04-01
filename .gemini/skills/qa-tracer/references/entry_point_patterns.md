# Android Entry Point Patterns

This document describes how entry points are identified in the pre-computed index.
Use `[ENTRY: xxx]` tags in [References] to determine `entry_point_file`.

## UI Entry Points

### Activity
Declared in AndroidManifest.xml. The top-level UI container.
```
class FooActivity : AppCompatActivity()
class FooActivity : ComponentActivity()
class FooActivity : FragmentActivity()
```

### Fragment
Hosted inside Activities. Declared in navigation XML or added programmatically.
```
class FooFragment : Fragment()
class FooFragment : DialogFragment()
class FooFragment : BottomSheetDialogFragment()
```

### ComposeScreen
Declared via `composable("route") { ... }` in Navigation Graph.
```
composable("home") { HomeScreen() }
```

## Background Entry Points

### Service
Long-running background operations. Declared in AndroidManifest.xml.
```
class FooService : Service()
class FooService : LifecycleService()
class FooService : IntentService("name")
```

### Worker
Scheduled background tasks via WorkManager.
```
class FooWorker : Worker(context, params)
class FooWorker : CoroutineWorker(context, params)
class FooWorker : ListenableWorker(context, params)
```

### BroadcastReceiver
System event handlers. Declared in AndroidManifest.xml.
```
class FooReceiver : BroadcastReceiver()
```

## How to use [ENTRY] tags

When [References] contains tagged entries like:
```
  MemberLabel:
    - app/.../MemberLabelFragment.kt [ENTRY: Fragment, VIEW_MODEL: MemberLabelViewModel]
    - app/.../MemberLabelViewModel.kt
```

- `MemberLabelFragment.kt` is the entry point (tagged as Fragment = UI)
- Set `entry_point_file` to `MemberLabelFragment.kt`
- Set `trigger_point` to `UI(MemberLabel > ...)`
- **Crucial Context:** The `VIEW_MODEL` tag indicates that changes to `MemberLabelViewModel` directly impact this UI entry point.

When no `[ENTRY: …]` tag appears for the relevant caller chain in `[References]`, do **not** stop at null immediately. Follow the main **qa-tracer** skill **Step 2** (iterative `rg` caller trace up to 10 levels). Set `entry_point_file` to null only after Step 2 fails or trace rules require abort (e.g. 10+ references utility path).
