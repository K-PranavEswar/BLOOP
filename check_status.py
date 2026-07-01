from app import create_app
from app.services.ai_risk_engine import calculate_global_risk

app = create_app()
app.app_context().push()
risk = calculate_global_risk()

for item in risk['blood_groups']:
    print(f"{item['blood_group']}: stock={item['current_stock']} demand={item['predicted_demand']} remaining={item['expected_remaining']} score={item['risk_score']} status={item['risk_level']}")
