# 24-Hour Session Persistence Implementation

## Overview
Implemented comprehensive 24-hour session persistence for both admin dashboard and agent mobile app. Users now stay logged in for 24 hours after login, with automatic logout if token expires during active use.

## Features Implemented

### 1. Token Expiration Timestamp
- **Login.html**: Saves `tokenExpiresAt` when user logs in
  - Timestamp: `Date.now() + (24 * 60 * 60 * 1000)` (24 hours ahead)
  - Stored in localStorage alongside token

- **Agent_app.html**: Saves `agent_token_expires_at` for agent login
  - Same 24-hour expiration calculation
  - Stored in localStorage alongside agent_token

### 2. Token Expiry Checks

#### App.html (Admin Dashboard)
```javascript
isTokenExpired()
  - Checks if current time > tokenExpiresAt
  - Returns boolean
  
getTokenFromUrl()
  - Saves tokenExpiresAt when token found in URL
  
clearTokenAndLogout()
  - Removes token + tokenExpiresAt
  - Clears agentTableState (table preferences)
  - Redirects to /login.html
```

#### Agent_app.html (Mobile App)
```javascript
On DOMContentLoaded:
  - Check if agent_token_expires_at exists
  - If expired: clear tokens, show login page, alert message
  
On loadDashboard:
  - Setup 5-minute interval check
  - If token expired: logout and show alert
```

### 3. Token Refresh (Sliding Window)
- **apiCall() function**: Automatically extends token by 24h on each successful API call
- Prevents logout if user is actively using the system
- Implemented as "sliding window" - keeps refreshing while user is active

### 4. Page Load Checks
- **App.html**: Checks token expiry immediately after DOMContentLoaded
  - If expired: calls `clearTokenAndLogout()`
  - Prevents using app with stale token
  
- **Agent_app.html**: Same check on DOMContentLoaded
  - Shows user-friendly alert before redirect

### 5. Periodic Background Checks

#### Admin Dashboard (app.html)
```javascript
setInterval(() => {
    if (isTokenExpired()) {
        // Show SweetAlert2 warning
        // Then call clearTokenAndLogout()
    }
}, 5 * 60 * 1000); // Every 5 minutes
```

#### Agent Mobile App (index.html)
```javascript
setInterval(() => {
    if (agent_token_expires_at > now) {
        // Show alert
        // Logout
    }
}, 5 * 60 * 1000); // Every 5 minutes
```

### 6. Logout Function Updates
- **app.html logout()**: Now removes both token AND tokenExpiresAt
- **Manual logout**: Cleans up all session data before redirect

## Files Modified

### 1. static/app.html (Admin Dashboard)
- Lines ~3338-3390: Added `getTokenFromUrl()`, `isTokenExpired()`, `clearTokenAndLogout()`
- Lines ~3408-3412: Token expiry check on DOMContentLoaded
- Lines ~3540-3554: 5-minute periodic token check with SweetAlert2 warning
- Lines ~5883-5898: Updated logout() to remove tokenExpiresAt
- Updated apiCall() to refresh token expiry on successful API calls

### 2. static/login.html
- Lines ~495-528: 
  - Calculate `expiresAt = Date.now() + (24h)`
  - Save tokenExpiresAt to localStorage
  - Save again in fallback try/catch block
  - Added console log for 24h expiration confirmation

### 3. static/index.html
- Lines ~960-976: Save `agent_token_expires_at` on successful agent login
- Lines ~926-944: Added DOMContentLoaded token expiry check
- Lines ~1230-1248: Added 5-minute periodic check in loadDashboard()
- Alert messages inform agent when session expires

## Session Flow

### Login Flow (24h Start)
```
User logs in → Token generated → tokenExpiresAt = now + 24h
→ Saved to localStorage → User redirected to dashboard
```

### Active Use (Sliding Window)
```
User makes API call → Token valid → Auto-refresh expiry to now + 24h
→ Continue using system without re-login for 24h of continuous use
```

