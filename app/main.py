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

    print("📡 Fetching data from Supabase...")
    response = supabase.table("turbidity_data").select("*").limit(1000).execute()
    data = response.data

    if not data:
        print("⚠️ No data received from Supabase.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": ""})

    df = pd.DataFrame(data)
    print(f"✅ DataFrame loaded: {len(df)} rows")

    if "sensor_id" not in df.columns:
        print("❌ 'sensor_id' column not found in data.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": ""})

    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]
    print(f"📊 Sensor1: {len(sensor1)}, Sensor2: {len(sensor2)}")

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], mode="lines", name="Sensor1 Raw", line=dict(color="orange")))
    fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], mode="lines", name="Sensor2 Raw", line=dict(color="white")))
    fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], mode="lines", name="Sensor1 Voltage", line=dict(color="orange", dash="dash")))
    fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], mode="lines", name="Sensor2 Voltage", line=dict(color="white", dash="dash")))

    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40),
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    plot_html = fig.to_html(full_html=False)
    return templates.TemplateResponse("dashboard.html", {"request": request, "plot_html": plot_html})
