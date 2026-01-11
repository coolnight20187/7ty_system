# 7TY SYSTEM - COMPLETE API AUDIT
**Generated:** December 27, 2025

---

## TABLE OF CONTENTS
1. [Authentication Endpoints](#authentication-endpoints)
2. [Users Management Endpoints](#users-management-endpoints)
3. [Agents Management Endpoints](#agents-management-endpoints)
4. [Bills Management Endpoints](#bills-management-endpoints)
5. [Customers Endpoints](#customers-endpoints)
6. [Transactions Endpoints](#transactions-endpoints)
7. [Reports Endpoints](#reports-endpoints)
8. [Notifications Endpoints](#notifications-endpoints)
9. [System Dashboard Endpoints](#system-dashboard-endpoints)
10. [External API Endpoints](#external-api-endpoints)

---

## AUTHENTICATION ENDPOINTS
**Router:** `routers/auth.py`  
**Prefix:** `/api/auth` (inferred)

### 1. User Registration
- **Method:** `POST`
- **Path:** `/api/auth/register`
- **Auth Required:** ❌ No
- **Parameters:**
  - **Body:** `UserCreate`
    - `username` (string, required)
    - `email` (string, required)
    - `full_name` (string, required)
    - `phone` (string, optional)
    - `password` (string, required)
    - `role` (UserRole, optional, default: USER)
- **Response:** `SuccessResponse`
  - `message` (string)
  - `data` (object): `user_id`, `username`, `email`
- **Status Codes:** 201 Success, 400 Bad Request, 500 Server Error

### 2. User Login (v1)
- **Method:** `POST`
- **Path:** `/api/auth/login`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ IP-based
- **Parameters:**
  - **Body:** `LoginRequest`
    - `username` (string, required) - Can be username or email
    - `password` (string, required)
- **Response:** `Token`
  - `access_token` (string)
  - `refresh_token` (string)
  - `token_type` (string) - "bearer"
  - `expires_in` (integer) - seconds
- **Status Codes:** 200 Success, 401 Unauthorized, 429 Too Many Requests
- **Security:** Account lockout after 5 failed attempts (30 min), IP blocking after 10 failed attempts

### 3. User Login (v2) - Extended
- **Method:** `POST`
- **Path:** `/api/auth/login-v2`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ login_rate_limit()
- **Parameters:**
  - **Body:** `LoginRequest` (same as v1)
    - `username` (string)
    - `password` (string)
    - `remember_me` (boolean, optional)
- **Response:** `Token` (same as v1, but with extended expiry if remember_me=true)
- **Features:** Extended token expiry (7x normal) when remember_me is true

### 4. Refresh Token
- **Method:** `POST`
- **Path:** `/api/auth/refresh`
- **Auth Required:** ❌ No
- **Parameters:**
  - **Body:** `RefreshTokenRequest`
    - `refresh_token` (string, required)
- **Response:** `Token`
- **Status Codes:** 200 Success, 401 Unauthorized

### 5. Logout
- **Method:** `POST`
- **Path:** `/api/auth/logout`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** None
- **Response:** `SuccessResponse`
- **Status Codes:** 200 Success, 500 Server Error

### 6. Change Password
- **Method:** `POST`
- **Path:** `/api/auth/change-password`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Body:** `ChangePasswordRequest`
    - `old_password` (string, required)
    - `new_password` (string, required)
- **Response:** `SuccessResponse`
- **Validation:** Password strength validation required

### 7. Forgot Password
- **Method:** `POST`
- **Path:** `/api/auth/forgot-password`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ 3 requests per 5 minutes
- **Parameters:**
  - **Body:** `ForgotPasswordRequest`
    - `email` (string, required)
- **Response:** `SuccessResponse` - Always returns success message (doesn't reveal if email exists)
- **Features:** Sends reset email in background, generates 24-hour token

### 8. Reset Password
- **Method:** `POST`
- **Path:** `/api/auth/reset-password`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ 5 requests per 5 minutes
- **Parameters:**
  - **Body:** `ResetPasswordRequest`
    - `token` (string, required) - Reset token from email
    - `new_password` (string, required)
- **Response:** `SuccessResponse`
- **Status Codes:** 200 Success, 400 Bad Request

### 9. Verify 2FA Token
- **Method:** `POST`
- **Path:** `/api/auth/verify-2fa`
- **Auth Required:** ✓ Yes (current_user)
- **Rate Limiting:** ✓ 10 attempts per minute
- **Parameters:**
  - **Query:** `token` (string, required) - 6-digit 2FA code
- **Response:** `SuccessResponse`
- **Status Codes:** 200 Success, 400 Bad Request

### 10. Enable 2FA
- **Method:** `POST`
- **Path:** `/api/auth/enable-2fa`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** None
- **Response:** `SuccessResponse`
  - `data`: `{"secret": "base32_secret_string"}`
- **Features:** Returns QR code secret for authenticator apps

### 11. Disable 2FA
- **Method:** `POST`
- **Path:** `/api/auth/disable-2fa`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** None
- **Response:** `SuccessResponse`

### 12. Get Current User Info
- **Method:** `GET`
- **Path:** `/api/auth/me`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** None
- **Response:** `UserResponse`

### 13. Get User Sessions
- **Method:** `GET`
- **Path:** `/api/auth/sessions`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** None
- **Response:** Object with active sessions list

### 14. Revoke Session
- **Method:** `POST`
- **Path:** `/api/auth/sessions/{session_id}/revoke`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:** 
  - **Path:** `session_id` (integer)
- **Response:** `SuccessResponse`

### 15. Check Username Availability
- **Method:** `GET`
- **Path:** `/api/auth/check-username/{username}`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ 20 requests per minute
- **Parameters:**
  - **Path:** `username` (string)
- **Response:** Object with `available` (boolean)

### 16. Check Email Availability
- **Method:** `GET`
- **Path:** `/api/auth/check-email/{email}`
- **Auth Required:** ❌ No
- **Rate Limiting:** ✓ 20 requests per minute
- **Parameters:**
  - **Path:** `email` (string)
- **Response:** Object with `available` (boolean)

### 17. Get User Activities
- **Method:** `GET`
- **Path:** `/api/auth/activities`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 20)
- **Response:** Object with activities list and pagination

### 18. Lock User Account
- **Method:** `POST`
- **Path:** `/api/auth/lock-account/{user_id}`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `user_id` (integer)
  - **Query:** `duration_minutes` (integer, default: 30)
  - **Query:** `reason` (string, optional)
- **Response:** `SuccessResponse` with lock details

### 19. Unlock User Account
- **Method:** `POST`
- **Path:** `/api/auth/unlock-account/{user_id}`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `SuccessResponse`

### 20. Auth Health Check
- **Method:** `GET`
- **Path:** `/api/auth/health`
- **Auth Required:** ❌ No
- **Response:** Object with service health status

### 21. Agent Mobile App Login
- **Method:** `POST`
- **Path:** `/api/auth/agent-login`
- **Auth Required:** ❌ No
- **Parameters:**
  - **Body:** `LoginRequest`
    - `username` (string)
    - `password` (string)
- **Response:** Token object (similar to standard login)
- **Restrictions:** Agent role required, agent must be ACTIVE status

---

## USERS MANAGEMENT ENDPOINTS
**Router:** `routers/users.py`  
**Prefix:** `/api/users`

### 1. Get Current User Profile
- **Method:** `GET`
- **Path:** `/api/users/me`
- **Auth Required:** ✓ Yes (current_active_user)
- **Response:** `UserResponse`

### 2. List All Users
- **Method:** `GET`
- **Path:** `/api/users/`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `sort_by` (string, optional)
  - **Query:** `sort_order` (string: "asc"/"desc", default: "desc")
  - **Query:** `search` (string, optional) - Search by username, email, or full name
  - **Query:** `role` (UserRole, optional)
  - **Query:** `is_active` (boolean, optional)
  - **Query:** `created_from` (datetime, optional)
  - **Query:** `created_to` (datetime, optional)
- **Response:** Object with users array and pagination metadata
  - `users` (array): User objects with id, username, email, role, etc.
  - `pagination`: `{page, limit, total, pages}`

### 3. Get User by ID
- **Method:** `GET`
- **Path:** `/api/users/{user_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `UserResponse`
- **Permissions:** Users can view own profile, admins can view any

### 4. Create New User
- **Method:** `POST`
- **Path:** `/api/users/`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Body:** `UserCreate`
    - `username` (string, required)
    - `email` (string, required)
    - `full_name` (string, required)
    - `phone` (string, optional)
    - `password` (string, required)
    - `role` (UserRole, optional)
    - `is_active` (boolean, optional)
- **Response:** `UserResponse`

### 5. Update User
- **Method:** `PUT`
- **Path:** `/api/users/{user_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `user_id` (integer)
  - **Body:** `UserUpdate` (all fields optional)
    - `email`, `full_name`, `phone`, `password`, `role`, `is_active`
- **Response:** `UserResponse`
- **Permissions:** Users can update own profile, non-admins cannot change role/active status

### 6. Update User Role
- **Method:** `PATCH`
- **Path:** `/api/users/{user_id}/role`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `user_id` (integer)
  - **Body:** `UserRoleUpdate`
    - `role` (UserRole, required)
- **Response:** `UserResponse`
- **Restrictions:** Cannot change own role, cannot demote last admin

### 7. Activate User Account
- **Method:** `PATCH`
- **Path:** `/api/users/{user_id}/activate`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `UserResponse`

### 8. Deactivate User Account
- **Method:** `PATCH`
- **Path:** `/api/users/{user_id}/deactivate`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `UserResponse`
- **Restrictions:** Cannot deactivate own account, cannot deactivate last admin

### 9. Unlock User Account
- **Method:** `PATCH`
- **Path:** `/api/users/{user_id}/unlock`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `UserResponse`
- **Effect:** Resets failed login attempts and locked_until timestamp

### 10. Delete User (Soft Delete)
- **Method:** `DELETE`
- **Path:** `/api/users/{user_id}`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** `SuccessResponse`
- **Restrictions:** Cannot delete own account, cannot delete last admin

### 11. Reset User Password
- **Method:** `POST`
- **Path:** `/api/users/{user_id}/reset-password`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `user_id` (integer)
  - **Body:** `ChangePasswordRequest`
    - `old_password` (string) - Required if user resetting own password
    - `new_password` (string, required)
- **Response:** `SuccessResponse`
- **Permissions:** Users can reset own, admins can reset any

### 12. Get User Activities
- **Method:** `GET`
- **Path:** `/api/users/{user_id}/activities`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `user_id` (integer)
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 20, max: 100)
- **Response:** Object with activities array and pagination
- **Permissions:** Users can view own, managers/admins can view any

### 13. Impersonate User
- **Method:** `POST`
- **Path:** `/api/users/{user_id}/impersonate`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `user_id` (integer)
- **Response:** Object with impersonation token (30-min validity)
- **Features:** Logs impersonation action, requires ALLOW_IMPERSONATION setting

### 14. Get Users Statistics
- **Method:** `GET`
- **Path:** `/api/users/stats/summary`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Response:** Object with stats
  - `total_users`, `active_users`, `inactive_users`
  - `new_users_this_month`, `locked_accounts`
  - `active_last_7_days`, `users_by_role`

### 15. Export Users to CSV
- **Method:** `GET`
- **Path:** `/api/users/export/csv`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Query:** `role` (UserRole, optional)
  - **Query:** `is_active` (boolean, optional)
- **Response:** CSV file download

---

## AGENTS MANAGEMENT ENDPOINTS
**Router:** `routers/agents.py`  
**Prefix:** `/api/agents`

### 1. List Agents
- **Method:** `GET`
- **Path:** `/api/agents`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `sort_by` (string, optional)
  - **Query:** `sort_order` (string: "asc"/"desc")
  - **Query:** `status` (AgentStatus, optional)
  - **Query:** `agent_type` (AgentType, optional)
  - **Query:** `search` (string, optional)
  - **Query:** `created_from` (date, optional)
  - **Query:** `created_to` (date, optional)
- **Response:** `PaginatedResponse` with agents array
  - Each agent includes: id, user_id, agent_code, agent_name, company_name, tax_code, address, city, district, ward, agent_type, status, commission_rate, balance, user object, created_at, updated_at, approved_at, approved_by

### 2. Get Agents Statistics
- **Method:** `GET`
- **Path:** `/api/agents/stats`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Response:** Object with statistics
  - `total_agents`, `active_agents`, `pending_approval`
  - `total_balance`, `total_frozen_balance`, `total_sales_30d`
  - `by_status` (map), `by_type` (map)

### 3. Get Agent Details
- **Method:** `GET`
- **Path:** `/api/agents/{agent_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `agent_id` (integer)
- **Response:** `AgentResponse` with full details including stats
  - Stats include: today_sales, today_bills, total_customers, success_rate, total_assigned_bills, total_sold_bills

### 4. Create Agent with User (Atomic)
- **Method:** `POST`
- **Path:** `/api/agents/with-user`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Body:** `AgentCreateWithUser`
    - `username` (string, required)
    - `full_name` (string, required)
    - `phone` (string, optional)
    - `password` (string, required)
    - `agent_code` (string, required)
    - `agent_name` (string, optional)
    - `agent_type` (AgentType: "individual"/"business", required)
    - `company_name` (string, optional)
    - `tax_code` (string, optional)
    - `address` (string, optional)
    - `city` (string, optional)
    - `district` (string, optional)
    - `ward` (string, optional)
    - `status` (AgentStatus, optional)
    - `commission_rate` (decimal, optional)
- **Response:** `AgentResponse`
- **Features:** Creates user and agent in single atomic transaction, auto-generates email

### 5. Create Agent (Existing User)
- **Method:** `POST`
- **Path:** `/api/agents`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Body:** `AgentCreate`
    - `user_id` (integer, required)
    - `agent_code` (string, required)
    - `company_name` (string, optional)
    - `tax_code` (string, optional)
    - `agent_type` (AgentType, required)
    - `status` (AgentStatus, optional)
    - `commission_rate` (decimal, optional)
    - `min_commission`, `max_commission`, `daily_limit`, `per_transaction_limit` (optional)
    - `approval_notes` (string, optional)
- **Response:** `AgentResponse`

### 6. Update Agent
- **Method:** `PUT`
- **Path:** `/api/agents/{agent_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Body:** `AgentUpdate` (all fields optional)
- **Response:** `AgentResponse`
- **Permissions:** Only managers/admins or the agent themselves can update

### 7. Delete Agent
- **Method:** `DELETE`
- **Path:** `/api/agents/{agent_id}`
- **Auth Required:** ✓ Yes (admin_only)
- **Parameters:**
  - **Path:** `agent_id` (integer)
- **Response:** Success message
- **Effect:** Soft delete (marks as deleted)

### 8. Approve Agent
- **Method:** `POST`
- **Path:** `/api/agents/{agent_id}/approve`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Query:** `approval_notes` (string, optional)
- **Response:** `SuccessResponse` with approval details

### 9. Suspend Agent
- **Method:** `POST`
- **Path:** `/api/agents/{agent_id}/suspend`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Query:** `reason` (string, required)
- **Response:** `SuccessResponse`

### 10. Reactivate Agent
- **Method:** `POST`
- **Path:** `/api/agents/{agent_id}/reactivate`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `agent_id` (integer)
- **Response:** `SuccessResponse`
- **Restriction:** Only suspended agents can be reactivated

### 11. Get Agent Bills
- **Method:** `GET`
- **Path:** `/api/agents/{agent_id}/bills`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `status` (BillStatus, optional)
  - **Query:** `start_date` (date, optional)
  - **Query:** `end_date` (date, optional)
- **Response:** `PaginatedResponse` with bills and summary (total_amount, total_commission, total_bills)

### 12. Get Agent Customers
- **Method:** `GET`
- **Path:** `/api/agents/{agent_id}/customers`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `search` (string, optional)
- **Response:** `PaginatedResponse` with customers

### 13. Get Agent Transactions
- **Method:** `GET`
- **Path:** `/api/agents/{agent_id}/transactions`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `agent_id` (integer)
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `transaction_type` (TransactionType, optional)
  - **Query:** `start_date` (date, optional)
  - **Query:** `end_date` (date, optional)
- **Response:** `PaginatedResponse` with transactions

---

## BILLS MANAGEMENT ENDPOINTS
**Router:** `routers/bills.py`  
**Prefix:** `/api/bills`

### 1. List Bills
- **Method:** `GET`
- **Path:** `/api/bills`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Query:** `page` (integer, default: 1)
  - **Query:** `limit` (integer, default: 10)
  - **Query:** `sort_by` (string, optional)
  - **Query:** `sort_order` (string: "asc"/"desc")
  - **Query:** `status` (BillStatus, optional)
  - **Query:** `period_from` (date, optional)
  - **Query:** `period_to` (date, optional)
  - **Query:** `agent_id` (integer, optional)
  - **Query:** `customer_code` (string, optional)
  - **Query:** `amount_from` (decimal, optional)
  - **Query:** `amount_to` (decimal, optional)
- **Response:** `PaginatedResponse` with bills
- **Restrictions:** Agents can only see their own bills

### 2. Get Bills Statistics
- **Method:** `GET`
- **Path:** `/api/bills/stats`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Response:** Object with statistics
  - `total_bills`, `total_amount`
  - `by_status` (map), `overdue_bills`, `today_sales`
  - `monthly_trend` (last 6 months)
  - `top_agents` (last 30 days)

### 3. Get Bill Details
- **Method:** `GET`
- **Path:** `/api/bills/{bill_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `bill_id` (integer)
- **Response:** `BillResponse`
- **Permissions:** Agents can only view their own bills

### 4. Create Bill
- **Method:** `POST`
- **Path:** `/api/bills`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Body:** `BillCreate`
    - `customer_code` (string, required)
    - `customer_name` (string, required)
    - `customer_address` (string, optional)
    - `customer_phone` (string, optional)
    - `evn_customer_code` (string, optional)
    - `period` (string: "YYYY-MM", required)
    - `due_date` (date, optional)
    - `total_amount` (decimal, required)
    - `electricity_amount` (decimal, optional)
    - `vat_amount` (decimal, optional)
    - `other_fees` (decimal, optional)
    - `consumption` (decimal, optional)
    - `previous_index`, `current_index` (integer, optional)
    - `agent_id` (integer, optional)
    - `status` (BillStatus, optional)
    - `evn_bill_code` (string, optional)
    - `notes` (string, optional)
    - `imported_file` (string, optional)
- **Response:** `BillResponse`

### 5. Update Bill
- **Method:** `PUT`
- **Path:** `/api/bills/{bill_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `bill_id` (integer)
  - **Body:** `BillUpdate` (all fields optional)
- **Response:** `BillResponse`
- **Restriction:** Cannot update paid bills

### 6. Assign Bill to Agent
- **Method:** `POST`
- **Path:** `/api/bills/{bill_id}/assign/{agent_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `bill_id` (integer)
  - **Path:** `agent_id` (integer)
- **Response:** `SuccessResponse` with assignment details
- **Restrictions:** Only managers/admins, bill must be IN_STOCK

### 7. Agent Purchases Bill
- **Method:** `POST`
- **Path:** `/api/bills/{bill_id}/purchase`
- **Auth Required:** ✓ Yes (current_active_agent)
- **Parameters:**
  - **Path:** `bill_id` (integer)
- **Response:** `SuccessResponse` with purchase details
- **Checks:** 
  - Sufficient balance
  - Per-transaction limit
  - Daily limit

### 8. Pay Bill
- **Method:** `POST`
- **Path:** `/api/bills/{bill_id}/pay`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `bill_id` (integer)
  - **Query:** `payment_method` (string, default: "cash")
  - **Query:** `transaction_ref` (string, optional)
- **Response:** `SuccessResponse` with payment details
- **Restriction:** Bill must be in SOLD status

### 9. Cancel Bill
- **Method:** `POST`
- **Path:** `/api/bills/{bill_id}/cancel`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `bill_id` (integer)
  - **Query:** `reason` (string, required)
- **Response:** `SuccessResponse`
- **Restrictions:** Only managers/admins, cannot cancel PAID bills

### 10. Delete Bill (Soft Delete)
- **Method:** `DELETE`
- **Path:** `/api/bills/{bill_id}`
- **Auth Required:** ✓ Yes (manager_or_admin)
- **Parameters:**
  - **Path:** `bill_id` (integer)
- **Response:** `SuccessResponse`
- **Restriction:** Cannot delete SOLD or PAID bills

---

## CUSTOMERS ENDPOINTS
**Router:** `routers/customers.py`  
**Prefix:** `/api/customers` (inferred as `/` based on router tag)

### 1. List Customers
- **Method:** `GET`
- **Path:** `/api/customers/`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Query:** `skip` (integer, default: 0)
  - **Query:** `limit` (integer, default: 100, max: 1000)
  - **Query:** `status` (string: "active"/"inactive", optional)
  - **Query:** `province` (string, optional)
  - **Query:** `district` (string, optional)
  - **Query:** `ward` (string, optional)
  - **Query:** `from_date` (date, optional)
  - **Query:** `to_date` (date, optional)
  - **Query:** `has_bills` (boolean, optional)
  - **Query:** `min_bills` (integer, optional)
  - **Query:** `max_bills` (integer, optional)
  - **Query:** `search` (string, optional) - Search in code, name, phone, email, address
- **Response:** Array of `CustomerResponse`
- **Permissions:** Agents see only customers with their bills

### 2. Create Customer
- **Method:** `POST`
- **Path:** `/api/customers/`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Body:** `CustomerCreate`
    - `customer_code` (string, required)
    - `customer_name` (string, required)
    - `phone` (string, optional) - Validated Vietnamese format
    - `email` (string, optional)
    - `address` (string, optional)
    - `province`, `district`, `ward` (string, optional)
    - `status` (string: "active"/"inactive", optional)
    - And other customer fields
- **Response:** `CustomerResponse` (201 Created)

### 3. Get Customer Details
- **Method:** `GET`
- **Path:** `/api/customers/{customer_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `customer_id` (integer)
- **Response:** `CustomerResponse`
- **Permissions:** Agents can only access customers with their bills

### 4. Update Customer
- **Method:** `PUT`
- **Path:** `/api/customers/{customer_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `customer_id` (integer)
  - **Body:** `CustomerUpdate` (all fields optional)
- **Response:** `CustomerResponse`
- **Permissions:** Admin/staff or creator can update

### 5. Delete Customer
- **Method:** `DELETE`
- **Path:** `/api/customers/{customer_id}`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `customer_id` (integer)
- **Response:** Success message
- **Restrictions:** Admin only, customer must not have any bills

### 6. Get Customer Bills
- **Method:** `GET`
- **Path:** `/api/customers/{customer_id}/bills`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `customer_id` (integer)
  - **Query:** `skip` (integer, default: 0)
  - **Query:** `limit` (integer, default: 50, max: 200)
  - **Query:** `status` (string, optional)
  - **Query:** `from_date` (date, optional)
  - **Query:** `to_date` (date, optional)
- **Response:** Object with customer info and bills array

### 7. Get Customer Statistics
- **Method:** `GET`
- **Path:** `/api/customers/{customer_id}/stats`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Path:** `customer_id` (integer)
  - **Query:** `from_date` (date, optional)
  - **Query:** `to_date` (date, optional)
- **Response:** `CustomerStats`
  - `total_bills`, `total_amount`, `average_amount`
  - `by_status` (map)
  - `by_period` (last 12 periods)
  - `by_month` (last 12 months)

### 8. Advanced Customer Search
- **Method:** `GET`
- **Path:** `/api/customers/search/advanced`
- **Auth Required:** ✓ Yes (current_user)
- **Parameters:**
  - **Query:** `query_string` (string, required, min: 2 chars)
  - **Query:** `search_fields` (string: "all"/"code"/"name"/"phone"/"email"/"address", default: "all")
- **Response:** `CustomerSearchResponse`

---

## TRANSACTIONS ENDPOINTS
**Router:** `routers/transactions.py`  
**Prefix:** `/api/v1` (inferred from context)

### 1. List Transactions
- **Method:** `GET`
- **Path:** `/api/v1/transactions/`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Query:** `skip` (integer, default: 0)
  - **Query:** `limit` (integer, default: 100, max: 1000)
  - **Query:** `agent_id` (integer, optional)
  - **Query:** `bill_id` (integer, optional)
  - **Query:** `transaction_type` (TransactionType, optional)
  - **Query:** `status` (TransactionStatus, optional)
  - **Query:** `start_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `end_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `min_amount` (float, optional)
  - **Query:** `max_amount` (float, optional)
  - **Query:** `search` (string, optional) - Search in code, full_name, agent_code, description
- **Response:** `PaginatedResponse` with transactions

### 2. Get Transaction Statistics
- **Method:** `GET`
- **Path:** `/api/v1/transactions/stats`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Query:** `period` (string: "today"/"yesterday"/"week"/"month"/"year"/"custom", default: "today")
  - **Query:** `start_date` (string: "YYYY-MM-DD", required if period="custom")
  - **Query:** `end_date` (string: "YYYY-MM-DD", required if period="custom")
- **Response:** `TransactionStatsResponse`
  - `total_count`, `total_amount`, `avg_amount`, `max_amount`, `min_amount`
  - `by_type` (array)
  - `by_status` (array)

### 3. Get Transaction Details
- **Method:** `GET`
- **Path:** `/api/v1/transactions/{transaction_id}`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Path:** `transaction_id` (integer)
- **Response:** `TransactionResponse`
- **Permissions:** Admins see all, agents see own agent's transactions

### 4. Create Transaction
- **Method:** `POST`
- **Path:** `/api/v1/transactions/`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Body:** `TransactionCreate`
    - `agent_id` (integer, required)
    - `bill_id` (integer, optional)
    - `transaction_type` (TransactionType, required)
    - `amount` (float, required)
    - `fee` (float, optional)
    - `description` (string, optional)
    - `status` (TransactionStatus, optional)
- **Response:** `TransactionResponse`
- **Features:** Auto-generates transaction code, updates agent balance if COMPLETED

### 5. Update Transaction
- **Method:** `PUT`
- **Path:** `/api/v1/transactions/{transaction_id}`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Path:** `transaction_id` (integer)
  - **Body:** `TransactionUpdate` (all fields optional)
- **Response:** `TransactionResponse`
- **Features:** Updates agent balance if status changes to COMPLETED

### 6. Delete Transaction
- **Method:** `DELETE`
- **Path:** `/api/v1/transactions/{transaction_id}`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Path:** `transaction_id` (integer)
- **Response:** `SuccessResponse`
- **Restriction:** Cannot delete COMPLETED transactions

### 7. Export Transactions
- **Method:** `POST`
- **Path:** `/api/v1/transactions/export`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Body:** `TransactionFilter`
    - `agent_id`, `transaction_type`, `status` (optional)
    - `start_date`, `end_date` (string: "YYYY-MM-DD", optional)
    - `min_amount`, `max_amount` (float, optional)
  - **Query:** `format` (string: "excel"/"csv", default: "excel")
- **Response:** File download (Excel or CSV)

---

## REPORTS ENDPOINTS
**Router:** `routers/reports.py`  
**Prefix:** `/api/reports` (inferred)

### 1. Get Reports List
- **Method:** `GET`
- **Path:** `/api/reports/`
- **Auth Required:** ✓ Yes (current_active_user)
- **Response:** Object with message "Reports endpoint"

### 2. Get Report Summary
- **Method:** `GET`
- **Path:** `/api/reports/summary`
- **Auth Required:** ✓ Yes (current_active_user)
- **Response:** Object with message "Report summary"

---

## NOTIFICATIONS ENDPOINTS
**Router:** `routers/notifications.py`  
**Prefix:** `/api/notifications`

### 1. Get Unread Count
- **Method:** `GET`
- **Path:** `/api/notifications/unread-count`
- **Auth Required:** ✓ Yes (current_active_user)
- **Response:** Object with `unread_count` (integer)

### 2. Get Unread Notifications
- **Method:** `GET`
- **Path:** `/api/notifications/unread`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Query:** `limit` (integer, default: 10, max: 100)
- **Response:** Array of unread notifications
  - Fields: `id`, `title`, `message`, `type`, `is_read`, `action_url`, `icon`, `priority`, `created_at`

### 3. List All Notifications
- **Method:** `GET`
- **Path:** `/api/notifications`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Query:** `is_read` (boolean, optional)
  - **Query:** `limit` (integer, default: 20, max: 100)
  - **Query:** `offset` (integer, default: 0)
- **Response:** Object with notifications array and pagination

### 4. Mark Notification as Read
- **Method:** `PUT`
- **Path:** `/api/notifications/{notification_id}/read`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Path:** `notification_id` (integer)
- **Response:** Success object with message

### 5. Mark All Notifications as Read
- **Method:** `PUT`
- **Path:** `/api/notifications/read-all`
- **Auth Required:** ✓ Yes (current_active_user)
- **Response:** Success object with message

### 6. Delete Notification
- **Method:** `DELETE`
- **Path:** `/api/notifications/{notification_id}`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Path:** `notification_id` (integer)
- **Response:** Success object with message

---

## SYSTEM DASHBOARD ENDPOINTS
**Router:** `routers/system.py`  
**Prefix:** `/api/system` (inferred)

### 1. Get Dashboard Statistics
- **Method:** `GET`
- **Path:** `/api/system/dashboard`
- **Auth Required:** ✓ Yes (current_active_user)
- **Parameters:**
  - **Query:** `period` (string: "today"/"week"/"month"/"year"/"custom", default: "today")
  - **Query:** `start_date` (string: "YYYY-MM-DD", required if period="custom")
  - **Query:** `end_date` (string: "YYYY-MM-DD", required if period="custom")
- **Response:** `DashboardResponse`
  - `stats`: DashboardStats object
  - `sales_data`: Array of SalesChartData
  - `bills_data`: Array of BillsChartData
  - `recent_activities`: Array of recent activity logs
  - `top_agents`: Array of top performing agents

### 2. Generate Sales Report
- **Method:** `POST`
- **Path:** `/api/system/reports/sales`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Body:** `ReportRequest`
    - `start_date` (date, required)
    - `end_date` (date, required)
    - `group_by` (string: "daily"/"weekly"/"monthly"/"yearly", optional)
    - `agent_id` (integer, optional)
    - `status` (BillStatus, optional)
- **Response:** `ReportResponse`
  - `total_amount`, `total_bills`, `total_commission`
  - `items` (array of SalesReportItem)
  - `summary` (avg_daily_sales, avg_bill_amount, commission_rate)

### 3. Generate Agent Report
- **Method:** `POST`
- **Path:** `/api/system/reports/agents`
- **Auth Required:** ✓ Yes (current_active_admin)
- **Parameters:**
  - **Body:** `ReportRequest` (same as sales report)
- **Response:** `ReportResponse`
  - Items array contains agent-specific metrics

---

## EXTERNAL API ENDPOINTS
**Router:** `routers/api.py`  
**Prefix:** `/api/v1`

### Authentication
All endpoints require API signature verification:
- **Headers Required:**
  - `X-API-Key` (agent API key)
  - `X-Timestamp` (ISO format datetime, max 5 min old)
  - `X-Signature` (HMAC-SHA256 signature)

### 1. Get Agent Balance
- **Method:** `GET`
- **Path:** `/api/v1/balance`
- **Auth Required:** ✓ Yes (API signature)
- **Response:** `ApiBalanceResponse`
  - `agent_code`, `balance`, `credit_limit`, `available_balance`
  - `currency` (VND), `last_updated`

### 2. Check Bill
- **Method:** `POST`
- **Path:** `/api/v1/bills/check`
- **Auth Required:** ✓ Yes (API signature)
- **Parameters:**
  - **Body:** `ApiCheckBillRequest`
    - `customer_code` (string, required)
    - `period` (string: "YYYY-MM", required)
- **Response:** `ApiCheckBillResponse`
  - If found: bill details (id, code, customer info, period, amount, due_date, status, created_at)
  - If not found: success=false with message

### 3. Pay Bill
- **Method:** `POST`
- **Path:** `/api/v1/bills/pay`
- **Auth Required:** ✓ Yes (API signature)
- **Parameters:**
  - **Body:** `ApiBillPaymentRequest`
    - `bill_id` (integer, required)
    - `fee` (decimal, optional)
    - `reference_id` (string, optional)
    - `payment_method` (string, optional)
    - `customer_ip` (string, optional)
    - `device_info` (string, optional)
- **Response:** `ApiBillPaymentResponse`
  - `transaction_id`, `transaction_code`, `amount`, `fee`, `new_balance`
  - `payment_time` (ISO datetime)
- **Features:** Sends webhook notification if configured

### 4. Top Up Account
- **Method:** `POST`
- **Path:** `/api/v1/topup`
- **Auth Required:** ✓ Yes (API signature)
- **Parameters:**
  - **Body:** `ApiTopUpRequest`
    - `amount` (decimal, required)
    - `reference_id` (string, optional)
    - `payment_method` (string, optional)
    - `bank_account` (string, optional)
    - `transaction_date` (date, optional)
- **Response:** `ApiTopUpResponse`
  - `transaction_id`, `transaction_code`, `amount`, `status` (pending)
  - `created_at` (ISO datetime)

### 5. Get Agent Transactions
- **Method:** `GET`
- **Path:** `/api/v1/transactions`
- **Auth Required:** ✓ Yes (API signature)
- **Parameters:**
  - **Query:** `start_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `end_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `transaction_type` (string, optional)
  - **Query:** `status` (string, optional)
  - **Query:** `limit` (integer, default: 100, max: 500)
  - **Query:** `offset` (integer, default: 0)
- **Response:** Array of `ApiTransactionResponse`
  - Fields: `id`, `transaction_code`, `type`, `amount`, `fee`, `total`, `status`, `description`, `bill_code`, `customer_code`, `created_at`, `completed_at`

### 6. Get Bill History
- **Method:** `GET`
- **Path:** `/api/v1/bills/history`
- **Auth Required:** ✓ Yes (API signature)
- **Parameters:**
  - **Query:** `start_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `end_date` (string: "YYYY-MM-DD", optional)
  - **Query:** `status` (string, optional)
  - **Query:** `customer_code` (string, optional)
  - **Query:** `limit` (integer, default: 100, max: 500)
  - **Query:** `offset` (integer, default: 0)
- **Response:** Array of `ApiBillResponse`
  - Fields: `id`, `bill_code`, `customer_code`, `customer_name`, `customer_address`, `period`, `total_amount`, `status`, `sold_at`, `paid_at`, `payment_method`

### 7. Get Agent Info
- **Method:** `GET`
- **Path:** `/api/v1/agent/info`
- **Auth Required:** ✓ Yes (API signature)
- **Response:** `ApiAgentInfoResponse`
  - `agent_code`, `full_name`, `company_name`, `phone`, `email`
  - `balance`, `credit_limit`, `available_balance`
  - `today_bills`, `today_sales`, `month_bills`, `month_sales`

---

## AUTHENTICATION & AUTHORIZATION SUMMARY

### User Roles
1. **ADMIN** - Full system access, user management
2. **MANAGER** - Agent and bill management
3. **STAFF** - Limited access to bills and reports
4. **AGENT** - Self-service access to assigned bills and account
5. **USER** - Basic user access

### Dependency Functions
- `get_current_user` - Basic authentication (token required)
- `get_current_active_user` - Active user required
- `admin_only()` - Admin role required
- `manager_or_admin()` - Manager or Admin role required
- `get_current_active_agent` - Authenticated agent user
- `get_current_active_admin` - Active admin user

### Rate Limiting
- General API: Per-IP rate limiting
- Login: IP-based with account lockout
- Forgot Password: 3 requests per 5 minutes
- Reset Password: 5 requests per 5 minutes
- 2FA: 10 attempts per minute
- Check Username/Email: 20 requests per minute

### Security Features
- JWT token-based authentication
- Password hashing with bcrypt
- 2FA support (TOTP)
- Account lockout after failed attempts
- IP blocking for repeated failures
- Activity logging
- Session management
- API signature verification (HMAC-SHA256)
- Webhook signature validation

---

## ERROR RESPONSES

### Standard HTTP Status Codes
- **200 OK** - Successful GET, PUT, PATCH
- **201 Created** - Successful POST (resource creation)
- **204 No Content** - Successful DELETE
- **400 Bad Request** - Invalid input parameters
- **401 Unauthorized** - Missing/invalid authentication
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - Resource not found
- **409 Conflict** - Resource already exists
- **423 Locked** - Account locked (too many failed attempts)
- **429 Too Many Requests** - Rate limit exceeded
- **500 Internal Server Error** - Server-side error

### Error Response Format
```json
{
  "detail": "Error message describing the issue"
}
```

---

## SUMMARY STATISTICS

- **Total Routers:** 10
- **Total Endpoints:** 100+ (estimated based on full audit)
- **Authentication Methods:** JWT, API Key + HMAC
- **Rate Limiting:** Yes (multiple strategies)
- **Audit Logging:** Yes
- **2FA Support:** Yes
- **Soft Delete:** Yes (for users, agents, bills)
- **Pagination:** Yes (most list endpoints)
- **Search/Filter:** Yes (most list endpoints)
- **Export:** Yes (users CSV, transactions Excel/CSV)
- **Webhooks:** Yes (for API bill payments)

---

## NOTES FOR DEVELOPERS

1. **Database Changes:** Updates to user/agent/bill records are logged for audit trail
2. **Email Notifications:** Background tasks used for email delivery
3. **Activity Logging:** Most state-changing operations are logged
4. **Atomic Transactions:** Agent creation with user is atomic
5. **Soft Deletes:** Users, agents, and bills support soft delete
6. **Cache Usage:** Some operations use caching for performance (login attempts, password reset tokens)
7. **API Signature:** All external API endpoints require HMAC-SHA256 signature verification
8. **Pagination Default:** Usually 10-20 items per page, configurable up to 1000
9. **Date Formats:** ISO 8601 for responses (datetime), YYYY-MM-DD for date queries

---

**END OF API AUDIT DOCUMENT**