### Logout Scenarios

#### 1. Immediate Logout (User Clicked Logout)
```
User clicks logout → Show confirmation → Clear token + tokenExpiresAt
→ Clear table preferences → Redirect to /login.html
```

#### 2. Expiration After Inactivity
```
Token expires → 5-min check detects expiry → Show warning popup
→ User clicks OK → clearTokenAndLogout() → Redirect to /login.html
```

#### 3. Page Reload After Expiry
```
User refreshes page → DOMContentLoaded fires → isTokenExpired() returns true
→ clearTokenAndLogout() → Redirected to /login.html
```

## localStorage Keys

### Admin Dashboard
- `token`: JWT access token
- `tokenExpiresAt`: Timestamp when token expires (milliseconds)
- `agentTableState`: Table preferences (sort, filter, columns)

### Agent Mobile App
- `agent_token`: JWT access token for agent
- `agent_token_expires_at`: Agent token expiration timestamp
- `agent_id`, `agent_name`, `agent_code`: Agent details

## Security Benefits

1. **Automatic Session Cleanup**: Token removed from localStorage after 24h
2. **Sliding Window**: User stays logged in while actively using system
3. **Background Check**: 5-minute interval catches token expiry even during inactivity
4. **Page Load Validation**: Prevents stale token access on refresh
5. **API Protection**: apiCall() blocks requests with expired tokens
6. **User Notification**: Clear alerts when session expires

## Testing

### Test Case 1: Normal Login (24h Retention)
1. Login at time T
2. Check localStorage → token + tokenExpiresAt both present
3. Wait 5 minutes → should still have access
4. Calculate: expiresAt should be T + 24 hours
5. ✅ User stays logged in until 24h window closes

### Test Case 2: Page Reload Before 24h
1. Login at time T
2. Reload page (F5)
3. Token still valid → check passes
4. Dashboard loads normally
5. ✅ No unexpected logout

### Test Case 3: Timeout Logout
1. Login at time T
2. Wait for token to expire (simulate by setting tokenExpiresAt to past time)
3. Make API call or check 5-min interval
4. SweetAlert warning shows
5. User clicks OK
6. Redirected to /login.html
7. ✅ Automatic logout works

### Test Case 4: Active Use (Sliding Window)
1. Login at time T
2. Make API calls every 2 minutes for 30 minutes
3. Each call should extend expiry to now + 24h
4. After 30 min, should still be logged in
5. ✅ Sliding window extends session

### Test Case 5: Manual Logout
1. Login
2. Click logout button
3. Confirm logout
4. Both token AND tokenExpiresAt removed
5. Redirected to /login.html
6. ✅ Manual logout cleans all data

## Edge Cases Handled

1. **Missing tokenExpiresAt**: Treated as valid token
2. **Clock Skew**: Uses client-side Date.now() (no server time issues)
3. **Browser Close**: localStorage persists across sessions
4. **Multiple Tabs**: Each tab has independent session check
5. **API Errors**: Token refresh only happens on successful requests

## Configuration

All time values are hardcoded:
- **Session Duration**: 24 hours (86,400,000 ms)
- **Check Interval**: 5 minutes (300,000 ms)
- **Page Load Check**: Immediate (DOMContentLoaded)

To adjust session duration, modify:
- `24 * 60 * 60 * 1000` in login.html and getTokenFromUrl()
- `5 * 60 * 1000` in setInterval() calls

## Deployment Notes

- All files deployed to Docker container: 7ty_app
- Changes effective immediately after container restart
- No database schema changes required
- Backward compatible with existing tokens (new field is optional)
- Works with existing auth endpoints

## Future Enhancements

1. **Token Refresh Endpoint**: Replace sliding window with explicit refresh token
2. **Server-Side Session**: Store session in Redis/database for multi-device logout
3. **Remember Me**: Option to extend session beyond 24h
4. **Session History**: Track login/logout events
5. **Device Management**: Allow user to logout other devices
