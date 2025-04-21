from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.supabase import supabase
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import os

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if not user.user:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
        return RedirectResponse(url="/dashboard", status_code=302)
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        # Fetch turbidity data
        result = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(100).execute()
        df = pd.DataFrame(result.data)

        if df.empty:
            return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": "<p>No data available.</p>"})

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

        # Split data by sensor
        sensor1 = df[df["sensor_id"] == "Sensor1"]
        sensor2 = df[df["sensor_id"] == "Sensor2"]

        # Plotly dual charts
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Raw Data", "Voltage"))

        fig.add_trace(go.Scatter(
            x=sensor1["timestamp"], y=sensor1["raw_value"],
            mode="lines+markers", name="Sensor1 Raw",
            line=dict(color="white")
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=sensor2["timestamp"], y=sensor2["raw_value"],
            mode="lines+markers", name="Sensor2 Raw",
            line=dict(color="orange")
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=sensor1["timestamp"], y=sensor1["voltage"],
            mode="lines+markers", name="Sensor1 Voltage",
            line=dict(color="white", dash="dot")
        ), row=1, col=2)

        fig.add_trace(go.Scatter(
            x=sensor2["timestamp"], y=sensor2["voltage"],
            mode="lines+markers", name="Sensor2 Voltage",
            line=dict(color="orange", dash="dot")
        ), row=1, col=2)

        fig.update_layout(
            template="plotly_dark",
            height=500,
            margin=dict(t=40, l=20, r=20, b=20),
            paper_bgcolor="#1e1e1e",
            plot_bgcolor="#1e1e1e"
        )

        plot_html = fig.to_html(full_html=False)
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": plot_html})

    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": f"<p>Error: {e}</p>"})

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    try:
        result = supabase.table("device_config").select("*").execute()
        df = pd.DataFrame(result.data)
        return templates.TemplateResponse("config.html", {"request": request, "config": df.to_dict(orient="records")})
    except Exception as e:
        return templates.TemplateResponse("config.html", {"request": request, "error": str(e)})
