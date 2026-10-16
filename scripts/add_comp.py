import json

questions = {
  'Competitor Research Agent': [
    {
      'question': 'What is your competitor\'s name?',
      'options': [],
      'multiSelect': False
    },
    {
      'question': 'What is your competitor\'s URL?',
      'options': [],
      'multiSelect': False
    }
  ]
}

out_str = ""
for key, qs in questions.items():
    out_str += f"  '{key}': [\n"
    for q in qs:
        out_str += "    {\n"
        out_str += f"      question: {json.dumps(q['question'])},\n"
        out_str += f"      options: {json.dumps(q['options'])},\n"
        out_str += f"      multiSelect: {'true' if q['multiSelect'] else 'false'}\n"
        out_str += "    },\n"
    out_str += "  ],\n"

with open("frontend/src/components/builder/MainContent.tsx", "r", encoding="utf-8") as f:
    content = f.read()

target = "};\n\nconst agentPrompts:"
new_content = content.replace(target, out_str + target)

with open("frontend/src/components/builder/MainContent.tsx", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done")
