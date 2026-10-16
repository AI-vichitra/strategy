import os
import re

search_dir = 'frontend/src'
for root, _, files in os.walk(search_dir):
    for file in files:
        if file.endswith(('.tsx', '.ts')):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = re.findall(r'.{0,40}(?:fetch\(|axios|api/).{0,60}', content)
                if matches:
                    print(f"--- {path} ---")
                    for match in matches:
                        print(match.strip())
