from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os
import pandas as pd
import plotly.graph_objs as go
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if user.user:
        request.session["user"] = user.user.email
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard")
def dashboard(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=302)

    # Fetch turbidity data
    response = supabase.table("turbidity_data").select("*").execute()
    data = response.data

    if not data:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": "No data found in Supabase"
        })

    df = pd.DataFrame(data)

    if "sensor_id" not in df.columns:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": "Missing 'sensor_id' column in data"
        })

    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]

    # Chart 1: Raw data
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], name="Sensor1", line=dict(color="orange")))
    fig1.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], name="Sensor2", line=dict(color="white")))
    fig1.update_layout(title="Raw Values", plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))

    # Chart 2: Voltage
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], name="Sensor1", line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], name="Sensor2", line=dict(color="white")))
    fig2.update_layout(title="Voltage", plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))

    plot1 = fig1.to_html(full_html=False)
    plot2 = fig2.to_html(full_html=False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "plot1": plot1,
        "plot2": plot2,
        "error": None
    })
