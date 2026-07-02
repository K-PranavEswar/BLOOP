import os

path = r'C:\PROJECTS\BLOOP\app\public\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_blood_avail = False
for line in lines:
    if line.startswith('@public_bp.route(\'/blood-availability\')'):
        in_blood_avail = True
        new_lines.append(line)
        new_lines.append('''def blood_availability():
    search = request.args.get('search', '').strip()
    
    query = BloodInventory.query

    if search:
        search = search.upper().replace('POS', '+').replace('NEG', '-').replace(' ', '+')
        query = query.filter(BloodInventory.blood_type.ilike(search))

    whole_blood_query = query.filter(BloodInventory.component == 'Whole Blood')
    platelets_query = query.filter(BloodInventory.component == 'Platelets')
    plasma_query = query.filter(BloodInventory.component == 'Plasma')

    # Temporary Debug Logging
    print(f"[DEBUG] Search term received: '{search}'")
    print(f"[DEBUG] SQL query (Whole Blood): {whole_blood_query.statement.compile(compile_kwargs={'literal_binds': True})}")
    
    whole_blood = whole_blood_query.all()
    platelets = platelets_query.all()
    plasma = plasma_query.all()
    
    print(f"[DEBUG] Component: Whole Blood -> Returned {len(whole_blood)} rows")
    print(f"[DEBUG] Component: Platelets -> Returned {len(platelets)} rows")
    print(f"[DEBUG] Component: Plasma -> Returned {len(plasma)} rows")
    
    return render_template('public/blood_availability.html', 
                          whole_blood=whole_blood,
                          platelets=platelets,
                          plasma=plasma,
                          search=search)
''')
    elif in_blood_avail:
        if line.startswith('@public_bp.route('):
            in_blood_avail = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Updated blood_availability with debug prints')
