import re

path = r'C:\PROJECTS\BLOOP\app\templates\staff\donors.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the Record Donation Modal block
# It starts with "<!-- Record Donation Modal -->" and ends with "</div>" right before "{% else %}"
modal_regex = re.compile(r'(\s*<!-- Record Donation Modal -->\s*<div class="modal fade" id="recordDonationModal\{\{ donor\.id \}\}".*?</form>\s*</div>\s*</div>\s*</div>\s*)(\{% else %})', re.DOTALL)

match = modal_regex.search(content)
if match:
    modal_html = match.group(1)
    # Remove it from inside the table loop
    content = content.replace(modal_html, '\n                ')
    
    # Now create the new loop block to place at the bottom, just before Add Walk-in Donor Modal
    new_loop = f"""
<!-- Record Donation Modals (Outside table to prevent clipping) -->
{{% for donor in donors %}}
{modal_html.strip()}
{{% endfor %}}

"""
    
    # Inject it before the Walk-in Donor Modal
    content = content.replace('<!-- Add Walk-in Donor Modal -->', new_loop + '<!-- Add Walk-in Donor Modal -->')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Modal successfully extracted and moved outside the table container.")
else:
    print("Could not find the modal block using regex.")
