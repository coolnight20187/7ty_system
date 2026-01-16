# 24-Hour Session Persistence - Testing Guide

## Quick Start Testing

### Prerequisites
- Container running: `docker ps` should show 7ty_app healthy
- Browser DevTools console open (F12)
- Access system at `http://localhost:8000`

---

## Test 1: Check Token Storage on Login ✅

**Steps:**
1. Open login.html
2. Enter credentials and login
3. Open DevTools Console (F12)
4. Run these commands:

```javascript
// Check tokens are saved
console.log('Token:', localStorage.getItem('token') ? 'EXISTS' : 'MISSING');
console.log('Expires At:', localStorage.getItem('tokenExpiresAt'));

// Calculate hours until expiry
const expiresAt = parseInt(localStorage.getItem('tokenExpiresAt'));
const now = new Date().getTime();
const hoursLeft = (expiresAt - now) / (1000 * 60 * 60);
console.log('Hours until expiry:', hoursLeft.toFixed(2));
```

**Expected Result:**
```
Token: EXISTS
Expires At: 1704067200000 (example timestamp)
Hours until expiry: 23.98
```

---

## Test 2: Token Expiry Check on Page Load ✅

**Steps:**
1. Login successfully
2. Open Console, look for this message:
   ```
   ✓ Token found in URL parameter
   ✓ Token saved to localStorage with 24h expiration
   ```
3. Refresh page (F5)
4. Check Console for:
   ```
   DOMContentLoaded fired
   [Message: Token still valid, app loads normally]
   ```

**Expected Behavior:**
- Dashboard loads normally
- No unexpected redirects
- Console shows token is valid

---

## Test 3: Simulate Token Expiry (Debug Test) ⚠️

**Steps:**
1. Login successfully
2. Open Console and set token to expired:

```javascript
// Set expiry to 1 second ago (immediately expired)
localStorage.setItem('tokenExpiresAt', (Date.now() - 1000).toString());
```

3. Refresh page (F5)
4. Observe behavior

**Expected Result:**
- Redirect to `/login.html`
- Console message: `✗ Token expired on page load, logging out`

---

## Test 4: Sliding Window (Active Use) ✅

**Steps:**
1. Login successfully
2. Note the `tokenExpiresAt` value:

```javascript
const expiresAt = parseInt(localStorage.getItem('tokenExpiresAt'));
console.log('Initial expiry:', new Date(expiresAt).toLocaleString());
```

3. Click on "Đại Lý" (Agents) to load agent list
4. After data loads, check expiry again:

```javascript
const newExpiresAt = parseInt(localStorage.getItem('tokenExpiresAt'));
console.log('New expiry:', new Date(newExpiresAt).toLocaleString());
console.log('Extended by minutes:', (newExpiresAt - expiresAt) / (1000 * 60));
```

**Expected Result:**
- Token expiry timestamp should be refreshed
- Should show approximately 24 hours from current time
- Console shows token was extended

---

## Test 5: 5-Minute Periodic Check ✅

**Steps:**
1. Login successfully
2. Open Console, set expiry to expire in 1 minute:

```javascript
localStorage.setItem('tokenExpiresAt', (Date.now() + 60000).toString());
```

3. Wait for console message (max 5 min for periodic check)
4. Should see SweetAlert warning popup
5. Click "Đăng nhập" button
6. Redirected to login page

**Expected Behavior:**
- SweetAlert appears: "Phiên đăng nhập hết hạn"
- Message: "Phiên làm việc của bạn đã hết hạn. Vui lòng đăng nhập lại."
- Clicking OK redirects to login

---

## Test 6: Manual Logout Clears Both Tokens ✅

**Steps:**
1. Login successfully
2. Check localStorage has both tokens:

```javascript
console.log('Token:', localStorage.getItem('token') ? 'YES' : 'NO');
console.log('Expires At:', localStorage.getItem('tokenExpiresAt') ? 'YES' : 'NO');
```

3. Click logout button (top right menu)
4. Confirm logout
5. Check localStorage again:

```javascript
console.log('Token after logout:', localStorage.getItem('token') ? 'YES' : 'NO');
console.log('Expires At after logout:', localStorage.getItem('tokenExpiresAt') ? 'YES' : 'NO');
```

**Expected Result:**
```
Before logout:
Token: YES
Expires At: YES

After logout:
Token: NO
Expires At: NO
```

---

## Test 7: Agent App Session (index.html) ✅

**Steps:**
1. Open agent app
2. Login with agent credentials
3. Check Console for:
   ```
   ✓ Agent token saved to localStorage with 24h expiration
   ```

4. Check localStorage:

```javascript
console.log('Agent Token:', localStorage.getItem('agent_token') ? 'YES' : 'NO');
console.log('Agent Expires At:', localStorage.getItem('agent_token_expires_at') ? 'YES' : 'NO');
```

5. Refresh page (F5)
6. Should stay logged in (no redirect to login)

**Expected Result:**
- Agent dashboard appears after refresh
- Both tokens present in localStorage
- No unexpected logout

---

## Test 8: Agent App Expiry on Page Load ✅

**Steps:**
1. Open agent app
2. Login successfully
3. Set agent token to expired:

