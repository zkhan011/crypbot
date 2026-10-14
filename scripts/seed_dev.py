from app.core.security import hash_password
print({'email':'dev-admin@example.local','password_hash_prefix':hash_password('ChangeMe-Dev-Only!')[:20],'note':'insert via migrations/repository in local dev'})
