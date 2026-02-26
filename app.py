from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import calendar

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finances.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'amount': self.amount
        }


class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'in' or 'out'
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=True)
    budget = db.relationship('Budget', backref='transactions')
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=True)
    vendor = db.relationship('Vendor', backref='transactions')
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'budget_id': self.budget_id,
            'budget_name': self.budget.name if self.budget else None,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.name if self.vendor else None,
            'date': self.date.isoformat()
        }


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # 'monthly', 'yearly'
    billing_day = db.Column(db.Integer, nullable=False)  # day of month (1-28)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=True)
    budget = db.relationship('Budget')
    active = db.Column(db.Boolean, default=True)
    last_charged = db.Column(db.Date, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'amount': self.amount,
            'frequency': self.frequency,
            'billing_day': self.billing_day,
            'budget_id': self.budget_id,
            'budget_name': self.budget.name if self.budget else None,
            'active': self.active,
            'last_charged': self.last_charged.isoformat() if self.last_charged else None
        }

    def get_next_billing_date(self):
        today = date.today()
        if self.last_charged:
            if self.frequency == 'monthly':
                next_date = self.last_charged + relativedelta(months=1)
            else:  # yearly
                next_date = self.last_charged + relativedelta(years=1)
        else:
            # Never charged, calculate first billing date
            next_date = date(today.year, today.month, min(self.billing_day, 28))
            if next_date < today:
                next_date = next_date + relativedelta(months=1)
        return next_date


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # 'monthly', 'yearly'
    pay_day = db.Column(db.Integer, nullable=False)  # day of month (1-28)
    active = db.Column(db.Boolean, default=True)
    last_paid = db.Column(db.Date, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'amount': self.amount,
            'frequency': self.frequency,
            'pay_day': self.pay_day,
            'active': self.active,
            'last_paid': self.last_paid.isoformat() if self.last_paid else None
        }

    def get_next_pay_date(self):
        today = date.today()
        if self.last_paid:
            if self.frequency == 'monthly':
                next_date = self.last_paid + relativedelta(months=1)
            else:  # yearly
                next_date = self.last_paid + relativedelta(years=1)
        else:
            # Never paid, calculate first pay date
            next_date = date(today.year, today.month, min(self.pay_day, 28))
            if next_date < today:
                next_date = next_date + relativedelta(months=1)
        return next_date


class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=True)  # Null for general savings (no goal)
    is_general = db.Column(db.Boolean, default=False)  # True for general savings account
    color = db.Column(db.String(7), default='#667eea')  # Hex color for display
    interest_rate = db.Column(db.Float, default=0)  # Annual interest rate as percentage (e.g. 6.95)
    last_interest_date = db.Column(db.Date, nullable=True)  # Last date interest was calculated

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'is_general': self.is_general,
            'color': self.color,
            'interest_rate': self.interest_rate,
            'last_interest_date': self.last_interest_date.isoformat() if self.last_interest_date else None
        }


class SavingsTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    savings_goal_id = db.Column(db.Integer, db.ForeignKey('savings_goal.id'), nullable=False)
    savings_goal = db.relationship('SavingsGoal', backref='transactions')
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'deposit' or 'withdraw'
    description = db.Column(db.String(200), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'savings_goal_id': self.savings_goal_id,
            'savings_goal_name': self.savings_goal.name if self.savings_goal else None,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'date': self.date.isoformat()
        }


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions"""
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return jsonify([t.to_dict() for t in transactions])


@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    """Add a new transaction"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['description', 'amount', 'transaction_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    if data['transaction_type'] not in ['in', 'out']:
        return jsonify({'error': 'transaction_type must be "in" or "out"'}), 400
    
    transaction = Transaction(
        description=data['description'],
        amount=float(data['amount']),
        transaction_type=data['transaction_type'],
        budget_id=data.get('budget_id'),
        vendor_id=data.get('vendor_id'),
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.utcnow()
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify(transaction.to_dict()), 201


@app.route('/api/transactions/<int:id>', methods=['DELETE'])
def delete_transaction(id):
    """Delete a transaction"""
    transaction = Transaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'message': 'Transaction deleted'}), 200


