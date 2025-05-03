from fastapi import FastAPI
import auth
import places_logic

app = FastAPI()


@app.get("/auth")
def authentification(username: str, password: str) -> int:
    return auth.verify_users_credentials(username, password).id


#@app.get("/{user_id}/places")
#def get_users_places(user_id: int):
#    for user in auth.users:
#        if user.id == user_id:
#            return places_logic.get_user_places(user_id)
#    return None
    
