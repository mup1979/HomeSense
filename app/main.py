from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

# Supabase config
url = "https://YOUR_PROJECT_ID.supabase.co"
key = "YOUR_SUPABASE_SERVICE_ROLE_KEY"
supabase: Client = create_client(url, key)

# Static and template folders
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def is_authenticated(request: Request):
    return request.session.get("user") is not None

@app.get("/", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user:
            request.session["user"] = dict(user.user)
            return RedirectResponse(url="/dashboard", status_code=302)
    except Exception as e:
        print(f"Login failed: {e}")
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)

    try:
        data = supabase.table("turbidity_data").select("*").execute()
        df = pd.DataFrame(data.data)

        if df.empty:
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "plot_raw": "<p>No data available</p>",
                "plot_voltage": "<p>No data available</p>"
            })

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        sensor1 = df[df["sensor_id"] == "Sensor1"]
        sensor2 = df[df["sensor_id"] == "Sensor2"]

        # Raw chart
        fig_raw = go.Figure()
        fig_raw.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"],
                                     mode="lines+markers", name="Sensor1 Raw", line=dict(color="white")))
        fig_raw.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"],
                                     mode="lines+markers", name="Sensor2 Raw", line=dict(color="orange")))
        fig_raw.update_layout(
            paper_bgcolor="#161616",
            plot_bgcolor="#161616",
            font=dict(color="white"),
            margin=dict(l=20, r=20, t=30, b=20),
            height=400,
            hovermode="x unified"
        )
        plot_raw = pio.to_html(fig_raw, full_html=False)

        # Voltage chart
        fig_voltage = go.Figure()
        fig_voltage.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"],
                                         mode="lines+markers", name="Sensor1 Voltage", line=dict(color="white", dash="dot")))
        fig_voltage.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"],
                                         mode="lines+markers", name="Sensor2 Voltage", line=dict(color="orange", dash="dot")))
        fig_voltage.update_layout(
            paper_bgcolor="#161616",
            plot_bgcolor="#161616",
            font=dict(color="white"),
            margin=dict(l=20, r=20, t=30, b=20),
            height=400,
            hovermode="x unified"
        )
        plot_voltage = pio.to_html(fig_voltage, full_html=False)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot_raw": plot_raw,
            "plot_voltage": plot_voltage
        })

    except Exception as e:
        print("Error loading dashboard:", e)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot_raw": "<p>Error loading data</p>",
            "plot_voltage": "<p>Error loading data</p>"
        })
