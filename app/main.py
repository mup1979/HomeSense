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
app.add_middleware(SessionMiddleware, secret_key="super-secret")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

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

    try:
        response = supabase.table("turbidity_data").select("*").limit(500).execute()
        data = response.data
    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": f"Error loading data from Supabase: {str(e)}"
        })

    if not data:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": "No data available"
        })

    df = pd.DataFrame(data)

    if "sensor_id" not in df.columns or "raw_value" not in df.columns or "voltage" not in df.columns:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": "Missing required columns in database"
        })

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    sensor1 = df[df["sensor_id"] == "Sensor1"]
    sensor2 = df[df["sensor_id"] == "Sensor2"]

    # Plot raw_value
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], mode='lines+markers',
                              name="Sensor1", line=dict(color="orange")))
    fig1.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], mode='lines+markers',
                              name="Sensor2", line=dict(color="white")))
    fig1.update_layout(title="Raw Data", paper_bgcolor="#111", plot_bgcolor="#111", font_color="white")

    # Plot voltage
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], mode='lines+markers',
                              name="Sensor1", line=dict(color="orange", dash='dash')))
    fig2.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], mode='lines+markers',
                              name="Sensor2", line=dict(color="white", dash='dash')))
    fig2.update_layout(title="Voltage", paper_bgcolor="#111", plot_bgcolor="#111", font_color="white")

    plot1 = fig1.to_html(full_html=False)
    plot2 = fig2.to_html(full_html=False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "plot1": plot1,
        "plot2": plot2,
        "error": None
    })
