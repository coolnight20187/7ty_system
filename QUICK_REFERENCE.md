# 24-Hour Session Persistence - Quick Reference Card

## At a Glance

| Feature | Details |
|---------|---------|
| **Session Duration** | 24 hours from login |
| **Auto-Extend** | Yes, on every API call |
| **Timeout Warning** | 5-minute periodic check |
| **Logout Warning** | SweetAlert2 popup |
| **Manual Logout** | Click "Đăng xuất" button |
| **Page Reload** | Session persists if valid |
| **localStorage Keys** | `token`, `tokenExpiresAt` |

---

## User Actions

### ✅ Login
```
1. Enter credentials
2. Click login
3. Token saved with 24h expiry
4. Redirected to dashboard
```
**Result**: User logged in for 24 hours

### ✅ Use Dashboard
```
1. Click on agents, bills, etc.
2. Make any API call
3. Token expiry auto-extends to now+24h
4. Continue working
```
**Result**: Can work indefinitely while active

### ✅ Manual Logout
```
1. Click profile menu (top right)
2. Click "Đăng xuất"
3. Confirm logout
4. Token cleared
5. Redirected to login
```
**Result**: Session ended cleanly

### ✅ Timeout Logout (After 24h Inactive)
```
1. Token expires
2. 5-min check detects expiry
3. SweetAlert warning appears
4. User clicks OK
5. Redirect to login
```
**Result**: Auto-logout with warning

### ✅ Page Reload
```
1. User refreshes page (F5)
2. Token validity checked
3. If valid: Dashboard loads
4. If expired: Redirect to login
```
**Result**: Session state preserved

---

## For Developers

### Check Token in Console
```javascript
// View token
localStorage.getItem('token')

// View expiration
localStorage.getItem('tokenExpiresAt')

// Calculate hours remaining
const exp = parseInt(localStorage.getItem('tokenExpiresAt'));
const hours = (exp - Date.now()) / (1000*60*60);
console.log(hours.toFixed(1) + ' hours remaining');
```

### Key Functions (app.html)

```javascript
// Check if token expired
isTokenExpired() {
    const expiresAt = localStorage.getItem('tokenExpiresAt');
    return expiresAt && Date.now() > parseInt(expiresAt);
}

// Get token from URL
getTokenFromUrl() {
    // Extracts from ?token=xxx
    // Saves with 24h expiry
}

// Logout completely
clearTokenAndLogout() {
    // Removes token + expiry
    // Redirects to /login.html
}
```

### Check Locations

| Check Type | Where | When |
|-----------|-------|------|
| **Page Load** | DOMContentLoaded | On refresh (F5) |
| **Periodic** | setInterval | Every 5 minutes |
| **API Call** | apiCall() | On every fetch |
| **Manual** | logout() | User clicks logout |

---

## Troubleshooting

### Issue: "Phiên đăng nhập hết hạn" Popup
**Cause**: Token expired after 24 hours  
**Solution**: Click OK, log back in  
**Note**: This is normal behavior

### Issue: Logged Out After Page Refresh
**Cause**: Token expired before refresh  
**Solution**: Log in again  
**Note**: Token only persists 24h from login

### Issue: Token Not in localStorage
**Cause**: Browser privacy mode or clearing data  
**Solution**: Normal behavior, user must re-login  
**Note**: Works fine in normal mode

### Issue: 5-Minute Check Not Firing
**Cause**: Console error or setInterval blocked  
**Solution**: Check F12 console for errors  
**Note**: Timeout still works on page load

---

## What Got Changed

### app.html (Admin Dashboard)
- ✅ Added `isTokenExpired()` function
- ✅ Added `clearTokenAndLogout()` function  
- ✅ Modified `getTokenFromUrl()` to save expiry
- ✅ Added DOMContentLoaded expiry check
- ✅ Added 5-minute periodic check
- ✅ Updated logout() to clear expiry

