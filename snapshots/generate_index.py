import os

folder = '.'  # Current directory (snapshots)
files = sorted(f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')))

html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Snapshots</title>
</head>
<body>
    <h1>Snapshots Folder</h1>
    <ul>
'''

for file in files:
    html_content += f'        <li><a href="{file}">{file}</a></li>\n'

html_content += '''    </ul>
</body>
</html>
'''

with open('index.html', 'w') as f:
    f.write(html_content)

print("index.html generated successfully!")
