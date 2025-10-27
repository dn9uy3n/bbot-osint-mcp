# Changelog

## v2.0.0 - Continuous Monitoring Mode (2025-10-27)

### 🎯 Major Changes

#### Architecture Shift: Manual → Continuous Monitoring
- **Before**: Scan on-demand via API/MCP triggers
- **After**: Automatic continuous scanning in cycles with configured targets

### ✅ Added

1. **Continuous Scanner (`scheduler.py`)**
   - Auto-starts on service startup
   - Loops through all targets from `init_config.json`
   - Runs indefinitely with configurable sleep times
   - Telegram notifications after each cycle

2. **2 Types of Sleep Time**
   - `target_sleep_seconds`: Rest between targets in same cycle (default 300s)
   - `cycle_sleep_seconds`: Rest between complete cycles (default 3600s)
   - Detailed documentation in `SLEEP_PARAMETERS.md`

3. **Incremental Data Updates**
   - Scans only add/update data, never delete existing data
   - Cleanup only removes old/offline data per retention policy
   - Full BBOT event history preserved

4. **Enhanced Neo4j Schema**
   - `DNS_NAME` nodes with timestamps
   - `OPEN_TCP_PORT` nodes with port info
   - `TECHNOLOGY` nodes for detected tech stack
   - Full relationships between all node types

5. **Status Monitoring**
   - `GET /status` endpoint for scanner state
   - `osint.status()` MCP tool
   - Real-time logs for cycle progress

### ❌ Removed

1. **Manual Scan Triggers**
   - Removed `POST /scan` API endpoint
   - Removed `osint.scan()` MCP tool
   - Scans now automatic based on `init_config.json`

2. **Upsert Endpoint**
   - Removed `POST /upsert` (not needed for monitoring mode)

### 🔄 Changed

1. **init_config.json Structure**
   ```json
   {
     "targets": ["target1.com", "target2.com"],
     "scan_defaults": {
       "presets": ["subdomain-enum"],
       "max_workers": 2,
       "target_sleep_seconds": 300,
       "cycle_sleep_seconds": 3600
     }
   }
   ```

2. **MCP Server (Query-Only)**
   - `osint.query()` - Still available
   - `osint.events.query()` - Still available
   - `osint.status()` - New
   - `osint.scan()` - Removed

3. **API Endpoints**
   - `GET /healthz` - Enhanced with scanner status
   - `GET /status` - New endpoint
   - `POST /query` - Unchanged
   - `POST /events/query` - Unchanged

4. **Documentation**
   - Complete rewrite of README.md (Vietnamese)
   - Complete rewrite of README_EN.md (English)
   - New SLEEP_PARAMETERS.md for detailed sleep time explanation
   - Updated architecture diagrams (Mermaid)

### 📚 Documentation Updates

1. **New Files**
   - `SLEEP_PARAMETERS.md`: Comprehensive guide on sleep parameters
   - `CHANGELOG.md`: This file

2. **Updated Files**
   - `README.md`: Continuous monitoring focus, detailed sleep params
   - `README_EN.md`: English version with same updates
   - Architecture diagrams: Added continuous monitoring flow

### 🔧 Configuration

#### Old Way (v1.x)
```bash
# Manual trigger
curl -X POST /scan -d '{"targets":["example.com"]}'
```

#### New Way (v2.0)
```json
// init_config.json
{
  "targets": ["example.com"],
  "scan_defaults": {
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  }
}
```
Service automatically scans in background.

### 📊 Monitoring

**Watch scanner logs:**
```bash
docker logs -f bbot_osint | grep -E "Scanning|Sleep|Cycle"
```

**Check status:**
```bash
curl -H "X-API-Token: $TOKEN" https://osint.example.com/status
```

### 🎓 Use Cases

| Scenario | cycle_sleep_seconds | Reasoning |
|----------|---------------------|-----------|
| Dev/Test | 600 (10 min) | Quick iterations |
| Frequent Monitoring | 3600-7200 (1-2 hours) | Balance freshness & safety |
| Daily Audit | 86400 (24 hours) | Once per day scan |
| Weekly Check | 604800 (7 days) | Periodic review |

### 🚀 Migration Guide (v1.x → v2.0)

1. **Update init_config.json**
   - Add `target_sleep_seconds` and `cycle_sleep_seconds` to `scan_defaults`
   - Ensure all targets are listed in `targets` array

2. **Remove manual scan scripts/crons**
   - Scanner now runs automatically
   - No need for external schedulers

3. **Update MCP configuration in Cursor**
   - Remove any references to `osint.scan` tool
   - Use only `osint.query`, `osint.events.query`, `osint.status`

4. **Monitor first cycle**
   ```bash
   docker logs -f bbot_osint
   ```
   Verify target_sleep and cycle_sleep are working as expected

5. **Adjust sleep times based on results**
   - If rate limited: increase both sleep times
   - If too slow: decrease cycle_sleep_seconds carefully

### ⚠️ Breaking Changes

1. **No more `/scan` endpoint** - All code calling this endpoint will fail
2. **No more `osint.scan()` MCP tool** - Cursor integrations using this will break
3. **Targets must be pre-configured** - Cannot scan arbitrary targets on-demand

### 🐛 Known Issues

None currently identified.

### 📝 Notes

- Database from v1.x is fully compatible
- All existing Neo4j data preserved
- Continuous scanner starts automatically on first deployment

