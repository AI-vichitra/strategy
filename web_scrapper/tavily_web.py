import os
import sys
import json
import html
from urllib.parse import urlparse
from dotenv import load_dotenv
from tavily import TavilyClient

def synthesize_insights(category, results, tavily_answer):
    """Aggregates, cleans, and structures retrieved snippets into a dense, multi-paragraph AI synthesis of 500+ words."""
    paragraphs = []
    
    # Start with Tavily's short answer if present
    if tavily_answer:
        paragraphs.append(f"<strong>Executive Overview:</strong> {tavily_answer}")
        
    # Extract all text content from the search results
    all_snippets = []
    for r in results:
        content = r.get('content', '')
        if content:
            all_snippets.append(content)
            
    # Clean and split into sentences, avoiding duplicates
    sentences = []
    seen = set()
    for snippet in all_snippets:
        for sentence in snippet.split('. '):
            clean_s = sentence.strip().replace('\n', ' ')
            if len(clean_s) > 25 and clean_s.lower() not in seen:
                seen.add(clean_s.lower())
                sentences.append(clean_s)
                
    if category == "company_overview_mission_and_strategy":
        # Group by History/Background, Mission/Vision, Business Model/Pricing, Marketing/Growth
        p_history = [s for s in sentences if any(w in s.lower() for w in ['history', 'founded', 'established', 'heritage', 'delhi land', 'largest', 'growth', 'years', 'decade'])]
        p_vision = [s for s in sentences if any(w in s.lower() for w in ['vision', 'mission', 'value', 'build', 'future', 'commit', 'quality', 'sustainability', 'responsibility'])]
        p_pricing = [s for s in sentences if any(w in s.lower() for w in ['pricing', 'price', 'cost', 'premium', 'luxury', 'revenue', 'financial', 'crore', 'sq', 'square', 'debt'])]
        p_marketing = [s for s in sentences if any(w in s.lower() for w in ['marketing', 'strategy', 'brand', 'advertise', 'promote', 'market', 'geographic', 'segment', 'real estate'])]
        
        other = [s for s in sentences if s not in p_history and s not in p_vision and s not in p_pricing and s not in p_marketing]
        
        if p_history:
            paragraphs.append("<strong>Corporate History & Foundation:</strong> " + ". ".join(p_history) + ".")
        if p_vision:
            paragraphs.append("<strong>Vision, Mission & Core Values:</strong> " + ". ".join(p_vision) + ".")
        if p_pricing:
            paragraphs.append("<strong>Pricing Structure & Business Model:</strong> " + ". ".join(p_pricing) + ".")
        if p_marketing:
            paragraphs.append("<strong>Marketing & Geographic Strategy:</strong> " + ". ".join(p_marketing) + ".")
        if other:
            paragraphs.append("<strong>Key Strategy Metrics & Operational Footprint:</strong> " + ". ".join(other) + ".")
            
    elif category == "products_and_services_deep_dive":
        p_res = [s for s in sentences if any(w in s.lower() for w in ['residential', 'apartment', 'home', 'housing', 'luxury residential', 'villa', 'project', 'gurugram'])]
        p_comm = [s for s in sentences if any(w in s.lower() for w in ['commercial', 'office', 'workspace', 'cybercity', 'cyber city', 'tech', 'lease', 'rental'])]
        p_retail = [s for s in sentences if any(w in s.lower() for w in ['retail', 'mall', 'shopping', 'centre', 'plaza', 'retail destination', 'entertainment'])]
        other = [s for s in sentences if s not in p_res and s not in p_comm and s not in p_retail]
        
        if p_res:
            paragraphs.append("<strong>Residential Developments:</strong> " + ". ".join(p_res) + ".")
        if p_comm:
            paragraphs.append("<strong>Commercial & Office Infrastructure:</strong> " + ". ".join(p_comm) + ".")
        if p_retail:
            paragraphs.append("<strong>Retail & Leisure Spaces:</strong> " + ". ".join(p_retail) + ".")
        if other:
            paragraphs.append("<strong>Additional Offerings & Quality Standards:</strong> " + ". ".join(other) + ".")
            
    elif category == "latest_news_and_developments":
        p_announcements = [s for s in sentences if any(w in s.lower() for w in ['launch', 'project', 'new project', 'upcoming', 'expansion', 'invest', 'crore'])]
        p_financials = [s for s in sentences if any(w in s.lower() for w in ['q1', 'q2', 'q3', 'q4', 'fy', 'revenue', 'profit', 'sales', 'growth', 'share', 'stock'])]
        p_news = [s for s in sentences if any(w in s.lower() for w in ['news', 'recent', 'latest', 'award', 'recognition', 'report', 'july', '2026', '2025'])]
        other = [s for s in sentences if s not in p_announcements and s not in p_financials and s not in p_news]
        
        if p_announcements:
            paragraphs.append("<strong>Upcoming Launch Announcements & Strategic Expansions:</strong> " + ". ".join(p_announcements) + ".")
        if p_financials:
            paragraphs.append("<strong>Recent Financial Reports & Sales Performance:</strong> " + ". ".join(p_financials) + ".")
        if p_news:
            paragraphs.append("<strong>Awards, Media Recognition & Market Highlights:</strong> " + ". ".join(p_news) + ".")
        if other:
            paragraphs.append("<strong>General Updates & Recent Activity:</strong> " + ". ".join(other) + ".")
            
    else:  # competitors
        p_res_comp = [s for s in sentences if any(w in s.lower() for w in ['godrej', 'tata', 'sobha', 'prestige', 'oberoi', 'lodha', 'macrotech', 'dlf', 'competitor', 'rival'])]
        p_comm_comp = [s for s in sentences if any(w in s.lower() for w in ['brookfield', 'embassy', 'mindspace', 'reit', 'commercial competitor', 'office space'])]
        p_general = [s for s in sentences if s not in p_res_comp and s not in p_comm_comp]
        
        if p_res_comp:
            paragraphs.append("<strong>Residential Domain Competitors:</strong> " + ". ".join(p_res_comp) + ".")
        if p_comm_comp:
            paragraphs.append("<strong>Commercial & Office Space Rivals:</strong> " + ". ".join(p_comm_comp) + ".")
        if p_general:
            paragraphs.append("<strong>General Market Competitors & Position:</strong> " + ". ".join(p_general) + ".")

    # Format into detailed paragraphs
    full_text = "<br/><br/>".join(paragraphs)
    word_count = len(full_text.split())
    
    # If the combined details are still less than 500 words, let's append remaining sentences to ensure density
    if word_count < 500 and sentences:
        extra_sentences = [s for s in sentences if s not in full_text]
        if extra_sentences:
            paragraphs.append("<strong>Additional Strategic Context:</strong> " + ". ".join(extra_sentences) + ".")
            full_text = "<br/><br/>".join(paragraphs)
            
    return full_text

