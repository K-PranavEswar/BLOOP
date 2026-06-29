"""
Inventory service – manages blood stock levels.
"""
from datetime import datetime
from app.extensions import db
from app.models.blood_inventory import BloodInventory
from app.utils.helpers import log_activity

BLOOD_TYPES = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-']
COMPONENTS = ['Whole Blood', 'Platelets', 'Plasma']


def seed_inventory_from_csv():
    """Seed inventory from existing CSV if database is empty."""
    import os, csv
    if BloodInventory.query.count() > 0:
        return

    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            'dataset', 'inventory.csv')
    if not os.path.exists(csv_path):
        _seed_default_inventory()
        return

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for component in COMPONENTS:
                factor = 1.0 if component == 'Whole Blood' else (0.3 if component == 'Platelets' else 0.2)
                inv = BloodInventory(
                    blood_type=row['blood_type'],
                    component=component,
                    current_units=int(float(row['current_stock']) * factor),
                    max_capacity=int(float(row['max_capacity']) * factor),
                    safety_stock=int(float(row['safety_stock']) * factor)
                )
                db.session.add(inv)
    db.session.commit()


def _seed_default_inventory():
    """Create default inventory entries."""
    defaults = {
        'O+': (52, 154, 64), 'A+': (54, 121, 50), 'B+': (22, 62, 26), 'AB+': (7, 17, 7),
        'O-': (23, 45, 19), 'A-': (3, 9, 3), 'B-': (1, 4, 1), 'AB-': (1, 3, 1)
    }
    for bt, (stock, cap, safety) in defaults.items():
        for component in COMPONENTS:
            factor = 1.0 if component == 'Whole Blood' else (0.3 if component == 'Platelets' else 0.2)
            inv = BloodInventory(
                blood_type=bt, component=component,
                current_units=int(stock * factor), max_capacity=int(cap * factor),
                safety_stock=int(safety * factor)
            )
            db.session.add(inv)
    db.session.commit()


def get_all_inventory():
    """Get all inventory records."""
    return BloodInventory.query.order_by(BloodInventory.blood_type).all()


def get_inventory_by_type(blood_type, component='Whole Blood'):
    """Get inventory for a specific blood type and component."""
    return BloodInventory.query.filter_by(blood_type=blood_type, component=component).first()


def get_inventory_summary():
    """Get summary of whole blood inventory for dashboard cards."""
    items = BloodInventory.query.filter_by(component='Whole Blood').all()
    summary = []
    for item in items:
        summary.append({
            'blood_type': item.blood_type,
            'current_units': item.current_units,
            'max_capacity': item.max_capacity,
            'safety_stock': item.safety_stock,
            'fill_percentage': item.fill_percentage,
            'status': item.status
        })
    return summary


def update_stock(blood_type, component, units, transaction_type, user_id=None):
    """
    Update blood stock. transaction_type: 'receive' or 'issue'.
    Returns (success, message).
    """
    inv = BloodInventory.query.filter_by(blood_type=blood_type, component=component).first()
    if not inv:
        return False, 'Blood type/component not found.'

    if transaction_type == 'receive':
        new_val = min(inv.max_capacity, inv.current_units + units)
        inv.current_units = new_val
        action = f'Received {units} units of {blood_type} ({component})'
    elif transaction_type == 'issue':
        if inv.current_units < units:
            return False, f'Insufficient stock. Available: {inv.current_units} units.'
        inv.current_units -= units
        action = f'Issued {units} units of {blood_type} ({component})'
    else:
        return False, 'Invalid transaction type.'

    inv.last_updated = datetime.utcnow()
    db.session.commit()

    if user_id:
        log_activity(user_id, action)

    return True, action


def get_low_stock_alerts():
    """Return list of blood types below safety threshold."""
    items = BloodInventory.query.filter_by(component='Whole Blood').all()
    alerts = []
    for item in items:
        if item.status in ('CRITICAL', 'LOW'):
            alerts.append({
                'blood_type': item.blood_type,
                'current_units': item.current_units,
                'safety_stock': item.safety_stock,
                'status': item.status,
                'deficit': max(0, item.safety_stock - item.current_units)
            })
    return alerts


def get_total_stock():
    """Get total units across all whole blood inventory."""
    items = BloodInventory.query.filter_by(component='Whole Blood').all()
    return sum(item.current_units for item in items)
