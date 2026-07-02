path = r'C:\PROJECTS\BLOOP\app\templates\public\profile.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make blood_group disabled
content = content.replace('<select name="blood_group" class="form-select border-light shadow-none">', '<select name="blood_group" class="form-select border-light shadow-none bg-light text-muted" disabled>')
# Make gender disabled
content = content.replace('<select name="gender" class="form-select border-light shadow-none">', '<select name="gender" class="form-select border-light shadow-none bg-light text-muted" disabled>')
# Make state disabled
content = content.replace('<select name="state" class="form-select border-light shadow-none">', '<select name="state" class="form-select border-light shadow-none bg-light text-muted" disabled>')
# Make age disabled
content = content.replace('<input type="number" name="age" id="age_input" class="form-control" value="{{ current_user.age or \'\' }}" min="18" max="100">', '<input type="number" name="age" id="age_input" class="form-control bg-light text-muted" value="{{ current_user.age or \'\' }}" min="18" max="100" disabled readonly>')
# Make district disabled
content = content.replace('<input type="text" name="district" class="form-control" value="{{ current_user.district or \'\' }}">', '<input type="text" name="district" class="form-control bg-light text-muted" value="{{ current_user.district or \'\' }}" disabled readonly>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated profile.html')
