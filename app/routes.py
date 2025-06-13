from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session, make_response
from . import db
from .models import Customer, Installment, Loan
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo 
import csv
from . import mail
from functools import wraps
from sqlalchemy import or_
from io import BytesIO, StringIO
import csv

main = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated

# Simple hardcoded login
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'nick' and request.form['password'] == 'nick#1234':
            session['logged_in'] = True
            return redirect(url_for('main.dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.login'))

@main.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

IST = ZoneInfo("Asia/Kolkata")

@main.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        data = request.form
        phone = data['phone'].strip()

        # Check if customer already exists
        existing_customer = Customer.query.filter_by(phone=phone).first()
        if existing_customer:
            flash("Customer already exists. Please use 'Add Loan' for new loans.", "danger")
            return redirect(url_for('main.add_loan'))

        now_ist = datetime.now(IST)

        # Create new customer
        customer = Customer(
            name=data['name'],
            phone=phone,
            location=data['location'].lower()
        )
        db.session.add(customer)
        db.session.commit()

        # Create initial loan
        loan = Loan(
            customer_id=customer.id,
            loan_type=data['loan_type'],
            amount=int(data['amount']),
            weeks=int(data['weeks']),
            weekly_installment=int(data['weekly_installment']),
            date_given=now_ist
        )
        db.session.add(loan)
        db.session.commit()

        # Create installments
        for i in range(1, loan.weeks + 1):
            due = now_ist + timedelta(weeks=i)
            installment = Installment(
                loan_id=loan.id,
                week_number=i,
                due_date=due
            )
            db.session.add(installment)

        db.session.commit()

        flash("Customer registered and first loan created.", "success")
        return redirect(url_for('main.register'))

    return render_template('register.html')

@main.route('/delete', methods=['GET', 'POST'])
@login_required
def delete_page():
    customer = None
    loans = []

    if request.method == 'POST':
        phone = request.form.get('phone')
        customer = Customer.query.filter_by(phone=phone).first()

        if customer:
            loans = Loan.query.filter_by(customer_id=customer.id).all()
        else:
            flash("No Customer Found", "danger")

    return render_template('delete.html', customer=customer, loans=loans)

@main.route('/delete_customer', methods=['POST'])
@login_required
def delete_customer():
    phone = request.form.get('phone')
    customer = Customer.query.filter_by(phone=phone).first()

    if customer:
        for loan in customer.loans:
            Installment.query.filter_by(loan_id=loan.id).delete()
            db.session.delete(loan)
        db.session.delete(customer)
        db.session.commit()
        flash(f"Customer {customer.name} and all data deleted.", "success")
    else:
        flash("Customer not found.", "warning")

    return redirect(url_for('main.delete_page'))


@main.route('/delete_loans', methods=['POST'])
@login_required
def delete_loans():
    phone = request.form.get('phone')
    loan_ids = request.form.getlist('loan_ids')

    customer = Customer.query.filter_by(phone=phone).first()
    if customer and loan_ids:
        for loan_id in loan_ids:
            loan = Loan.query.filter_by(id=loan_id, customer_id=customer.id).first()
            if loan:
                Installment.query.filter_by(loan_id=loan.id).delete()
                db.session.delete(loan)

        db.session.commit()
        flash(f"Deleted {len(loan_ids)} loan(s) for {customer.name}.", "warning")
    else:
        flash("No loans selected or customer not found.", "warning")

    return redirect(url_for('main.delete_page'))



@main.route('/collection', methods=['GET', 'POST'])
@login_required
def collection():
    customer = None
    loans = []
    selected_loan = None
    installments = []

    if request.method == 'POST':
        # Fresh search
        search_term = request.form.get('search', '').strip()
        loan_id = None  # reset loan_id on fresh search
    else:
        # Navigating between loans or after mark_paid
        search_term = request.args.get('search', '').strip()
        loan_id = request.args.get('loan_id')

    if search_term:
        # Search by phone or name
        customer = Customer.query.filter(
            (Customer.phone == search_term) | or_(
        Customer.phone == search_term,
        Customer.name.ilike(search_term)
    )
        ).first()
        if customer:
            # Fetch all loans for the customer
            loans = Loan.query.filter_by(customer_id=customer.id).order_by(Loan.date_given.desc()).all()

            # If specific loan selected, fetch it
            if loan_id:
                selected_loan = Loan.query.filter_by(id=loan_id, customer_id=customer.id).first()
            elif loans:
                selected_loan = loans[0]  # Default to the most recent loan

            if selected_loan:
                installments = Installment.query.filter_by(loan_id=selected_loan.id).order_by(Installment.week_number).all()
        else:
            flash("Customer Not Found", "danger")

    return render_template(
        'collection.html',
        customer=customer,
        loans=loans,
        selected_loan=selected_loan,
        installments=[{
            'id': i.id,
            'week_number': i.week_number,
            'due_date': i.due_date.strftime('%Y-%m-%d'),
            'paid': i.paid,
            'paid_on': i.paid_on.strftime('%Y-%m-%d') if i.paid_on else None
        } for i in installments]
    )


