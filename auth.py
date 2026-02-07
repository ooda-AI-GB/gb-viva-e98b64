import bcrypt
from itsdangerous import URLSafeSerializer, BadSignature

# In a real app, use a secure, randomly generated secret key
SECRET_KEY = "a-very-secret-key-that-should-be-in-env"
serializer = URLSafeSerializer(SECRET_KEY)

# Hardcoded users
USERS = {
    "employee1": {
        "password_hash": bcrypt.hashpw(b"pass1", bcrypt.gensalt()),
        "role": "employee",
        "name": "Alex Smith"
    },
    "employee2": {
        "password_hash": bcrypt.hashpw(b"pass2", bcrypt.gensalt()),
        "role": "employee",
        "name": "Jane Doe"
    },
    "manager": {
        "password_hash": bcrypt.hashpw(b"manage1", bcrypt.gensalt()),
        "role": "finance_manager",
        "name": "Sam Manager"
    }
}

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)

def get_user(username):
    return USERS.get(username)

def create_session_cookie(username: str) -> str:
    return serializer.dumps(username)

def get_username_from_cookie(cookie: str):
    try:
        return serializer.loads(cookie)
    except BadSignature:
        return None
