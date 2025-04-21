import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objs as go
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user and user.user:
            request.session["user"] = user.user.id
            request.session["site"] = "SiteA"
            return RedirectResponse(url="/dashboard", status_code=303)
    except Exception:
        pass
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=303)

    site = request.session.get("site", "SiteA")

    print("📡 Fetching data from Supabase...")
    response = supabase.table("turbidity_data").select("*").eq("site", site).order("timestamp", desc=True).limit(1000).execute()
    data = response.data

    if not data:
        print("⚠️ No data received from Supabase.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "chart1": None, "chart2": None})

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    print(f"✅ DataFrame loaded: {len(df)} rows")

    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]

    print(f"📊 Sensor1: {len(sensor1)}, Sensor2: {len(sensor2)}")

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"],
                              mode='lines+markers', name="Sensor1 Raw", line=dict(color='white')))
    fig1.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"],
                              mode='lines+markers', name="Sensor2 Raw", line=dict(color='orange')))
    fig1.update_layout(
        paper_bgcolor='rgb(20,20,20)',
        plot_bgcolor='rgb(20,20,20)',
        font=dict(color='white'),
        margin=dict(l=20, r=20, t=40, b=20),
        height=400
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"],
                              mode='lines+markers', name="Sensor1 Voltage", line=dict(color='white', dash='dot')))
    fig2.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"],
                              mode='lines+markers', name="Sensor2 Voltage", line=dict(color='orange', dash='dot')))
    fig2.update_layout(
        paper_bgcolor='rgb(20,20,20)',
        plot_bgcolor='rgb(20,20,20)',
        font=dict(color='white'),
        margin=dict(l=20, r=20, t=40, b=20),
        height=400
    )

    chart1 = fig1.to_html(full_html=False, default_height=400)
    chart2 = fig2.to_html(full_html=False, default_height=400)

    return templates.TemplateResponse("dashboard.html", {"request": request, "chart1": chart1, "chart2": chart2})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})
