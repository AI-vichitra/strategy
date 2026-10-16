import os
import re

def extract_prompts():
    path = r"C:\Users\Cog\Desktop\Strategy\frontend\src\components\builder\MainContent.tsx"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Create backend/prompts directory if not exists
    os.makedirs(r"C:\Users\Cog\Desktop\Strategy\backend\prompts", exist_ok=True)

    # Extract agentQuestions
    questions_match = re.search(r"const agentQuestions: Record<string, Question\[\]> = (\{.*?\});\n\nconst agentPrompts", content, re.DOTALL)
    if questions_match:
        questions_str = questions_match.group(1)
        # It's TypeScript/JS object, we need to convert it to valid Python if possible,
        # But wait, python has dictionaries. The JS object has keys like 'SEO Audit': and unquoted keys.
        # Actually, in JS the keys are quoted like 'SEO Audit':
        # And we have functions like `condition: (answers) => {...}` which won't parse in Python easily.
        # So maybe a direct textual conversion isn't perfect, but I can write a script that does a passable job,
        # or I can just use JS to export it as JSON.
        pass

if __name__ == '__main__':
    extract_prompts()