```javascript
localStorage.setItem('agent_token_expires_at', (Date.now() - 1000).toString());
```

4. Refresh page (F5)
5. Observe alert popup

**Expected Result:**
- Alert: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
- Redirected to login page
- All agent tokens cleared from localStorage

---

## Console Commands Reference

### View All Session Data
```javascript
console.log('=== ADMIN SESSION ===');
console.log('Token exists:', !!localStorage.getItem('token'));
console.log('Expires At:', localStorage.getItem('tokenExpiresAt'));
const adminExpires = parseInt(localStorage.getItem('tokenExpiresAt') || 0);
console.log('Hours left:', ((adminExpires - Date.now()) / (1000*60*60)).toFixed(2));

console.log('\n=== AGENT SESSION ===');
console.log('Agent Token exists:', !!localStorage.getItem('agent_token'));
console.log('Agent Expires At:', localStorage.getItem('agent_token_expires_at'));
const agentExpires = parseInt(localStorage.getItem('agent_token_expires_at') || 0);
console.log('Hours left:', ((agentExpires - Date.now()) / (1000*60*60)).toFixed(2));
```

### Clear All Session Data (Force Logout)
```javascript
localStorage.removeItem('token');
localStorage.removeItem('tokenExpiresAt');
localStorage.removeItem('agent_token');
localStorage.removeItem('agent_token_expires_at');
window.location.href = '/login.html';
```

### Manually Expire Token (Debug)
```javascript
// Admin token expires in 10 seconds
localStorage.setItem('tokenExpiresAt', (Date.now() + 10000).toString());
console.log('Admin token set to expire in 10 seconds');

// Agent token expires in 10 seconds
localStorage.setItem('agent_token_expires_at', (Date.now() + 10000).toString());
console.log('Agent token set to expire in 10 seconds');
```

### Extend Token (Simulate Activity)
```javascript
// Admin token extended 24h from now
localStorage.setItem('tokenExpiresAt', (Date.now() + 24*60*60*1000).toString());

// Agent token extended 24h from now
localStorage.setItem('agent_token_expires_at', (Date.now() + 24*60*60*1000).toString());
```

---

## Expected Console Messages

### Successful Login
```
✓ Token found in URL parameter
✓ Token saved to localStorage with 24h expiration
STATUS: [1/5] UI OK
STATUS: [2/5] OK
STATUS: [3/5] OK
✓ Loading screen hidden
```

### Page Reload (Valid Token)
```
DOMContentLoaded fired
Token still valid, continuing...
appState.token: eyJhbGc...
```

### Expired Token on Load
```
DOMContentLoaded fired
✗ Token expired on page load, logging out
```

### API Call (Sliding Window)
```
[No specific message, but token expiry gets refreshed]
```

### 5-Minute Check
```
SweetAlert popup appears with expiration warning
```

---

## Debugging Tips

### 1. Check Token Validity
```javascript
function debugToken() {
    const token = localStorage.getItem('token');
    const expiresAt = parseInt(localStorage.getItem('tokenExpiresAt') || 0);
    const now = Date.now();
    
    console.log('Token exists:', !!token);
    console.log('Expires at:', new Date(expiresAt).toLocaleString());
    console.log('Current time:', new Date(now).toLocaleString());
    console.log('Is expired:', now > expiresAt);
    console.log('Minutes left:', ((expiresAt - now) / (1000 * 60)).toFixed(1));
}

debugToken();
```

### 2. Simulate Time Passing
```javascript
// Set expiry to 23 hours from now
localStorage.setItem('tokenExpiresAt', (Date.now() + 23*60*60*1000).toString());

// Wait, then check how much time passed
setTimeout(() => {
    const expiresAt = parseInt(localStorage.getItem('tokenExpiresAt'));
    const hoursLeft = (expiresAt - Date.now()) / (1000*60*60);
    console.log('Hours left after delay:', hoursLeft.toFixed(2));
}, 60000); // 1 minute
```

### 3. Enable Detailed Logging
```javascript
// Add this to see all fetch requests with auth
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    console.log('📡 API Call:', args[0]);
    const response = await originalFetch(...args);
    console.log('📡 Response Status:', response.status);
    return response;
};
```

---

## Known Behavior

- ✅ Token extends automatically on API calls (sliding window)
- ✅ Works across browser tabs independently
- ✅ Persists across browser close/reopen
- ✅ Survives hard refresh (Ctrl+Shift+R)
- ✅ Clear browsing data will clear tokens
- ✅ Private/Incognito mode may not persist tokens
- ✅ Clock skew doesn't affect timing (uses client time)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Token not saving | Check browser allows localStorage |
| Still logged in after 24h | Token expiry timestamp wrong, check Date.now() |
| Logged out immediately | Token expiry in past, check browser clock |
| 5-min check not working | Check setInterval is running, look for console |
| SweetAlert not showing | Ensure SweetAlert2 library loaded |
| Redirect loop | Check URL rewriting not interfering |

---

## Success Criteria

✅ All 8 tests pass
✅ Token persists for 24 hours
✅ Sliding window extends session on activity
✅ Manual logout clears all tokens
✅ Expiration warning shows before logout
✅ Page reload respects token expiry
✅ Agent app has independent session
✅ Console shows expected messages
