import re
import os

def extract():
    with open(r"C:\Users\Cog\Desktop\Strategy\frontend\src\components\builder\MainContent.tsx", 'r', encoding='utf-8') as f:
        content = f.read()

    # Find agentQuestions
    q_start = content.find('const agentQuestions: Record<string, Question[]> = {')
    if q_start != -1:
        q_start = content.find('{', q_start)
        # Find matching brace
        brace_count = 0
        q_end = q_start
        for i in range(q_start, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    q_end = i + 1
                    break
        q_str = content[q_start:q_end]
        
        # turn into valid python
        q_str = re.sub(r'\btrue\b', 'True', q_str)
        q_str = re.sub(r'\bfalse\b', 'False', q_str)
        q_str = re.sub(r"condition:\s*\(answers\)\s*=>\s*{\s*const ans = answers\['(.*?)'\] \|\| '';\s*return ans\.includes\('(.*?)'\) \|\| ans\.includes\('(.*?)'\);\s*}",
                       r'condition: lambda answers: ("\2" in answers.get("\1", "") or "\3" in answers.get("\1", ""))', q_str)
        
        # Remove any trailing commas before } which python dicts allow, but JS unquoted keys need to be quoted.
        # Actually, python requires quoted string keys if they are strings. 
        # JS object keys like `question: "..."` need to become `"question": "..."`
        q_str = re.sub(r'(\s+)([a-zA-Z_][a-zA-Z0-9_]*):', r'\1"\2":', q_str)

        os.makedirs(r"C:\Users\Cog\Desktop\Strategy\backend\prompts", exist_ok=True)
        with open(r"C:\Users\Cog\Desktop\Strategy\backend\prompts\agent_questions.py", "w", encoding="utf-8") as out_q:
            out_q.write("agent_questions = " + q_str + "\n")

    p_start = content.find('const agentPrompts: Record<string, string> = {')
    if p_start != -1:
        p_start = content.find('{', p_start)
        brace_count = 0
        p_end = p_start
        for i in range(p_start, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    p_end = i + 1
                    break
        p_str = content[p_start:p_end]
        
        # JS object keys like `'SEO Audit':` are already quoted, but let's make sure
        p_str = re.sub(r'(\s+)([a-zA-Z_][a-zA-Z0-9_]*):', r'\1"\2":', p_str)
        # Handle template literals: `...` -> """...""" or similar
        # Since template literals might contain unescaped quotes or newlines:
        p_str = re.sub(r'`(.*?)`', lambda m: '"""' + m.group(1).replace('"""', '\\"\\"\\"') + '"""', p_str, flags=re.DOTALL)

        with open(r"C:\Users\Cog\Desktop\Strategy\backend\prompts\agent_prompts.py", "w", encoding="utf-8") as out_p:
            out_p.write("agent_prompts = " + p_str + "\n")

if __name__ == '__main__':
    extract()
