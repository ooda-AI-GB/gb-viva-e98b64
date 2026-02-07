from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta

import database as db
import auth

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

db.init_db()

def get_current_user(request: Request):
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None
    username = auth.get_username_from_cookie(session_cookie)
    if not username:
        return None
    return auth.get_user(username)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = auth.get_user(username)
    if user and auth.verify_password(password, user["password_hash"]):
        response = RedirectResponse(url="/dashboard", status_code=303)
        session_cookie = auth.create_session_cookie(username)
        response.set_cookie(key="session", value=session_cookie, httponly=True)
        return response
    return RedirectResponse(url="/?error=1", status_code=303)

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user: dict = Depends(get_current_user), db_session: Session = Depends(db.get_db)):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    today = date.today()
    start_of_month = today.replace(day=1)

    query = db_session.query(db.Expense)
    if current_user['role'] == 'employee':
        query = query.filter(db.Expense.username == list(auth.USERS.keys())[list(auth.USERS.values()).index(current_user)])


    total_this_month = query.filter(db.Expense.date >= start_of_month).with_entities(func.sum(db.Expense.amount)).scalar() or 0
    pending_approvals = query.filter(db.Expense.status == db.ExpenseStatus.PENDING).count()
    approved_total = query.filter(db.Expense.status == db.ExpenseStatus.APPROVED).with_entities(func.sum(db.Expense.amount)).scalar() or 0
    rejected_total = query.filter(db.Expense.status == db.ExpenseStatus.REJECTED).with_entities(func.sum(db.Expense.amount)).scalar() or 0

    # Monthly trend data
    monthly_totals = {}
    for i in range(6, -1, -1):
        month_date = today - timedelta(days=i*30)
        month_key = month_date.strftime("%b %Y")
        start_of_trend_month = month_date.replace(day=1)
        end_of_trend_month = (start_of_trend_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        
        month_total = query.filter(
            db.Expense.date >= start_of_trend_month,
            db.Expense.date <= end_of_trend_month,
            db.Expense.status == db.ExpenseStatus.APPROVED
        ).with_entities(func.sum(db.Expense.amount)).scalar() or 0
        monthly_totals[month_key] = month_total
    
    max_total = max(monthly_totals.values()) if monthly_totals else 0

    context = {
        "request": request,
        "user": current_user,
        "total_this_month": f"{total_this_month:,.2f}",
        "pending_approvals": pending_approvals,
        "approved_total": f"{approved_total:,.2f}",
        "rejected_total": f"{rejected_total:,.2f}",
        "monthly_totals": monthly_totals,
        "max_total": max_total
    }
    return templates.TemplateResponse("dashboard.html", context)

@app.get("/my-expenses", response_class=HTMLResponse)
def my_expenses(request: Request, current_user: dict = Depends(get_current_user), db_session: Session = Depends(db.get_db)):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)
    
    username = list(auth.USERS.keys())[list(auth.USERS.values()).index(current_user)]
    expenses = db_session.query(db.Expense).filter(db.Expense.username == username).order_by(db.Expense.date.desc()).all()
    
    context = {"request": request, "user": current_user, "expenses": expenses}
    return templates.TemplateResponse("my_expenses.html", context)

@app.get("/submit", response_class=HTMLResponse)
def submit_expense_form(request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user['role'] != 'employee':
        return RedirectResponse(url="/dashboard", status_code=303)
    context = {"request": request, "user": current_user, "categories": list(db.ExpenseCategory)}
    return templates.TemplateResponse("submit_expense.html", context)

@app.post("/submit")
async def submit_expense(
    request: Request,
    amount: float = Form(...),
    category: db.ExpenseCategory = Form(...),
    expense_date: date = Form(...),
    description: str = Form(...),
    receipt_reference: str = Form(None),
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(db.get_db)
):
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    username = list(auth.USERS.keys())[list(auth.USERS.values()).index(current_user)]
    new_expense = db.Expense(
        username=username,
        amount=amount,
        category=category,
        date=expense_date,
        description=description,
        receipt_reference=receipt_reference,
        status=db.ExpenseStatus.PENDING
    )
    db_session.add(new_expense)
    db_session.commit()
    return RedirectResponse(url="/my-expenses", status_code=303)

@app.get("/approvals", response_class=HTMLResponse)
def approvals(request: Request, current_user: dict = Depends(get_current_user), db_session: Session = Depends(db.get_db)):
    if not current_user or current_user['role'] != 'finance_manager':
        return RedirectResponse(url="/dashboard", status_code=303)
    
    pending_expenses = db_session.query(db.Expense).filter(db.Expense.status == db.ExpenseStatus.PENDING).order_by(db.Expense.date).all()
    context = {"request": request, "user": current_user, "expenses": pending_expenses}
    return templates.TemplateResponse("approvals.html", context)

@app.post("/approve/{expense_id}")
def approve_expense(expense_id: int, current_user: dict = Depends(get_current_user), db_session: Session = Depends(db.get_db)):
    if not current_user or current_user['role'] != 'finance_manager':
        raise HTTPException(status_code=403, detail="Not authorized")
    
    expense = db_session.query(db.Expense).filter(db.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    expense.status = db.ExpenseStatus.APPROVED
    db_session.commit()
    return RedirectResponse(url="/approvals", status_code=303)

@app.post("/reject/{expense_id}")
def reject_expense(expense_id: int, current_user: dict = Depends(get_current_user), db_session: Session = Depends(db.get_db)):
    if not current_user or current_user['role'] != 'finance_manager':
        raise HTTPException(status_code=403, detail="Not authorized")
        
    expense = db_session.query(db.Expense).filter(db.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
        
    expense.status = db.ExpenseStatus.REJECTED

    db_session.commit()
    return RedirectResponse(url="/approvals", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
