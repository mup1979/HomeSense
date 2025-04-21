from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- LOGIN PAGE ---
@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user:
            return RedirectResponse(url="/dashboard", status_code=303)
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})


# --- DASHBOARD PAGE ---
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        data = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(100).execute()
        df = pd.DataFrame(data.data)

        if df.empty or "sensor_id" not in df.columns:
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "raw_chart": "No data available",
                "voltage_chart": "No data available"
            })

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        sensor1 = df[df["sensor_id"] == "Sensor1"]
        sensor2 = df[df["sensor_id"] == "Sensor2"]

        # --- Raw Data Chart ---
        fig_raw = go.Figure()
        fig_raw.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], mode="lines+markers",
                                     name="Sensor1 Raw", line=dict(color="white")))
        fig_raw.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], mode="lines+markers",
                                     name="Sensor2 Raw", line=dict(color="orange")))

        fig_raw.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=400,
            hovermode="x unified"
        )

        # --- Voltage Chart ---
        fig_voltage = go.Figure()
        fig_voltage.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], mode="lines+markers",
                                         name="Sensor1 Voltage", line=dict(color="white", dash="dot")))
        fig_voltage.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], mode="lines+markers",
                                         name="Sensor2 Voltage", line=dict(color="orange", dash="dot")))

        fig_voltage.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=400,
            hovermode="x unified"
        )

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "raw_chart": fig_raw.to_html(include_plotlyjs="cdn", full_html=False),
            "voltage_chart": fig_voltage.to_html(include_plotlyjs=False, full_html=False)
        })

    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "raw_chart": "Error loading data",
            "voltage_chart": str(e)
        })