@app.route('/api/transactions/<int:id>', methods=['PUT'])
def update_transaction(id):
    """Update a transaction"""
    transaction = Transaction.query.get_or_404(id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'description' in data:
        transaction.description = data['description']
    if 'amount' in data:
        transaction.amount = float(data['amount'])
    if 'transaction_type' in data:
        transaction.transaction_type = data['transaction_type']
    if 'budget_id' in data:
        transaction.budget_id = data['budget_id'] if data['budget_id'] else None
    if 'vendor_id' in data:
        transaction.vendor_id = data['vendor_id'] if data['vendor_id'] else None
    if 'date' in data:
        transaction.date = datetime.fromisoformat(data['date'])
    
    db.session.commit()
    return jsonify(transaction.to_dict()), 200


@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Get current balance"""
    transactions = Transaction.query.all()
    balance = sum(
        t.amount if t.transaction_type == 'in' else -t.amount
        for t in transactions
    )
    return jsonify({'balance': balance})


@app.route('/api/budgets', methods=['GET'])
def get_budgets():
    """Get all budgets"""
    budgets = Budget.query.order_by(Budget.name).all()
    return jsonify([b.to_dict() for b in budgets])


@app.route('/api/budgets', methods=['POST'])
def add_budget():
    """Add a new budget"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'name' not in data or 'amount' not in data:
        return jsonify({'error': 'Missing required fields: name, amount'}), 400
    
    budget = Budget(
        name=data['name'],
        amount=float(data['amount'])
    )
    
    db.session.add(budget)
    db.session.commit()
    
    return jsonify(budget.to_dict()), 201


@app.route('/api/budgets/<int:id>', methods=['PUT'])
def update_budget(id):
    """Update a budget"""
    budget = Budget.query.get_or_404(id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'amount' in data:
        budget.amount = float(data['amount'])
    if 'name' in data:
        budget.name = data['name']
    
    db.session.commit()
    return jsonify(budget.to_dict()), 200


@app.route('/api/budgets/<int:id>', methods=['DELETE'])
def delete_budget(id):
    """Delete a budget"""
    budget = Budget.query.get_or_404(id)
    db.session.delete(budget)
    db.session.commit()
    return jsonify({'message': 'Budget deleted'}), 200


@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors"""
    vendors = Vendor.query.order_by(Vendor.name).all()
    return jsonify([v.to_dict() for v in vendors])


@app.route('/api/vendors', methods=['POST'])
def add_vendor():
    """Add a new vendor"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing required field: name'}), 400
    
    # Check if vendor already exists
    existing = Vendor.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify(existing.to_dict()), 200
    
    vendor = Vendor(name=data['name'])
    db.session.add(vendor)
    db.session.commit()
    
    return jsonify(vendor.to_dict()), 201


@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    """Get all subscriptions"""
    subscriptions = Subscription.query.order_by(Subscription.name).all()
    return jsonify([s.to_dict() for s in subscriptions])


@app.route('/api/subscriptions', methods=['POST'])
def add_subscription():
    """Add a new subscription"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['name', 'amount', 'frequency', 'billing_day']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    subscription = Subscription(
        name=data['name'],
        amount=float(data['amount']),
        frequency=data['frequency'],
        billing_day=int(data['billing_day']),
        budget_id=data.get('budget_id'),
        active=True
    )
    
    db.session.add(subscription)
    db.session.commit()
    
    return jsonify(subscription.to_dict()), 201


@app.route('/api/subscriptions/<int:id>', methods=['DELETE'])
def delete_subscription(id):
    """Delete a subscription"""
    subscription = Subscription.query.get_or_404(id)
    db.session.delete(subscription)
    db.session.commit()
    return jsonify({'message': 'Subscription deleted'}), 200


@app.route('/api/subscriptions/<int:id>/toggle', methods=['POST'])
def toggle_subscription(id):
    """Toggle subscription active status"""
    subscription = Subscription.query.get_or_404(id)
    subscription.active = not subscription.active
    db.session.commit()
    return jsonify(subscription.to_dict()), 200


@app.route('/api/incomes', methods=['GET'])
def get_incomes():
    """Get all incomes"""
    incomes = Income.query.order_by(Income.name).all()
    return jsonify([i.to_dict() for i in incomes])


@app.route('/api/incomes', methods=['POST'])
def add_income():
    """Add a new income"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['name', 'amount', 'frequency', 'pay_day']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    income = Income(
        name=data['name'],
        amount=float(data['amount']),
        frequency=data['frequency'],
        pay_day=int(data['pay_day']),
        active=True
    )
    
    db.session.add(income)
    db.session.commit()
    
    return jsonify(income.to_dict()), 201


@app.route('/api/incomes/<int:id>', methods=['DELETE'])
def delete_income(id):
    """Delete an income"""
    income = Income.query.get_or_404(id)
    db.session.delete(income)
    db.session.commit()
    return jsonify({'message': 'Income deleted'}), 200


@app.route('/api/incomes/<int:id>/toggle', methods=['POST'])
def toggle_income(id):
    """Toggle income active status"""
    income = Income.query.get_or_404(id)
    income.active = not income.active
    db.session.commit()
    return jsonify(income.to_dict()), 200


# Savings Goals endpoints
@app.route('/api/savings-goals', methods=['GET'])
def get_savings_goals():
    """Get all savings goals"""
    goals = SavingsGoal.query.all()
    result = []
    for g in goals:
        goal_dict = g.to_dict()
        # Calculate current balance
        balance = sum(
            t.amount if t.transaction_type == 'deposit' else -t.amount
            for t in g.transactions
        )
        goal_dict['balance'] = balance
        result.append(goal_dict)
    return jsonify(result)


@app.route('/api/savings-goals', methods=['POST'])
def add_savings_goal():
    """Add a new savings goal"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing required field: name'}), 400
    
    goal = SavingsGoal(
        name=data['name'],
        target_amount=float(data['target_amount']) if data.get('target_amount') else None,
        is_general=data.get('is_general', False),
        color=data.get('color', '#667eea'),
        interest_rate=float(data.get('interest_rate', 0))
    )
    
    db.session.add(goal)
    db.session.commit()
    
    return jsonify(goal.to_dict()), 201


@app.route('/api/savings-goals/<int:id>', methods=['PUT'])
def update_savings_goal(id):
    """Update a savings goal"""
    goal = SavingsGoal.query.get_or_404(id)
    data = request.get_json()
    
    if 'name' in data:
        goal.name = data['name']
    if 'target_amount' in data:
        goal.target_amount = float(data['target_amount']) if data['target_amount'] else None
    if 'color' in data:
        goal.color = data['color']
    if 'interest_rate' in data:
        goal.interest_rate = float(data['interest_rate'])
    
    db.session.commit()
    return jsonify(goal.to_dict()), 200


@app.route('/api/savings-goals/<int:id>', methods=['DELETE'])
def delete_savings_goal(id):
    """Delete a savings goal"""
    goal = SavingsGoal.query.get_or_404(id)
    # Delete related transactions first
    SavingsTransaction.query.filter_by(savings_goal_id=id).delete()
    db.session.delete(goal)
    db.session.commit()
    return jsonify({'message': 'Savings goal deleted'}), 200


@app.route('/api/savings-goals/<int:id>/apply-interest', methods=['POST'])
def apply_interest_manually(id):
    """Manually apply interest to a savings goal"""
    goal = SavingsGoal.query.get_or_404(id)
    
    if goal.interest_rate <= 0:
        return jsonify({'error': 'This savings goal has no interest rate set'}), 400
    
    # Calculate current balance
    balance = sum(
        t.amount if t.transaction_type == 'deposit' else -t.amount
        for t in goal.transactions
    )
    
    if balance <= 0:
        return jsonify({'error': 'Balance must be positive to apply interest'}), 400
    
    # Calculate interest
    monthly_rate = goal.interest_rate / 100
    interest_amount = round(balance * monthly_rate, 2)
    
    if interest_amount <= 0:
        return jsonify({'error': 'Interest amount is too small'}), 400
    
    # Create interest transaction
    interest_trans = SavingsTransaction(
        savings_goal_id=goal.id,
        amount=interest_amount,
        transaction_type='deposit',
        description=f'Manual Interest ({goal.interest_rate}% on R{balance:.2f})',
        date=datetime.utcnow()
    )
    db.session.add(interest_trans)
    db.session.commit()
    
    return jsonify({
        'message': f'Interest of R{interest_amount:.2f} applied successfully',
        'interest_amount': interest_amount,
        'new_balance': balance + interest_amount
    }), 200


# Savings Transactions endpoints
@app.route('/api/savings-transactions', methods=['GET'])
def get_savings_transactions():
    """Get all savings transactions"""
    transactions = SavingsTransaction.query.order_by(SavingsTransaction.date.desc()).all()
    return jsonify([t.to_dict() for t in transactions])


@app.route('/api/savings-transactions', methods=['POST'])
def add_savings_transaction():
    """Add a new savings transaction"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['savings_goal_id', 'amount', 'transaction_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    if data['transaction_type'] not in ['deposit', 'withdraw']:
        return jsonify({'error': 'transaction_type must be "deposit" or "withdraw"'}), 400
    
    transaction = SavingsTransaction(
        savings_goal_id=int(data['savings_goal_id']),
        amount=float(data['amount']),
        transaction_type=data['transaction_type'],
        description=data.get('description', ''),
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.utcnow()
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify(transaction.to_dict()), 201


@app.route('/api/savings-transactions/<int:id>', methods=['DELETE'])
def delete_savings_transaction(id):
    """Delete a savings transaction"""
    transaction = SavingsTransaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'message': 'Savings transaction deleted'}), 200


