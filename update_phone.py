import re
import os

files_changed = []

# 1. Update app/auth/forms.py
path = r'C:\PROJECTS\BLOOP\app\auth\forms.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
content = content.replace(
    '''from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError''',
    '''from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError, Regexp'''
)
content = content.replace(
    '''phone = StringField('Phone', validators=[Optional(), Length(max=20)])''',
    '''phone = StringField('Phone', validators=[Optional(), Regexp(r'^\\d{10}$', message='Phone number must be exactly 10 digits.')])'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/auth/forms.py')


# 2. Update app/public/routes.py
path = r'C:\PROJECTS\BLOOP\app\public\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
if 'import re' not in content:
    content = 'import re\n' + content

content = content.replace(
    '''        # Phone Validation
        if phone and len(phone) < 10:
            flash('Phone number must be at least 10 digits.', 'danger')
            return redirect(url_for('public.profile'))''',
    '''        # Phone Validation
        if phone and not re.match(r'^\\d{10}$', phone):
            flash('Phone number must be exactly 10 digits.', 'danger')
            return redirect(url_for('public.profile'))'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/public/routes.py')


# 3. Update app/staff/routes.py
path = r'C:\PROJECTS\BLOOP\app\staff\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
if 'import re' not in content:
    content = 'import re\n' + content

content = content.replace(
    '''        phone = request.form.get('phone')''',
    '''        phone = request.form.get('phone')
        if phone and not re.match(r'^\\d{10}$', phone):
            flash('Phone number must be exactly 10 digits.', 'danger')
            return redirect(url_for('staff.donors'))'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/staff/routes.py')


# 4. Update app/templates/auth/register.html
path = r'C:\PROJECTS\BLOOP\app\templates\auth\register.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
content = content.replace(
    '''{{ form.phone(class="form-control", placeholder="+91 9876543210") }}''',
    '''{{ form.phone(class="form-control", placeholder="9876543210", maxlength="10", minlength="10", pattern="[0-9]{10}", inputmode="numeric", type="tel", oninput="this.value = this.value.replace(/[^0-9]/g, '').slice(0, 10);") }}'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/templates/auth/register.html')


# 5. Update app/templates/public/profile.html
path = r'C:\PROJECTS\BLOOP\app\templates\public\profile.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
content = content.replace(
    '''<input type="tel" name="phone" id="phone_input" class="form-control border-start-0 ps-0" value="{{ current_user.phone or '' }}" pattern="[0-9]{10,15}">''',
    '''<input type="tel" name="phone" id="phone_input" class="form-control border-start-0 ps-0" value="{{ current_user.phone or '' }}" pattern="[0-9]{10}" maxlength="10" minlength="10" inputmode="numeric" oninput="this.value = this.value.replace(/[^0-9]/g, '').slice(0, 10);">'''
)
content = content.replace(
    '''<div class="invalid-feedback" id="phoneError">Enter a valid 10-15 digit phone number.</div>''',
    '''<div class="invalid-feedback" id="phoneError">Enter a valid 10-digit phone number.</div>'''
)
content = content.replace(
    '''if (phone && !/^[0-9]{10,15}$/.test(phone)) {''',
    '''if (phone && !/^[0-9]{10}$/.test(phone)) {'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/templates/public/profile.html')


# 6. Update app/templates/staff/donors.html
path = r'C:\PROJECTS\BLOOP\app\templates\staff\donors.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

orig_content = content
content = content.replace(
    '''<input type="text" name="phone" class="form-control" required>''',
    '''<input type="tel" name="phone" class="form-control" required maxlength="10" minlength="10" pattern="[0-9]{10}" inputmode="numeric" oninput="this.value = this.value.replace(/[^0-9]/g, '').slice(0, 10);">'''
)
if content != orig_content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_changed.append('app/templates/staff/donors.html')

print('Files changed:', files_changed)
