from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objs as go
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Auth Dependency
def get_user(request: Request):
    return request.session.get("user")

# Routes
@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        request.session = {"user": user}
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    response = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(100).execute()
    rows = response.data[::-1]  # reverse to chronological order

    # Debug output
    print("Fetched rows:", rows)

    if not rows:
        return templates.TemplateResponse("dashboard.html", {"request": request, "charts": None})

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Extract data
    sensor1 = df[df["sensor"] == "Sensor1"]
    sensor2 = df[df["sensor"] == "Sensor2"]

    # Debug print
    print("Sensor1:", sensor1)
    print("Sensor2:", sensor2)

    # Raw Data Plot
    fig_raw = go.Figure()
    fig_raw.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["value"], mode='lines+markers', name="Sensor1 Raw", line=dict(color='white')))
    fig_raw.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["value"], mode='lines+markers', name="Sensor2 Raw", line=dict(color='orange')))
    fig_raw.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'))

    # Voltage Chart (assuming value / 6000 gives voltage)
    fig_voltage = go.Figure()
    fig_voltage.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["value"] / 6000, mode='lines+markers', name="Sensor1 Voltage", line=dict(color='white', dash='dot')))
    fig_voltage.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["value"] / 6000, mode='lines+markers', name="Sensor2 Voltage", line=dict(color='orange', dash='dot')))
    fig_voltage.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'))

    raw_html = fig_raw.to_html(full_html=False, include_plotlyjs='cdn')
    voltage_html = fig_voltage.to_html(full_html=False, include_plotlyjs=False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "raw_chart": raw_html,
        "voltage_chart": voltage_html
    })
