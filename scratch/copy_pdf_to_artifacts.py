import os
import shutil

src = "scratch/StratAI_Strategy_Prompts_And_Outputs_Report.pdf"
dst_dir = r"C:\Users\Cog\.gemini\antigravity-ide\brain\a87380f2-32e5-4c33-960b-4bdbd066335e"
dst = os.path.join(dst_dir, "StratAI_Strategy_Prompts_And_Outputs_Report.pdf")

if os.path.exists(src):
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied PDF to artifact location: {dst}")
else:
    print("Source PDF not found!")
