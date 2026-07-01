import os
import re

def update_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        if isinstance(old, re.Pattern):
            content = old.sub(new, content)
        else:
            content = content.replace(old, new)
            
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated {path}")

# 1. blood_inventory.py
blood_inv_path = r"C:\PROJECTS\BLOOP\app\models\blood_inventory.py"
blood_inv_replacements = [
    (r"    def __repr__(self):", """
    @property
    def fill_percentage(self):
        if self.max_capacity <= 0:
            return 0
        return min(100, int((self.current_units / self.max_capacity) * 100))

    @property
    def status(self):
        if self.current_units == 0:
            return 'CRITICAL'
        elif 1 <= self.current_units <= 5:
            return 'LOW'
        elif 6 <= self.current_units <= 15:
            return 'MODERATE'
        else:
            return 'HEALTHY'

    @property
    def badge_class(self):
        s = self.status
        if s == 'CRITICAL': return 'bg-danger text-white'
        if s == 'LOW': return 'bg-warning text-dark'
        if s == 'MODERATE': return 'bg-primary text-white'
        return 'bg-success text-white'

    def __repr__(self):""")
]
update_file(blood_inv_path, blood_inv_replacements)

# 2. admin/inventory.html
admin_inv_path = r"C:\PROJECTS\BLOOP\app\templates\admin\inventory.html"
admin_inv_repl = [
    (r"{% for item in global_risk.blood_groups %}", r"{% for item in whole_blood %}"),
    (r"{{ item.current_stock }} / {{ item.safety_stock }} Units", r"{{ item.current_units }} / {{ item.max_capacity }} Units"),
    (r"{% if item.risk_level in ['CRITICAL', 'OUT OF STOCK'] %}liquid-critical{% endif %}", r"{% if item.status == 'CRITICAL' %}liquid-critical{% endif %}"),
    (r"style=\"height: {{ item.fill_pct }}%;\"", r"style=\"height: {{ item.fill_percentage }}%;\""),
    (r"{% if item.risk_level == 'HEALTHY' %}", r"{% if item.status == 'HEALTHY' %}"),
    (r"{% elif item.risk_level in ['LOW', 'HIGH RISK'] %}", r"{% elif item.status == 'LOW' %}"),
    
    (r"{% if status_map[item.blood_type].risk_level == 'HEALTHY' %}", r"{% if item.status == 'HEALTHY' %}"),
    (r"{% elif status_map[item.blood_type].risk_level in ['LOW', 'HIGH RISK'] %}", r"{% elif item.status == 'LOW' %}"),
    
    (r"<span class=\"badge bg-warning bg-opacity-25 text-warning\">{{ status_map[item.blood_type].risk_level }}</span>", r"<span class=\"badge bg-warning bg-opacity-25 text-warning\">{{ item.status }}</span>"),
    (r"<span class=\"badge bg-danger bg-opacity-25 text-danger\">{{ status_map[item.blood_type].risk_level }}</span>", r"<span class=\"badge bg-danger bg-opacity-25 text-danger\">{{ item.status }}</span>")
]
update_file(admin_inv_path, admin_inv_repl)

# 3. staff/inventory.html
staff_inv_path = r"C:\PROJECTS\BLOOP\app\templates\staff\inventory.html"
staff_inv_repl = [
    (r"{% if status_map[item.blood_type].risk_level in ['CRITICAL', 'OUT OF STOCK'] %}bg-danger", r"{% if item.status == 'CRITICAL' %}bg-danger"),
    (r"{% elif status_map[item.blood_type].risk_level in ['LOW', 'HIGH RISK'] %}bg-warning text-dark", r"{% elif item.status == 'LOW' %}bg-warning text-dark"),
    (r"{{ status_map[item.blood_type].risk_level }}", r"{{ item.status }}")
]
update_file(staff_inv_path, staff_inv_repl)

# 4. admin/routes.py
admin_rt_path = r"C:\PROJECTS\BLOOP\app\admin\routes.py"
admin_rt_repl = [
    (re.compile(r"def inventory\(\):.*?return render_template\('admin/inventory.html', whole_blood=items, all_items=all_items, global_risk=global_risk, status_map=status_map\)", re.DOTALL),
     "def inventory():\n    items = BloodInventory.query.filter_by(component='Whole Blood').order_by(BloodInventory.blood_type).all()\n    all_items = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()\n    return render_template('admin/inventory.html', whole_blood=items, all_items=all_items)")
]
update_file(admin_rt_path, admin_rt_repl)

# 5. staff/routes.py
staff_rt_path = r"C:\PROJECTS\BLOOP\app\staff\routes.py"
staff_rt_repl = [
    (re.compile(r"def inventory\(\):.*?return render_template\('staff/inventory.html', global_risk=global_risk, recent_transactions=all_items, status_map=status_map\)", re.DOTALL),
     "def inventory():\n    all_items = BloodInventory.query.order_by(BloodInventory.last_updated.desc()).limit(20).all()\n    return render_template('staff/inventory.html', recent_transactions=all_items)")
]
update_file(staff_rt_path, staff_rt_repl)

# 6. Streamlit inventory.py
inv_py_path = r"C:\PROJECTS\BLOOP\app\inventory.py"
inv_py_repl = [
    (re.compile(r"    # Let's enrich the inventory DataFrame with AI-based status.*?    \]", re.DOTALL), 
     """    enriched_inventory = []
    
    for idx, row in inventory_df.iterrows():
        bt = row["blood_type"]
        curr_stock = row["current_stock"]
        max_cap = row["max_capacity"]
        
        fill_percent = min(100, int((curr_stock / max_cap) * 100)) if max_cap > 0 else 0
        
        if curr_stock == 0:
            status = 'CRITICAL'
        elif 1 <= curr_stock <= 5:
            status = 'LOW'
        elif 6 <= curr_stock <= 15:
            status = 'MODERATE'
        else:
            status = 'HEALTHY'
            
        enriched_inventory.append({
            "blood_type": bt,
            "current_stock": curr_stock,
            "max_capacity": max_cap,
            "fill_percent": fill_percent,
            "status": status,
            "risk_level": status
        })""")
]
update_file(inv_py_path, inv_py_repl)
