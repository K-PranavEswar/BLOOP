import os
import re

# 1. Update app/public/routes.py
routes_path = r'C:\PROJECTS\BLOOP\app\public\routes.py'
with open(routes_path, 'r', encoding='utf-8') as f:
    routes_content = f.read()

# I will rewrite the `profile()` function entirely using a regex replacement to ensure it is correct.
# Wait, replacing the whole function is safer.
profile_func = '''@public_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        gender = request.form.get('gender')
        district = request.form.get('district')
        state = request.form.get('state')
        address = request.form.get('address')
        
        # Phone Validation
        if phone and not re.match(r'^\\d{10}$', phone):
            flash('Phone number must be exactly 10 digits.', 'danger')
            return redirect(url_for('public.profile'))
        
        # Profile Photo
        photo_file = request.files.get('profile_photo')
        if photo_file and photo_file.filename != '':
            # Validate format
            allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
            if '.' not in photo_file.filename or photo_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                flash('Invalid image format. Only JPG, JPEG, PNG, and WEBP are allowed.', 'danger')
                return redirect(url_for('public.profile'))
                
            # Validate size (Max 2MB)
            photo_file.seek(0, os.SEEK_END)
            size = photo_file.tell()
            photo_file.seek(0)
            if size > 2 * 1024 * 1024:
                flash('File too large. Maximum size is 2 MB.', 'danger')
                return redirect(url_for('public.profile'))
                
            try:
                ext = photo_file.filename.rsplit('.', 1)[1].lower()
                timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"user_{current_user.id}_{timestamp}.{ext}"
                
                folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profile')
                os.makedirs(folder, exist_ok=True)
                filepath = os.path.join(folder, filename)
                
                # Delete old photo if exists
                if current_user.profile_photo:
                    old_file = current_user.profile_photo.split('/')[-1] if '/' in current_user.profile_photo else current_user.profile_photo
                    old_path = os.path.join(folder, old_file)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            print(f"[WARNING] Could not delete old photo: {e}")
                
                photo_file.save(filepath)
                # Save only the filename to the database as requested
                current_user.profile_photo = filename
                
                print(f"[UPLOAD]\\nUser: {current_user.username.upper()}\\nImage Saved: {filename}")
                flash('Profile photo updated successfully.', 'success')
            except Exception as e:
                print(f"[ERROR] Upload failed: {e}")
                flash('Upload failed due to a server error.', 'danger')
                return redirect(url_for('public.profile'))
            
        if full_name:
            current_user.full_name = full_name
        current_user.phone = phone
        current_user.gender = gender
        current_user.district = district
        current_user.state = state
        current_user.address = address
        
        db.session.commit()
        log_activity(current_user.id, 'Updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('public.profile'))
        
    from app.utils.helpers import INDIAN_STATES, BLOOD_GROUPS
    return render_template('public/profile.html', indian_states=INDIAN_STATES, blood_groups=BLOOD_GROUPS)'''

# Replace everything from @public_bp.route('/profile' to the next route or end of file
new_routes_content = re.sub(
    r'@public_bp\.route\(\'/profile\', methods=\[\'GET\', \'POST\'\]\).*?def profile\(\):.*?return render_template\(\'public/profile\.html\'.*?\)',
    profile_func,
    routes_content,
    flags=re.DOTALL
)

with open(routes_path, 'w', encoding='utf-8') as f:
    f.write(new_routes_content)

# 2. Update app/templates/public/profile.html
html_path = r'C:\PROJECTS\BLOOP\app\templates\public\profile.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Fix image paths
html_content = html_content.replace("uploads/profile_photos/", "uploads/profile/")
# Fix accept property
html_content = html_content.replace('accept="image/jpeg, image/png, image/jpg"', 'accept="image/jpeg, image/png, image/jpg, image/webp"')

# Re-enable gender, state, district
# I will just replace ` disabled>` with `>` for gender and state, and ` disabled readonly>` with `>` for district.
# But wait, gender was: `<select name="gender" class="form-select border-light shadow-none bg-light text-muted" disabled>`
html_content = html_content.replace('<select name="gender" class="form-select border-light shadow-none bg-light text-muted" disabled>', '<select name="gender" class="form-select border-light shadow-none">')
html_content = html_content.replace('<select name="state" class="form-select border-light shadow-none bg-light text-muted" disabled>', '<select name="state" class="form-select border-light shadow-none">')
html_content = html_content.replace('<input type="text" name="district" class="form-control bg-light text-muted" value="{{ current_user.district or \'\' }}" disabled readonly>', '<input type="text" name="district" class="form-control" value="{{ current_user.district or \'\' }}">')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Upgrade complete!")
