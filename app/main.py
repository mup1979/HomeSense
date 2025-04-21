from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client
import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Middleware
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET_KEY", "supersecret"))

# Static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Supabase config
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if not user or not user.user:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials."})
        request.session["user"] = user.user.id
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        print("❌ Login Error:", e)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Authentication failed."})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    try:
        print("📡 Fetching data from Supabase...")
        response = supabase.table("turbidity_data").select("*").order("timestamp", desc=True).limit(200).execute()

        if not response or not response.data:
            print("⚠️ No data received from Supabase.")
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "plot1": "",
                "plot2": "",
                "error": "No data returned from Supabase"
            })

        print("✅ Supabase returned data")

        df = pd.DataFrame(response.data)
        print("📊 Raw DataFrame:\n", df.head())
        print("📋 Columns:", df.columns.tolist())

        if "sensor_id" not in df.columns:
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "plot1": "",
                "plot2": "",
                "error": "Missing 'sensor_id' column in data"
            })

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        sensor1 = df[df["sensor_id"] == "Sensor1"]
        sensor2 = df[df["sensor_id"] == "Sensor2"]

        print(f"📈 Sensor1 records: {len(sensor1)}")
        print(f"📈 Sensor2 records: {len(sensor2)}")

        fig = make_subplots(rows=1, cols=2, subplot_titles=("Raw Data", "Voltage"))

        # Raw Data Plot
        fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["raw_value"],
                                 mode="lines+markers", name="Sensor1 Raw", line=dict(color="orange")), row=1, col=1)
        fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["raw_value"],
                                 mode="lines+markers", name="Sensor2 Raw", line=dict(color="white")), row=1, col=1)

        # Voltage Plot
        fig.add_trace(go.Scatter(x=sensor1["timestamp"], y=sensor1["voltage"],
                                 mode="lines+markers", name="Sensor1 Voltage", line=dict(color="orange", dash="dot")), row=1, col=2)
        fig.add_trace(go.Scatter(x=sensor2["timestamp"], y=sensor2["voltage"],
                                 mode="lines+markers", name="Sensor2 Voltage", line=dict(color="white", dash="dot")), row=1, col=2)

        fig.update_layout(template="plotly_dark", height=500, width=1200, showlegend=True)
        plot_html = fig.to_html(full_html=False)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": plot_html,
            "plot2": "",
            "error": ""
        })

    except Exception as e:
        print("🔥 Dashboard Error:", e)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "plot1": "",
            "plot2": "",
            "error": f"Dashboard error: {str(e)}"
        })
