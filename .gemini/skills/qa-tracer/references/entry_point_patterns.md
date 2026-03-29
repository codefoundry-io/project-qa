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
    - app/.../MemberLabelFragment.kt [ENTRY: Fragment]
    - app/.../MemberLabelViewModel.kt
```

- `MemberLabelFragment.kt` is the entry point (tagged as Fragment = UI)
- Set `entry_point_file` to `MemberLabelFragment.kt`
- Set `trigger_point` to `UI(MemberLabel > ...)`

When no [ENTRY] tag exists, set `entry_point_file` to null.
