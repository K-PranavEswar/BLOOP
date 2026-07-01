from app import create_app
from app.models.blood_inventory import BloodInventory

app = create_app()

test_cases = [66, 57, 23, 22, 7, 6, 4, 1, 0]

with app.app_context():
    for stock in test_cases:
        item = BloodInventory(current_units=stock)
        print(f"{stock} Units -> {item.status}")