def process_subscriptions():
    """Process due subscriptions and create transactions"""
    today = date.today()
    subscriptions = Subscription.query.filter_by(active=True).all()
    
    for sub in subscriptions:
        next_billing = sub.get_next_billing_date()
        
        # Create transactions for any billing dates that have passed
        while next_billing <= today:
            transaction = Transaction(
                description=f'{sub.name} subscription',
                amount=sub.amount,
                transaction_type='out',
                budget_id=sub.budget_id,
                date=datetime.combine(next_billing, datetime.min.time())
            )
            db.session.add(transaction)
            sub.last_charged = next_billing
            
            # Calculate next billing date
            if sub.frequency == 'monthly':
                next_billing = next_billing + relativedelta(months=1)
            else:  # yearly
                next_billing = next_billing + relativedelta(years=1)
        
        db.session.commit()


def process_income():
    """Process due income and create transactions"""
    today = date.today()
    incomes = Income.query.filter_by(active=True).all()
    
    for inc in incomes:
        next_pay = inc.get_next_pay_date()
        
        # Create transactions for any pay dates that have passed
        while next_pay <= today:
            transaction = Transaction(
                description=f'{inc.name}',
                amount=inc.amount,
                transaction_type='in',
                date=datetime.combine(next_pay, datetime.min.time())
            )
            db.session.add(transaction)
            inc.last_paid = next_pay
            
            # Calculate next pay date
            if inc.frequency == 'monthly':
                next_pay = next_pay + relativedelta(months=1)
            else:  # yearly
                next_pay = next_pay + relativedelta(years=1)
        
        db.session.commit()


