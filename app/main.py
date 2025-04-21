from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
from dotenv import load_dotenv
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
import os

# Use headless backend for rendering charts
matplotlib.use("Agg")

# Load environment
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

# Home page (login)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Handle login
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

# Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        result = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(50).execute()
        data = result.data
    except Exception as e:
        data = []
        print("Supabase error:", e)

    return templates.TemplateResponse("dashboard.html", {"request": request, "data": data})

# Chart image route
@app.get("/chart")
async def chart():
    try:
        result = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(50).execute()
        data = result.data
    except Exception as e:
        print("Chart data error:", e)
        return Response(content="Error loading chart", media_type="text/plain")

    # Prepare data (reverse for chronological order)
    timestamps = [row["timestamp"] for row in data][::-1]
    values = [row["raw_value"] for row in data][::-1]

    # Plot to image
    fig, ax = plt.subplots()
    ax.plot(timestamps, values, marker='o', linestyle='-')
    ax.set_title("Turbidity Over Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Raw Value")
    fig.autofmt_xdate()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return Response(content=buf.read(), media_type="image/png")
