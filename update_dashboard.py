import os

path = r'C:\PROJECTS\BLOOP\app\templates\staff\dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Welcome Message
if 'Welcome, ' not in content:
    welcome_html = '''
<div class="mb-4">
    <h3 class="fw-bold text-dark mb-1">Welcome, {{ current_user.full_name or current_user.username }} 👋</h3>
    <p class="text-muted">Here's the latest overview of today's blood bank operations.</p>
</div>
'''
    content = content.replace('{% block content %}', '{% block content %}' + welcome_html)

# 2. Critical AI Analysis Heading Color
content = content.replace(
    '''<h4 class="fw-bold mb-0 d-flex align-items-center">
                            Critical AI Analysis''',
    '''<h4 class="fw-bold text-danger mb-0 d-flex align-items-center">
                            Critical AI Analysis'''
)

# 3 & 4. Quick Inventory Design
old_inventory_html = '''            <div class="row g-3">
                {% for item in global_risk.blood_groups %}
                <div class="col-3">
                    <div class="text-center p-2 rounded {% if item.risk_level in ['CRITICAL', 'OUT OF STOCK'] %}bg-danger bg-opacity-10 border border-danger border-opacity-25{% else %}bg-secondary bg-opacity-10{% endif %}">
                        <h6 class="mb-1 text-dark fw-bold">{{ item.blood_group }}</h6>
                        <span class="small {% if item.risk_level in ['CRITICAL', 'OUT OF STOCK'] %}text-danger{% elif item.risk_level in ['LOW', 'HIGH RISK'] %}text-warning{% else %}text-success{% endif %}">{{ item.current_stock }}</span>
                    </div>
                </div>
                {% endfor %}
            </div>'''

new_inventory_html = '''            <div class="row g-3">
                {% for item in global_risk.blood_groups %}
                {% set stock = item.current_stock %}
                {% if stock == 0 %}
                    {% set bg_class = 'bg-danger bg-opacity-10' %}
                    {% set text_class = 'text-danger' %}
                    {% set badge_text = '🔴 Critical' %}
                {% elif stock < 10 %}
                    {% set bg_class = 'bg-warning bg-opacity-10' %}
                    {% set text_class = 'text-warning' %}
                    {% set badge_text = '🟡 Low Stock' %}
                {% else %}
                    {% set bg_class = 'bg-success bg-opacity-10' %}
                    {% set text_class = 'text-success' %}
                    {% set badge_text = '🟢 Healthy' %}
                {% endif %}
                
                <div class="col-6 col-md-3">
                    <div class="text-center p-3 rounded {{ bg_class }}">
                        <h5 class="mb-2 text-dark fw-bold">{{ item.blood_group }}</h5>
                        <div class="mb-2 fw-semibold {{ text_class }}">{{ stock }} Units</div>
                        <span class="small fw-bold {{ text_class }}">{{ badge_text }}</span>
                    </div>
                </div>
                {% endfor %}
            </div>'''

content = content.replace(old_inventory_html, new_inventory_html)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Dashboard UI updated successfully.')
