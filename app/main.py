from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# Load .env
load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Home/login
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

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

# Dashboard with Plotly charts
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        response = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(200).execute()
        data = response.data[::-1]  # reverse to show oldest → newest
    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": "", "error": str(e)})

    # Split by sensor
    sensor1 = [d for d in data if d["sensor_id"] == "Sensor1"]
    sensor2 = [d for d in data if d["sensor_id"] == "Sensor2"]

    # Create subplots
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Raw Data", "Voltage"))

    # RAW VALUES
    fig.add_trace(go.Scatter(
        x=[d["timestamp"] for d in sensor1],
        y=[d["raw_value"] for d in sensor1],
        mode="lines+markers",
        name="Sensor1 Raw",
        line=dict(color="orange")
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[d["timestamp"] for d in sensor2],
        y=[d["raw_value"] for d in sensor2],
        mode="lines+markers",
        name="Sensor2 Raw",
        line=dict(color="black")
    ), row=1, col=1)

    # VOLTAGE
    fig.add_trace(go.Scatter(
        x=[d["timestamp"] for d in sensor1],
        y=[d["voltage"] for d in sensor1],
        mode="lines+markers",
        name="Sensor1 Voltage",
        line=dict(color="orange", dash="dot")
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=[d["timestamp"] for d in sensor2],
        y=[d["voltage"] for d in sensor2],
        mode="lines+markers",
        name="Sensor2 Voltage",
        line=dict(color="black", dash="dot")
    ), row=1, col=2)

    fig.update_layout(
        title="📊 Turbidity Sensor Dashboard",
        template="plotly_dark",
        height=500,
        showlegend=True
    )

    # Convert to HTML snippet
    plot_html = fig.to_html(full_html=False)

    return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": plot_html})
