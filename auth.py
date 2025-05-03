from pydantic import BaseModel, TypeAdapter
USERS_FILE = "data/users.json"

class User(BaseModel):
    id: int
    username: str
    password: str

users = []

# --- Function to Load Data ---
def load_users_from_json(filepath: str) -> list:
    """Loads user data from a JSON file."""
    try:
        with open(filepath, "r") as f:
            json_content = f.read()
            user_list_adapter = TypeAdapter(list[User])
            users_data = user_list_adapter.validate_json(json_content)
            return users_data
    except FileNotFoundError:
        print(f"Error: User data file not found at '{filepath}'")
        return []

def verify_users_credentials(username: str, password: str) -> int:
    users = load_users_from_json(USERS_FILE)
    for user in users:
        if user.username == username:
            if user.password == password:
                return user
            return None
    return None