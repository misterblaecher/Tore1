# Remote Config Seed Payloads (Night-1)

Use these as baseline payloads for initial environment seeding and emergency toggles.

## DEV seed
```json
{
  "disable_writes_global": false,
  "disable_writes_message": "",
  "diagnostics_enabled": true,
  "min_supported_build": 1,
  "module_defaults": {
    "entry_enabled": true,
    "orders_enabled": true,
    "bar_enabled": true
  }
}
```

## STAGE seed
```json
{
  "disable_writes_global": false,
  "disable_writes_message": "",
  "diagnostics_enabled": true,
  "min_supported_version": "1.8.0",
  "module_defaults": {
    "entry_enabled": true,
    "orders_enabled": true,
    "bar_enabled": true
  }
}
```

## PROD seed
```json
{
  "disable_writes_global": false,
  "disable_writes_message": "Temporarily read-only while operations stabilize.",
  "diagnostics_enabled": false,
  "min_supported_version": "1.8.0",
  "module_defaults": {
    "entry_enabled": true,
    "orders_enabled": true,
    "bar_enabled": true
  }
}
```

### Emergency PROD toggle example
```json
{
  "disable_writes_global": true,
  "disable_writes_message": "Writes paused by operations. Please retry shortly."
}
```

## How to apply
Apply payloads through your remote config admin surface (for example backend `/admin` endpoint or the managed config system used by ops). After apply, validate on-device in diagnostics and run `./scripts/rc_verify_mobile.sh`.
