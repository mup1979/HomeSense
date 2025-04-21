import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_role(auth_id):
    result = supabase.table("users").select("role").eq("auth_id", auth_id).execute()
    return result.data[0]["role"] if result.data else None