### login.html (Login Page)
- ✅ Save `tokenExpiresAt` = now + 24h
- ✅ Save on successful login
- ✅ Save in fallback try/catch too

### index.html (Mobile App)
- ✅ Save `agent_token_expires_at` on agent login
- ✅ Check expiry on DOMContentLoaded
- ✅ Check every 5 minutes in loadDashboard()

---

## Endpoints (No Changes)

All existing auth endpoints work as before:
- `POST /auth/login` - Still returns JWT token
- `POST /auth/agent-login` - Still returns JWT token
- All other APIs - Work with Bearer token
- WebSocket auth - Uses token from URL

No server-side changes needed!

---

## Files to Check

### To Verify Installation
```bash
# Check files exist
ls -la static/app.html static/login.html static/index.html

# Search for new functions
grep -n "isTokenExpired" static/app.html
grep -n "tokenExpiresAt" static/login.html
grep -n "agent_token_expires_at" static/index.html
```

### Container Status
```bash
docker ps --filter "name=7ty_app"
# Should show: Up X seconds (healthy)
```

---

## Test Cases (Quick)

### Test 1: Login Saves Expiry (30 seconds)
1. Login
2. Open Console (F12)
3. Run: `localStorage.getItem('tokenExpiresAt')`
4. Should show a 13-digit timestamp

### Test 2: Token Extends on Use (1 minute)
1. Login
2. Save initial expiry: `exp1 = localStorage.getItem('tokenExpiresAt')`
3. Click Agents (load data)
4. Check again: `exp2 = localStorage.getItem('tokenExpiresAt')`
5. Should be `exp2 > exp1`

### Test 3: Page Reload Keeps Session (30 seconds)
1. Login
2. Refresh page (F5)
3. Dashboard should load normally
4. Token should still exist

See `TESTING_SESSION_PERSISTENCE.md` for comprehensive tests!

---

## Important Notes

⚠️ **Token Doesn't Refresh on Server**
- No server-side session tracking
- Client-side timestamp only
- Works offline (no server contact needed)
- If clock is wrong, behavior affected

⚠️ **localStorage is Required**
- Session doesn't work without it
- Private/Incognito mode may not persist
- Browser clearing data removes session
- Each browser tab has independent session

⚠️ **Time Zone Doesn't Matter**
- Uses Date.now() (UTC milliseconds)
- No conversion needed
- Works globally

---

## One-Liner Explanations

| Term | Means |
|------|-------|
| **tokenExpiresAt** | Milliseconds when token becomes invalid |
| **isTokenExpired()** | Checks if current time > tokenExpiresAt |
| **Sliding Window** | Token extends every time user is active |
| **5-Min Check** | Periodic check finds expired tokens |
| **DOMContentLoaded** | Browser's "page fully loaded" event |
| **clearTokenAndLogout()** | Remove session and redirect to login |
| **SweetAlert** | Pretty warning popup before logout |

---

## Next Logical Steps

1. **Test** - Run all 8 tests from TESTING_SESSION_PERSISTENCE.md
2. **Deploy** - Files already in container, restart if needed
3. **Monitor** - Check logs for any token-related errors
4. **Document** - Update your user docs with new behavior
5. **Train** - Inform users they're logged out after 24h inactivity

---

## Still Have Questions?

📖 Full documentation in:
- `SESSION_PERSISTENCE.md` - Technical details
- `TESTING_SESSION_PERSISTENCE.md` - All test cases
- `IMPLEMENTATION_COMPLETE.md` - How it works
- `RELEASE_NOTES.md` - What changed

🐛 Found a bug?
- Check console (F12) for errors
- Verify container is healthy: `docker ps`
- Check logs: `docker logs 7ty_app`
- Clear localStorage and re-test

✅ Everything working?
- Congratulations! Session persistence is live
- Users can enjoy 24-hour uninterrupted sessions
- System automatically logs out stale sessions
- All data is secure and properly cleaned up
