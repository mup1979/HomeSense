import os
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objs as go
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    request.session["user"] = username
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    response = supabase.table("turbidity_data").select("*").limit(1000).execute()
    data = response.data

    if not data:
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": ""})

    df = pd.DataFrame(data)

    if "timestamp" not in df.columns or "sensor_id" not in df.columns:
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": ""})

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    last_day = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
    df = df[df["timestamp"] >= last_day]

    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]

    fig_raw = go.Figure()
    fig_raw.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"],
                                 mode="lines", name="Sensor1 Raw", line=dict(color="orange")))
    fig_raw.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"],
                                 mode="lines", name="Sensor2 Raw", line=dict(color="white")))
    fig_raw.update_layout(template="plotly_dark", height=400, margin=dict(l=40, r=40, t=40, b=40))

    fig_voltage = go.Figure()
    fig_voltage.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"],
                                     mode="lines", name="Sensor1 Voltage", line=dict(color="orange", dash="dash")))
    fig_voltage.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"],
                                     mode="lines", name="Sensor2 Voltage", line=dict(color="white", dash="dash")))
    fig_voltage.update_layout(template="plotly_dark", height=400, margin=dict(l=40, r=40, t=40, b=40))

    plot_html = fig_raw.to_html(full_html=False) + fig_voltage.to_html(full_html=False)
    return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": plot_html})

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    sensor_types = ["turbidity", "temperature", "pm"]
    device_id = "RP1"
    config_data = []

    for sensor_type in sensor_types:
        response = supabase.table("device_config") \
            .select("interval_sec, enabled") \
            .eq("device_id", device_id) \
            .eq("sensor_type", sensor_type) \
            .execute()

        if response.data:
            entry = response.data[0]
            entry["sensor_type"] = sensor_type
            config_data.append(entry)
        else:
            config_data.append({
                "sensor_type": sensor_type,
                "interval_sec": 300,
                "enabled": False
            })

    return templates.TemplateResponse("config.html", {
        "request": request,
        "config_data": config_data
    })

@app.post("/update_config", response_class=HTMLResponse)
async def update_config(
    request: Request,
    sensor_type: str = Form(...),
    interval_sec: int = Form(...),
    enabled: str = Form(...)
):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    device_id = "RP1"
    enabled_bool = enabled.lower() == "true"

    supabase.table("device_config").upsert({
        "device_id": device_id,
        "sensor_type": sensor_type,
        "interval_sec": interval_sec,
        "enabled": enabled_bool
    }).execute()

    return RedirectResponse(url="/config", status_code=status.HTTP_303_SEE_OTHER)
