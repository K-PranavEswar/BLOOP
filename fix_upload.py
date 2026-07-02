import os

# 1. Update routes.py
path = r'C:\PROJECTS\BLOOP\app\staff\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("request.files.get('profile_photo')", "request.files.get('photo')")
content = content.replace("{'png', 'jpg', 'jpeg'}", "{'png', 'jpg', 'jpeg', 'webp'}")
content = content.replace("'uploads', 'profile_photos'", "'uploads', 'profile'")
content = content.replace("profile_photo = request.files.get('photo')", "photo = request.files.get('photo')")
content = content.replace("if profile_photo and profile_photo.filename:", "if photo and photo.filename:")
content = content.replace("secure_filename(profile_photo.filename)", "secure_filename(photo.filename)")
content = content.replace("profile_photo.save(filepath)", "photo.save(filepath)")
content = content.replace("Only JPG/JPEG and PNG files are allowed", "Only JPG, JPEG, PNG, and WEBP files are allowed")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)


# 2. Update profile.html
path = r'C:\PROJECTS\BLOOP\app\templates\staff\profile.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("name=\"profile_photo\"", "name=\"photo\"")
content = content.replace("id=\"profile_photo\"", "id=\"photo\"")
content = content.replace("for=\"profile_photo\"", "for=\"photo\"")
content = content.replace("uploads/profile_photos/", "uploads/profile/")
content = content.replace("accept=\".jpg,.jpeg,.png\"", "accept=\".jpg,.jpeg,.png,.webp\"")
content = content.replace("document.getElementById('profile_photo')", "document.getElementById('photo')")
content = content.replace("['image/jpeg', 'image/png', 'image/jpg']", "['image/jpeg', 'image/png', 'image/jpg', 'image/webp']")
content = content.replace("Only JPG/JPEG and PNG files", "Only JPG, JPEG, PNG, and WEBP files")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)


# 3. Update base.html
path = r'C:\PROJECTS\BLOOP\app\templates\base.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("uploads/profile_photos/", "uploads/profile/")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated everything!')
