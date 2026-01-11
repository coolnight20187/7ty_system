-- Initialize admin user
INSERT INTO users (
    username, 
    full_name, 
    email, 
    password_hash, 
    role, 
    is_active, 
    is_verified, 
    login_attempts, 
    two_factor_enabled, 
    api_calls_count, 
    is_deleted, 
    created_at, 
    updated_at
) VALUES (
    'admin',
    'System Administrator',
    'admin@7ty.vn',
    '$argon2id$v=19$m=65536,t=3,p=4$PEfoPacUotQaA8A459yb8w$b1k8bTtWTpfzmxhAQTVkGz/vN0TeUN9Mrf/2OrVmh88',
    'ADMIN',
    true,
    true,
    0,
    false,
    0,
    false,
    NOW(),
    NOW()
)
ON CONFLICT (username) DO NOTHING;
