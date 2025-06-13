from . import db
from datetime import datetime

# models.py

# models.py

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20), unique=True)
    location = db.Column(db.String(100))
    loans = db.relationship('Loan', backref='customer', lazy=True, cascade="all, delete-orphan")

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    loan_type = db.Column(db.String(50))
    amount = db.Column(db.Integer)
    weeks = db.Column(db.Integer)
    weekly_installment = db.Column(db.Integer)
    date_given = db.Column(db.Date)
    installments = db.relationship('Installment', backref='loan', lazy=True, cascade="all, delete-orphan")

class Installment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    week_number = db.Column(db.Integer)
    due_date = db.Column(db.DateTime)
    paid = db.Column(db.Boolean, default=False)
    paid_on = db.Column(db.DateTime, nullable=True)
