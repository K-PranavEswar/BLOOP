import re

# 1. Fix admin/inventory.html
admin_path = r"C:\PROJECTS\BLOOP\app\templates\admin\inventory.html"
with open(admin_path, 'r', encoding='utf-8') as f:
    admin_content = f.read()

# We need to remove everything between `</div>\n    </div>` and `{% endfor %}` for the blood group cards loop.
# Notice the loop ends at line 58 with `{% endfor %}`.
# The card properly closes at `</div>\n    </div>`.
# Let's find the exact block and replace it.
admin_fixed = re.sub(
    r'(<div class="mt-3 text-center">\s*<span class="badge \{\{ item\.badge_class \}\} px-3 py-2 shadow-sm" style="font-size: 0\.85rem;">\s*\{\{ item\.status \| capitalize \}\}\s*</span>\s*</div>\s*</div>\s*</div>).*?(\{% endfor %\})',
    r'\1\n    \2',
    admin_content,
    flags=re.DOTALL
)

with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(admin_fixed)


# 2. Fix staff/inventory.html
staff_path = r"C:\PROJECTS\BLOOP\app\templates\staff\inventory.html"
with open(staff_path, 'r', encoding='utf-8') as f:
    staff_content = f.read()

# Here we need to remove everything between the closing of the card and `{% else %}`
staff_fixed = re.sub(
    r'(<div class="mt-3 text-center">\s*<span class="badge \{\{ item\.badge_class \}\} px-3 py-2 shadow-sm" style="font-size: 0\.85rem;">\s*\{\{ item\.status \| capitalize \}\}\s*</span>\s*</div>\s*</div>\s*</div>).*?(\{% else %\})',
    r'\1\n    \2',
    staff_content,
    flags=re.DOTALL
)

with open(staff_path, 'w', encoding='utf-8') as f:
    f.write(staff_fixed)

print("Layouts repaired.")
