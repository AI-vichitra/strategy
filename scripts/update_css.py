import sys

replacements = {
    '#bbf7d0': '#e8e4f3',
    'rgba(22, 163, 74, 0.08)': 'rgba(198, 186, 222, 0.15)',
    'rgba(22, 163, 74, 0.07)': 'rgba(198, 186, 222, 0.15)',
    '#f0fdf4': '#f8f7ff',
    '#dcfce7': '#e8e4f3',
    '#16a34a': '#8b5cf6',
    '#15803d': '#7c3aed',
    '#86efac': '#c6bade',
    '#14532d': '#1e1b4b',
    '#fafffe': '#faf9ff',
    '#f7fef9': '#f5f2ff',
    '#059669': '#c6bade',
    '#d1fae5': '#e8e4f3',
    'rgba(22, 163, 74, 0.3)': 'rgba(139, 92, 246, 0.3)',
    'rgba(22, 163, 74, 0.4)': 'rgba(139, 92, 246, 0.4)'
}

for filepath in [
    r'c:\Users\Cog\Desktop\Strategy\frontend\src\components\builder\ChatInput.module.css',
    r'c:\Users\Cog\Desktop\Strategy\frontend\src\components\builder\AgentQuestionnaire.module.css'
]:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements.items():
        content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