def process_interest():
    """Process monthly interest for savings goals"""
    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    
    savings_goals = SavingsGoal.query.filter(SavingsGoal.interest_rate > 0).all()
    
    for goal in savings_goals:
        # Determine the starting point for interest calculation
        if goal.last_interest_date:
            # Start from the month after last interest was applied
            check_date = goal.last_interest_date + relativedelta(months=1)
            check_date = date(check_date.year, check_date.month, 1)
        else:
            # Find the first transaction date for this goal
            first_trans = SavingsTransaction.query.filter_by(
                savings_goal_id=goal.id
            ).order_by(SavingsTransaction.date.asc()).first()
            
            if not first_trans:
                continue  # No transactions, skip
            
            # Start from the month after first transaction
            first_trans_date = first_trans.date.date() if isinstance(first_trans.date, datetime) else first_trans.date
            check_date = first_trans_date + relativedelta(months=1)
            check_date = date(check_date.year, check_date.month, 1)
        
        # Apply interest for each month up to (but not including) current month
        while check_date < first_of_month:
            # Calculate balance at end of previous month
            end_of_prev_month = check_date - relativedelta(days=1)
            transactions = SavingsTransaction.query.filter(
                SavingsTransaction.savings_goal_id == goal.id,
                SavingsTransaction.date <= datetime.combine(end_of_prev_month, datetime.max.time())
            ).all()
            
            balance = sum(
                t.amount if t.transaction_type == 'deposit' else -t.amount
                for t in transactions
            )
            
            if balance > 0:
                # Calculate monthly interest (rate is already monthly)
                monthly_rate = goal.interest_rate / 100
                interest_amount = round(balance * monthly_rate, 2)
                
                if interest_amount > 0:
                    # Create interest transaction
                    interest_trans = SavingsTransaction(
                        savings_goal_id=goal.id,
                        amount=interest_amount,
                        transaction_type='deposit',
                        description=f'Interest ({goal.interest_rate}% p.m.)',
                        date=datetime.combine(check_date, datetime.min.time())
                    )
                    db.session.add(interest_trans)
            
            goal.last_interest_date = end_of_prev_month
            check_date = check_date + relativedelta(months=1)
        
        db.session.commit()


@app.route('/')
def index():
    """Redirect to transactions page"""
    return redirect(url_for('transactions_page'))