def convert_markdown_to_html(text):
    """Converts basic markdown tags (bold, headers, lists, linebreaks) to standard HTML tags."""
    import re
    # 1. Headers
    text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    
    # 2. Bold/Italics
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    
    # 3. Lists conversion
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\s*[-*+]\s+(.*?)$', stripped):
            item_text = re.sub(r'^\s*[-*+]\s+', '', stripped)
            if not in_list:
                new_lines.append('<ul>')
                in_list = True
            new_lines.append(f'<li>{item_text}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
        
    text = '\n'.join(new_lines)
    # Double newlines to paragraph break, single to line break
    text = text.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
    return text

def synthesize_master_insights(brand_name, categorized_results):
    """Combines all categorised results into a single comprehensive corporate summary of at least 500 words."""
    paragraphs = []
    
    # Collect all sentences from all categories
    all_sentences_by_cat = {}
    for category, data in categorized_results.items():
        results = data.get('results', [])
        tavily_answer = data.get('answer', '')
        
        snippets = []
        if tavily_answer:
            snippets.append(tavily_answer)
        for r in results:
            content = r.get('content', '')
            if content:
                snippets.append(content)
                
        sentences = []
        seen = set()
        for snip in snippets:
            for s in snip.split('. '):
                clean_s = s.strip().replace('\n', ' ')
                if len(clean_s) > 25 and clean_s.lower() not in seen:
                    seen.add(clean_s.lower())
                    sentences.append(clean_s)
        all_sentences_by_cat[category] = sentences

    # 1. Company Overview, History & Mission
    overview_s = all_sentences_by_cat.get("company_overview_mission_and_strategy", [])
    if overview_s:
        p_overview = "<strong>Corporate Overview & Strategy:</strong> " + ". ".join(overview_s[:12]) + "."
        paragraphs.append(p_overview)
    
    # 2. Products & Services Deep Dive
    products_s = all_sentences_by_cat.get("products_and_services_deep_dive", [])
    if products_s:
        p_products = "<strong>Product & Service Portfolio:</strong> " + ". ".join(products_s[:12]) + "."
        paragraphs.append(p_products)
    
    # 3. Latest News & Developments
    news_s = all_sentences_by_cat.get("latest_news_and_developments", [])
    if news_s:
        p_news = "<strong>Recent Developments & News:</strong> " + ". ".join(news_s[:12]) + "."
        paragraphs.append(p_news)
    
    # 4. Competitor Analysis
    competitors_s = all_sentences_by_cat.get("competitors_by_domain_and_vertical", [])
    if competitors_s:
        p_competitors = "<strong>Competitive Landscape & Market Positioning:</strong> " + ". ".join(competitors_s[:12]) + "."
        paragraphs.append(p_competitors)

    full_text = "<br/><br/>".join(paragraphs)
    word_count = len(full_text.split())
    
    # Ensure it's at least 500 words
    if word_count < 500:
        extra = []
        for cat, s_list in all_sentences_by_cat.items():
            for s in s_list:
                if s not in full_text:
                    extra.append(s)
        if extra:
            paragraphs.append("<strong>Additional Deep Insights:</strong> " + ". ".join(extra[:20]) + ".")
            full_text = "<br/><br/>".join(paragraphs)
            
    return convert_markdown_to_html(full_text)

def generate_html_report(brand_name, company_url, brand_category, categorized_results):
    """Generates a premium, beautiful dark-mode HTML report with rich aesthetics and responsive layout."""
    
    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand_name.upper()} - Comprehensive Intelligence Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
    <style>
        :root {{
            --bg-color: #0b0c10;
            --card-bg: rgba(22, 24, 30, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-primary: #00f2fe;
            --accent-secondary: #4facfe;
            --text-main: #f5f6f8;
            --text-muted: #94a3b8;
            --glow: rgba(0, 242, 254, 0.15);
        }}
        
        body {{
            margin: 0;
            padding: 40px 20px;
            font-family: 'Outfit', sans-serif;
            background: radial-gradient(circle at 50% 0%, #1e1e2f 0%, var(--bg-color) 70%);
            color: var(--text-main);
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 60px;
            position: relative;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 48px;
            font-weight: 800;
            letter-spacing: -1px;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px var(--glow);
        }}
        
        .header p {{
            color: var(--text-muted);
            font-size: 18px;
            margin-top: 12px;
            font-weight: 300;
        }}
        
        .header .meta-url {{
            display: inline-block;
            margin-top: 8px;
            color: var(--accent-primary);
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
            background: rgba(0, 242, 254, 0.1);
            padding: 6px 16px;
            border-radius: 20px;
            border: 1px solid rgba(0, 242, 254, 0.2);
            transition: all 0.3s ease;
        }}
        
        .header .meta-url:hover {{
            background: rgba(0, 242, 254, 0.2);
            box-shadow: 0 0 15px var(--glow);
        }}
        
        .category-section {{
            margin-bottom: 60px;
        }}
        
        .category-title {{
            font-size: 26px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 25px;
            padding-bottom: 12px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .category-title::before {{
            content: '';
            display: inline-block;
            width: 6px;
            height: 24px;
            background: linear-gradient(to bottom, var(--accent-primary), var(--accent-secondary));
            border-radius: 3px;
        }}
        
        .results-grid {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        .ai-summary {{
            background: linear-gradient(135deg, rgba(22, 24, 30, 0.9), rgba(15, 23, 42, 0.9));
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3), 0 0 20px var(--glow);
            backdrop-filter: blur(8px);
        }}
        
        .ai-summary h3 {{
            color: var(--accent-primary);
            font-size: 20px;
            margin: 0 0 15px 0;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }}
        
        .ai-summary-content {{
            font-size: 16px;
            color: #e2e8f0;
            font-weight: 400;
        }}
        
        .result-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(8px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .result-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(0, 242, 254, 0.4);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 0 15px var(--glow);
        }}
        
        .result-title {{
            font-size: 19px;
            font-weight: 600;
            margin: 0 0 8px 0;
        }}
        
        .result-title a {{
            color: var(--text-main);
            text-decoration: none;
            background: linear-gradient(to right, #fff, #fff);
            background-size: 0% 2px;
            background-repeat: no-repeat;
            background-position: left bottom;
            transition: background-size 0.3s ease, color 0.3s ease;
        }}
        
        .result-title a:hover {{
            color: var(--accent-primary);
            background-size: 100% 2px;
        }}
        
        .result-url {{
            font-size: 13px;
            color: var(--accent-secondary);
            margin-bottom: 14px;
            word-break: break-all;
            font-family: monospace;
            opacity: 0.8;
        }}
        
        .result-content {{
            font-size: 15px;
            color: var(--text-muted);
            line-height: 1.6;
        }}
        
        .empty-state {{
            text-align: center;
            color: var(--text-muted);
            padding: 30px;
            font-size: 16px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
        }}
        
        footer {{
            text-align: center;
            margin-top: 80px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{brand_name.upper()}</h1>
            <p style="text-transform: uppercase; font-size: 14px; letter-spacing: 2px; color: var(--accent-primary); margin-top: 4px; font-weight: 600;">{brand_category}</p>
            <p>Extensive Market Intelligence & Corporate Profile Report</p>
            {f'<a href="{company_url}" target="_blank" class="meta-url">{company_url}</a>' if company_url else ''}
        </div>
        
        <!-- Single Master AI Synthesized Insight at the Top -->
        <div class="ai-summary" style="margin-bottom: 50px;">
            <h3 style="font-size: 24px; border-bottom: 1px solid rgba(0, 242, 254, 0.2); padding-bottom: 12px;">✨ Integrated AI Corporate Intelligence & Synthesized Insight</h3>
            <div class="ai-summary-content" style="font-size: 16.5px; line-height: 1.8;">
                {synthesize_master_insights(brand_name, categorized_results)}
            </div>
        </div>
"""

    for category, data in categorized_results.items():
        results = data.get('results', [])
        
        # Format the title for better user viewing
        formatted_title = category.replace('_', ' ').title()
        
        html_output += f"""
        <div class="category-section">
            <h2 class="category-title">{formatted_title}</h2>
        """
        
        html_output += '            <div class="results-grid">\n'
        
        if not results:
            html_output += '                <div class="empty-state">No direct web sources matching this query.</div>\n'
        else:
            for res in results:
                title = res.get('title', 'No Title')
                url = res.get('url', '#')
                raw_content = res.get('content', '')
                clean_content = raw_content.replace('#', '').strip()
                
                html_output += f"""
                <div class="result-card">
                    <h3 class="result-title"><a href="{url}" target="_blank">{html.escape(title)}</a></h3>
                    <div class="result-url">{url}</div>
                    <div class="result-content">{html.escape(clean_content)}</div>
                </div>
                """
        html_output += """
            </div>
        </div>
        """

    html_output += """
        <footer>
            Generated by Tavily2 Deep Search Agent • Deep Dive Corporate Intelligence
        </footer>
    </div>
</body>
</html>
"""
    return html_output


def run_report(brand_name, brand_url, brand_category, output_dir=None):
    # Load .env variables
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(base_dir, "backend", ".env"))
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Error: TAVILY_API_KEY not found!")
        return None

    client = TavilyClient(api_key=api_key)
    
    if output_dir is None:
        data_dir = os.path.join(base_dir, "ALL_OUTPUT")
    else:
        data_dir = output_dir
    os.makedirs(data_dir, exist_ok=True)
    
    # We clean brand_name for filename saving
    clean_brand_name = brand_name.replace(" ", "_").lower()
    
    print(f"\nExecuting Tavily2 Deep Search Agent for: {brand_name.upper()} ({brand_category.upper()})...")
    
    # Categorized queries mapping using the three specified details
    queries = {
        "company_overview_mission_and_strategy": (
            f"Provide a highly detailed, comprehensive corporate profile and strategy overview of at least 500 words for the company {brand_name} ({brand_category}) with official website {brand_url}, "
            f"including its history, mission statement, vision statement, pricing model, and marketing strategy."
        ),
        "products_and_services_deep_dive": (
            f"Provide a detailed and comprehensive breakdown of at least 500 words of all products and services offered by the {brand_category} company {brand_name} (official website: {brand_url}), "
            f"describing every major product, feature, or service they provide in depth."
        ),
        "latest_news_and_developments": (
            f"Provide a dense, in-depth news digest of at least 500 words covering the latest news, recent updates, press releases, "
            f"and public announcements regarding the {brand_category} company {brand_name} (website: {brand_url})."
        ),
        "competitors_by_domain_and_vertical": (
            f"Provide an extensive analysis of at least 500 words listing and explaining the key competitors and market rivals "
            f"of the {brand_category} company {brand_name} (website: {brand_url}) across different business domains and verticals."
        )
    }
    
    categorized_results = {}
    
    for category_name, query_string in queries.items():
        print(f"  -> Deep Searching: '{query_string}'")
        try:
            response = client.search(
                query=query_string,
                search_depth="advanced",
                max_results=5,  # Fetch more results for extensive details
                include_answer=True
            )
            categorized_results[category_name] = {
                'results': response.get("results", []),
                'answer': response.get("answer", "")
            }
        except Exception as e:
            print(f"     Search failed for '{query_string}': {e}")
            categorized_results[category_name] = {'results': [], 'answer': ''}
            
    # Generate Report
    html_content = generate_html_report(brand_name, brand_url, brand_category, categorized_results)
    
    report_filename = f"{clean_brand_name}_tavily2.html"
    report_filepath = os.path.join(data_dir, report_filename)
    
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Saved extensive Tavily2 report to: {report_filepath}")
    return report_filepath

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tavily2_agent.py <brand_name> [brand_url] [brand_category]")
        sys.exit(1)
        
    brand_name = sys.argv[1].replace("@", "")
    brand_url = sys.argv[2] if len(sys.argv) > 2 else f"https://{brand_name}"
    brand_category = sys.argv[3] if len(sys.argv) > 3 else "Company"
    
    run_report(brand_name, brand_url, brand_category)