@main.route('/add_loan', methods=['GET', 'POST'])
@login_required
def add_loan():
    customer = None

    if request.method == 'POST':
        phone = request.form.get('phone')
        customer = Customer.query.filter_by(phone=phone).first()

        if 'loan_submit' in request.form and customer:
            loan_type = request.form['loan_type']
            amount = int(request.form['amount'])
            weeks = int(request.form['weeks'])
            weekly_installment = int(request.form['weekly_installment'])
            now = datetime.now(IST)

            # Save loan
            loan = Loan(
                customer_id=customer.id,
                loan_type=loan_type,
                amount=amount,
                weeks=weeks,
                weekly_installment=weekly_installment,
                date_given=now
            )
            db.session.add(loan)
            db.session.commit()

            # Create installments
            for i in range(1, weeks + 1):
                due_date = now + timedelta(weeks=i)
                inst = Installment(
                    loan_id=loan.id,
                    week_number=i,
                    due_date=due_date
                )
                db.session.add(inst)

            db.session.commit()
            flash("New loan added successfully!", "success")
            return redirect(url_for('main.collection'))

    return render_template('add_loan.html', customer=customer)




@main.route('/loan/<int:loan_id>')
@login_required
def loan_details(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    installments = Installment.query.filter_by(loan_id=loan.id).order_by(Installment.week_number).all()
    return render_template('loan_details.html', loan=loan, installments=installments)


@main.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('q', '').lower()
    customers = Customer.query.all()
    results = []
    for cust in customers:
        query = query.replace("%", " ")
        print(query, cust.name)
        if query.casefold() == cust.name or query == cust.phone:
            installments = [{
                'week': ins.week_number,
                'paid': ins.paid,
                'date': ins.paid_on.strftime('%Y-%m-%d') if ins.paid_on else ''
            } for ins in cust.installments]
            results.append({
                'id': cust.id,
                'name': cust.name,
                'phone': cust.phone,
                'installments': installments
            })
    return {'results': results}

@main.route('/mark_paid/<int:installment_id>', methods=['POST'])
@login_required
def mark_paid(installment_id):
    installment = Installment.query.get_or_404(installment_id)
    installment.paid = True
    installment.paid_on = datetime.now(IST)
    db.session.commit()

    # Redirect back to collection page with current customer and loan
    loan = Loan.query.get(installment.loan_id)
    customer = Customer.query.get(loan.customer_id)
    return redirect(url_for('main.collection', search=customer.phone, loan_id=loan.id))


@main.route('/report')
@login_required
def report():
    locations = db.session.query(Customer.location).distinct().all()
    location_filter = request.args.get('location')
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    query = Customer.query
    if location_filter:
        query = query.filter_by(location=location_filter.lower())

    customers = query.all()
    preview_data = []
    name_phn, paid_counts, due_counts = [], [], []
    total_paid = 0
    total_due = 0

    for cust in customers:
        loans = Loan.query.filter_by(customer_id=cust.id)
        if from_date_str:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
            loans = loans.filter(Loan.date_given >= from_date)
        if to_date_str:
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
            loans = loans.filter(Loan.date_given <= to_date)

        for loan in loans:
            installments = Installment.query.filter_by(loan_id=loan.id).all()
            paid_weeks = sum(1 for i in installments if i.paid)
            due_weeks = loan.weeks - paid_weeks if loan.weeks else 0
            status = "paid" if paid_weeks == loan.weeks else "due"

            # Bar chart data
            name_phn.append(f"{cust.name}-{cust.phone}")
            paid_counts.append(paid_weeks)
            due_counts.append(due_weeks)
            total_paid += paid_weeks
            total_due += due_weeks

            # Preview data
            preview_data.append({
                'name': cust.name or 'N/A',
                'phone': cust.phone or 'N/A',
                'location': cust.location or 'N/A',
                'loan_type': loan.loan_type or 'N/A',
                'amount': loan.amount if loan.amount else 'N/A',
                'weeks': f"{paid_weeks}/{loan.weeks}" if loan.weeks else f"{paid_weeks}/0",
                'paid_weeks': paid_weeks,
                'due_weeks': due_weeks,
                'status': status,
                'date_given': loan.date_given.strftime('%Y-%m-%d') if loan.date_given else 'N/A'
            })

    chart_data = {
        'name_phn': name_phn,
        'paid': paid_counts,
        'due': due_counts,
        'total_paid': total_paid,
        'total_due': total_due
    }

    return render_template(
        'report.html',
        report=preview_data,
        chart_data=chart_data,
        locations=[loc[0] for loc in locations if loc[0]]
    )

@main.route('/export_csv', methods=['GET'])
@login_required
def export_csv():
    location_filter = request.args.get('location')
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    query = Customer.query
    if location_filter:
        query = query.filter_by(location=location_filter)

    customers = query.all()

    csv_text = StringIO()
    writer = csv.writer(csv_text)
    writer.writerow(["Customer Name", "Phone", "Location", "Loan Type", "Amount", "Weeks", "Paid Weeks", "Due Weeks", "Status", "Date Given"])

    for cust in customers:
        loans = Loan.query.filter_by(customer_id=cust.id)

        if from_date_str:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
            loans = loans.filter(Loan.date_given >= from_date)
        if to_date_str:
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
            loans = loans.filter(Loan.date_given <= to_date)

        for loan in loans:
            installments = Installment.query.filter_by(loan_id=loan.id).all()
            paid_weeks = sum(1 for i in installments if i.paid)
            due_weeks = loan.weeks - paid_weeks
            status = "paid" if paid_weeks == loan.weeks else "due"

            writer.writerow([
                cust.name,
                cust.phone,
                cust.location,
                loan.loan_type,
                loan.amount,
                loan.weeks,
                paid_weeks,
                due_weeks,
                status,
                loan.date_given.strftime('%Y-%m-%d')
            ])

    mem = BytesIO()
    mem.write(csv_text.getvalue().encode('utf-8'))
    mem.seek(0)
    csv_text.close()

    response = make_response(mem.read())
    response.headers['Content-Disposition'] = 'attachment; filename=customer_loans_report.csv'
    response.mimetype = 'text/csv'
    return response