def get_common_data():
    """Get common data used across all pages"""
    # Process any due subscriptions, income, and interest
    process_subscriptions()
    process_income()
    process_interest()
    
    # Get month/year from query params or use current
    year = request.args.get('year', type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    
    # Calculate first and last day of selected month
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1)
    else:
        last_day = date(year, month + 1, 1)
    
    # Filter transactions by selected month
    transactions = Transaction.query.filter(
        Transaction.date >= first_day,
        Transaction.date < last_day
    ).order_by(Transaction.date.desc()).all()
    
    # Calculate carry-forward balance (all transactions BEFORE selected month)
    previous_transactions = Transaction.query.filter(
        Transaction.date < first_day
    ).all()
    carry_forward = sum(
        t.amount if t.transaction_type == 'in' else -t.amount
        for t in previous_transactions
    )
    
    # Calculate balance for selected month only
    month_balance = sum(
        t.amount if t.transaction_type == 'in' else -t.amount
        for t in transactions
    )
    
    # Total balance is carry forward + this month
    balance = carry_forward + month_balance
    
    # Format month name for display
    month_name = calendar.month_name[month]
    
    return {
        'selected_year': year,
        'selected_month': month,
        'month_name': month_name,
        'balance': balance,
        'carry_forward': carry_forward,
        'month_balance': month_balance,
        'first_day': first_day,
        'last_day': last_day,
        'transactions': transactions
    }


@app.route('/transactions')
def transactions_page():
    """Render the transactions page"""
    common = get_common_data()
    budgets = Budget.query.order_by(Budget.name).all()
    vendors = Vendor.query.order_by(Vendor.name).all()
    
    return render_template('transactions.html',
        active_page='transactions',
        transactions=common['transactions'],
        budgets=budgets,
        vendors=vendors,
        **{k: v for k, v in common.items() if k not in ['transactions', 'first_day', 'last_day']}
    )


@app.route('/budgets')
def budgets_page():
    """Render the budgets page"""
    common = get_common_data()
    budgets = Budget.query.order_by(Budget.name).all()
    incomes = Income.query.order_by(Income.name).all()
    
    # Calculate spent per budget for selected month
    budget_spending = {}
    for b in budgets:
        spent = sum(t.amount for t in common['transactions'] if t.budget_id == b.id and t.transaction_type == 'out')
        budget_spending[b.id] = spent
    
    # Calculate total income and total budgets for unallocated funds
    total_income = sum(i.amount for i in incomes)
    total_budgets = sum(b.amount for b in budgets)
    unallocated = total_income - total_budgets
    
    return render_template('budgets.html',
        active_page='budgets',
        budgets=budgets,
        budget_spending=budget_spending,
        total_income=total_income,
        total_budgets=total_budgets,
        unallocated=unallocated,
        **{k: v for k, v in common.items() if k not in ['transactions', 'first_day', 'last_day']}
    )


@app.route('/subscriptions')
def subscriptions_page():
    """Render the subscriptions page"""
    common = get_common_data()
    budgets = Budget.query.order_by(Budget.name).all()
    subscriptions = Subscription.query.order_by(Subscription.name).all()
    
    return render_template('subscriptions.html',
        active_page='subscriptions',
        subscriptions=subscriptions,
        budgets=budgets,
        **{k: v for k, v in common.items() if k not in ['transactions', 'first_day', 'last_day']}
    )


@app.route('/income')
def income_page():
    """Render the income page"""
    common = get_common_data()
    incomes = Income.query.order_by(Income.name).all()
    
    return render_template('income.html',
        active_page='income',
        incomes=incomes,
        **{k: v for k, v in common.items() if k not in ['transactions', 'first_day', 'last_day']}
    )


@app.route('/savings')
def savings_page():
    """Render the savings page"""
    common = get_common_data()
    
    # Get savings goals with balances
    savings_goals = SavingsGoal.query.all()
    savings_with_balance = []
    total_savings = 0
    for g in savings_goals:
        balance_amount = sum(
            t.amount if t.transaction_type == 'deposit' else -t.amount
            for t in g.transactions
        )
        total_savings += balance_amount
        savings_with_balance.append({
            'goal': g,
            'balance': balance_amount
        })
    
    # Get all savings transactions with pagination
    savings_page_num = request.args.get('savings_page', type=int, default=1)
    per_page = 10
    savings_transactions_query = SavingsTransaction.query.order_by(SavingsTransaction.date.desc())
    total_savings_transactions = savings_transactions_query.count()
    savings_transactions = savings_transactions_query.offset((savings_page_num - 1) * per_page).limit(per_page).all()
    total_savings_pages = (total_savings_transactions + per_page - 1) // per_page  # Ceiling division
    
    return render_template('savings.html',
        active_page='savings',
        savings_goals=savings_with_balance,
        savings_transactions=savings_transactions,
        total_savings=total_savings,
        savings_page=savings_page_num,
        total_savings_pages=total_savings_pages,
        **{k: v for k, v in common.items() if k not in ['transactions', 'first_day', 'last_day']}
    )


# Initialize database tables
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
