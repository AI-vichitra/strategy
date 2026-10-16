import os
import sys
import reportlab
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

def create_pdf():
    pdf_path = "scratch/StratAI_Strategy_Prompts_And_Outputs_Report.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E1B4B'),
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#475569'),
        spaceAfter=24
    )
    
    agent_title_style = ParagraphStyle(
        'AgentTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#4F46E5'),
        spaceBefore=16,
        spaceAfter=8
    )
    
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=6
    )
    
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6,
        wordWrap='CJK'
    )
    
    story = []
    
    # Header
    story.append(Paragraph("StratAI — Backend Prompts & AI Strategy Outputs Report", title_style))
    story.append(Paragraph("Comprehensive Audit Report covering Competition Analysis, Go-To-Market (GTM) Strategy, and Product Launch Strategy.", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4F46E5'), spaceAfter=20))
    
    agents = [
        ("01. Competition Analysis Agent", "scratch/prompts/01_competition_analysis_prompt.txt", "scratch/outputs/01_competition_analysis_output.md"),
        ("02. Go-To-Market (GTM) Strategy Agent", "scratch/prompts/02_gtm_strategy_prompt.txt", "scratch/outputs/02_gtm_strategy_output.md"),
        ("03. Product Launch Strategy Agent", "scratch/prompts/03_product_launch_strategy_prompt.txt", "scratch/outputs/03_product_launch_strategy_output.md"),
    ]
    
    for agent_title, prompt_file, output_file in agents:
        story.append(Paragraph(agent_title, agent_title_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=10))
        
        # Backend Prompt Section
        story.append(Paragraph("Backend System Prompt", section_header_style))
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
            # Escape HTML characters for Paragraph
            clean_prompt = prompt_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
            story.append(Paragraph(clean_prompt[:3500] + ("..." if len(clean_prompt) > 3500 else ""), code_style))
        else:
            story.append(Paragraph("Prompt file not found.", body_style))
            
        story.append(Spacer(1, 10))
        
        # Generated Output Section
        story.append(Paragraph("Generated AI Strategy Output", section_header_style))
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                output_text = f.read()
            
            clean_output = output_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
            story.append(Paragraph(clean_output, body_style))
        else:
            story.append(Paragraph("Output file not found.", body_style))
            
        story.append(PageBreak())
        
    doc.build(story)
    print(f"PDF successfully generated at {pdf_path}")

if __name__ == "__main__":
    create_pdf()
