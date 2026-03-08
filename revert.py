import os
import re

files = [
    r'd:\project for hackthon\ecogravity 1\ecogravity\templates\dashboard\student.html',
    r'd:\project for hackthon\ecogravity 1\ecogravity\templates\dashboard\researcher.html',
    r'd:\project for hackthon\ecogravity 1\ecogravity\templates\dashboard\professional.html'
]

for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove animation classes
    content = re.sub(r'\s*animate-slide-up\s*', ' ', content)
    content = re.sub(r'\s*stagger-\d\s*', ' ', content)
    
    # Restore normal CSS link
    content = content.replace("css/student.css') }}?v=1.1", "css/student.css') }}")
    content = content.replace("css/researcher.css') }}?v=1.1", "css/researcher.css') }}")
    content = content.replace("css/professional.css') }}?v=1.1", "css/professional.css') }}")
    
    # clean up any leftover multiple spaces
    content = content.replace('class=\" ', 'class=\"')
    content = content.replace('  \"', '\"')
    
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
print('HTML restored')
