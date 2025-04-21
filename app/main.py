import os
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objs as go
from plotly.utils import PlotlyJSONEncoder
import json

# Load .env
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user:
            request.session["user"] = dict(user.user)
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        pass
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    print("📡 Fetching data from Supabase...")
    try:
        response = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(1000).execute()
        data = response.data
        df = pd.DataFrame(data)

        if df.empty:
            print("⚠️ No data received from Supabase.")
            return templates.TemplateResponse("dashboard.html", {"request": request, "raw_chart_json": "{}", "voltage_chart_json": "{}"})

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Split sensors
        sensor1 = df[df["sensor_id"] == "Sensor1"]
        sensor2 = df[df["sensor_id"] == "Sensor2"]
        print(f"✅ DataFrame loaded: {len(df)} rows")
        print(f"📊 Sensor1: {len(sensor1)}, Sensor2: {len(sensor2)}")

        # --- Raw chart ---
        raw_fig = go.Figure()
        raw_fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"],
                                     mode="lines", name="Sensor1 Raw", line=dict(color="orange")))
        raw_fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"],
                                     mode="lines", name="Sensor2 Raw", line=dict(color="white")))
        raw_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#161616", plot_bgcolor="#161616",
                              font=dict(color="white"), height=400)

        # --- Voltage chart ---
        voltage_fig = go.Figure()
        voltage_fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"],
                                         mode="lines", name="Sensor1 Voltage", line=dict(color="orange", dash="dash")))
        voltage_fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"],
                                         mode="lines", name="Sensor2 Voltage", line=dict(color="white", dash="dash")))
        voltage_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#161616", plot_bgcolor="#161616",
                                  font=dict(color="white"), height=400)

        raw_chart_json = json.dumps(raw_fig, cls=PlotlyJSONEncoder)
        voltage_chart_json = json.dumps(voltage_fig, cls=PlotlyJSONEncoder)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "raw_chart_json": raw_chart_json,
            "voltage_chart_json": voltage_chart_json
        })

    except Exception as e:
        print("❌ Error fetching data:", e)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "raw_chart_json": "{}", "voltage_chart_json": "{}"
        })

@app.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("config.html", {"request": request})
