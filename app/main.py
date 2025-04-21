from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.supabase import supabase
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if user:
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(key="user_email", value=email)
            return response
    except Exception as e:
        print("Login failed:", e)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    email = request.cookies.get("user_email")
    if not email:
        return RedirectResponse(url="/", status_code=302)

    data = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(100).execute()
    rows = data.data[::-1]
    df = pd.DataFrame(rows)

    if df.empty:
        return templates.TemplateResponse("dashboard.html", {"request": request, "graph": "<p>No data available.</p>"})

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Raw Data", "Voltage"),
        horizontal_spacing=0.2
    )

    # Raw values
    fig.add_trace(go.Scatter(
        x=df[df["sensor_id"] == "Sensor1"]["timestamp"],
        y=df[df["sensor_id"] == "Sensor1"]["raw_value"],
        mode="lines+markers",
        name="Sensor1 Raw",
        line=dict(color="white")
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df[df["sensor_id"] == "Sensor2"]["timestamp"],
        y=df[df["sensor_id"] == "Sensor2"]["raw_value"],
        mode="lines+markers",
        name="Sensor2 Raw",
        line=dict(color="orange")
    ), row=1, col=1)

    # Voltage values
    fig.add_trace(go.Scatter(
        x=df[df["sensor_id"] == "Sensor1"]["timestamp"],
        y=df[df["sensor_id"] == "Sensor1"]["voltage"],
        mode="lines+markers",
        name="Sensor1 Voltage",
        line=dict(color="white", dash="dot")
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=df[df["sensor_id"] == "Sensor2"]["timestamp"],
        y=df[df["sensor_id"] == "Sensor2"]["voltage"],
        mode="lines+markers",
        name="Sensor2 Voltage",
        line=dict(color="orange", dash="dot")
    ), row=1, col=2)

    fig.update_layout(
        template="plotly_dark",
        showlegend=True,
        height=500,
        autosize=True,
        margin=dict(t=40, b=40, l=40, r=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )

    graph_html = fig.to_html(full_html=False, config={"responsive": True})
    return templates.TemplateResponse("dashboard.html", {"request": request, "graph": graph_html})

@app.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})
