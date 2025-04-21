from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objs as go
import os
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        request.session["user"] = user.user.id
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})

@app.get("/dashboard")
async def dashboard(request: Request):
    print("📡 Fetching data from Supabase...")
    try:
        response = supabase.table("turbidity_data").select("*").execute()
        data = response.data
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return templates.TemplateResponse("dashboard.html", {"request": request, "charts": [], "error": str(e)})

    if not data:
        print("⚠️ No data received from Supabase.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "charts": [], "error": "No data found."})

    df = pd.DataFrame(data)
    print(f"✅ DataFrame loaded: {df.shape[0]} rows")

    if "sensor_id" not in df.columns:
        print("❌ 'sensor_id' column missing.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "charts": [], "error": "'sensor_id' column missing"})

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]
    print(f"📊 Sensor1: {len(sensor1)}, Sensor2: {len(sensor2)}")

    fig_raw = go.Figure()
    fig_raw.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], mode="lines", name="Sensor1", line=dict(color="orange")))
    fig_raw.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], mode="lines", name="Sensor2", line=dict(color="white")))
    fig_raw.update_layout(
        title="Raw Data",
        xaxis_title="Time",
        yaxis_title="Raw Value",
        plot_bgcolor="#222", paper_bgcolor="#222", font=dict(color="white"),
        hovermode="x unified",
    )

    fig_voltage = go.Figure()
    fig_voltage.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], mode="lines", name="Sensor1", line=dict(color="orange", dash="dot")))
    fig_voltage.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], mode="lines", name="Sensor2", line=dict(color="white", dash="dot")))
    fig_voltage.update_layout(
        title="Voltage",
        xaxis_title="Time",
        yaxis_title="Voltage (V)",
        plot_bgcolor="#222", paper_bgcolor="#222", font=dict(color="white"),
        hovermode="x unified",
    )

    chart1 = fig_raw.to_html(full_html=False, include_plotlyjs="cdn")
    chart2 = fig_voltage.to_html(full_html=False, include_plotlyjs=False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "charts": [chart1, chart2],
        "error": None
    })
