from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.services.supabase import supabase, get_user_role

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        auth_id = user.user.id
        role = get_user_role(auth_id)

        if not role:
            return templates.TemplateResponse("login.html", {"request": request, "error": "❌ Not authorized."})

        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie("email", email)
        response.set_cookie("auth_id", auth_id)
        response.set_cookie("role", role)
        return response

    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": f"Login failed: {e}"})

@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/config")
def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})
