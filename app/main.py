from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

# Mount static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Home page → login
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Handle login form POST
@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if auth_response.user:
            return RedirectResponse("/dashboard", status_code=302)
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})
    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": str(e)})

# Turbidity dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        result = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(50).execute()
        data = result.data
    except Exception as e:
        data = []
        print("Supabase error:", e)

    return templates.TemplateResponse("dashboard.html", {"request": request, "data": data})
