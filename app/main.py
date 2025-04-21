from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objs as go
import os

app = FastAPI()

# Static and template setup
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# Supabase config
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin":
        request.session["user"] = username
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/", status_code=303)

    print("📡 Fetching data from Supabase...")
    response = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(1000).execute()

    if not response.data:
        print("⚠️ No data received from Supabase.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "no_data": True})

    df = pd.DataFrame(response.data)

    if 'sensor_id' not in df.columns:
        print("❌ Column 'sensor_id' not found in dataframe.")
        return templates.TemplateResponse("dashboard.html", {"request": request, "no_data": True})

    print(f"✅ DataFrame loaded: {len(df)} rows")

    sensor1 = df[df["sensor_id"] == "Sensor1"].sort_values("timestamp")
    sensor2 = df[df["sensor_id"] == "Sensor2"].sort_values("timestamp")

    print(f"📊 Sensor1: {len(sensor1)}, Sensor2: {len(sensor2)}")

    chart1 = go.Figure()
    chart1.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"], mode="lines", name="Sensor1 Raw", line=dict(color="orange")))
    chart1.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"], mode="lines", name="Sensor2 Raw", line=dict(color="white")))
    chart1.update_layout(title="Raw Data", paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e",
                         font=dict(color="white"), xaxis=dict(title="Time"), yaxis=dict(title="Raw Value"))

    chart2 = go.Figure()
    chart2.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"], mode="lines", name="Sensor1 Voltage", line=dict(color="orange")))
    chart2.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"], mode="lines", name="Sensor2 Voltage", line=dict(color="white")))
    chart2.update_layout(title="Voltage Data", paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e",
                         font=dict(color="white"), xaxis=dict(title="Time"), yaxis=dict(title="Voltage"))

    chart1_html = chart1.to_html(full_html=False)
    chart2_html = chart2.to_html(full_html=False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "chart1": chart1_html,
        "chart2": chart2_html
    })
