import re

filepath = r'c:\Users\Cog\Desktop\Strategy\frontend\src\components\builder\MainContent.module.css'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'(?s)\.cursorGlass\s*\{[^}]+\}\s*', '', content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
