"""
init_config.py — run ONCE to create config.yaml with your first account.
=========================================================================
RUN:  python init_config.py

This creates config.yaml holding user credentials. Passwords are stored
bcrypt-HASHED, never in plain text — even you can't read them back from the file.
After this, you can register more users from the app's Sign up tab.

The cookie 'key' below signs the login cookie in the browser. Change it to any
random string. Treat it like a secret: don't commit the real one to GitHub.
"""
import yaml
import streamlit_authenticator as stauth

# --- edit these for your first account ---
NAME = "Pavi"
USERNAME = "pavi"
EMAIL = "pavi@example.com"
PLAIN_PASSWORD = "changeme123"   # you'll log in with this, then can change it
# -----------------------------------------

# Hash the plain password with bcrypt. Hasher.hash() returns the hashed string.
hashed = stauth.Hasher.hash(PLAIN_PASSWORD)

config = {
    "credentials": {
        "usernames": {
            USERNAME: {
                "name": NAME,
                "email": EMAIL,
                "password": hashed,   # stored hashed, not plain
            }
        }
    },
    "cookie": {
        "name": "marginalia_auth",
        "key": "REPLACE_WITH_A_RANDOM_SECRET_STRING",
        "expiry_days": 7,             # stay logged in for 7 days
    },
}

with open("config.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False)

print("Wrote config.yaml")
print(f"Login with username '{USERNAME}' and the password you set above.")
print("Now run:  python -m streamlit run app.py")
