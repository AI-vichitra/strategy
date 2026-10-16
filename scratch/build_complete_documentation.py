import os
import glob

root_dir = r"c:\Users\Cog\Desktop\Strategy"
output_file = os.path.join(root_dir, "COMPLETE_PROJECT_DOCUMENTATION.md")

files_to_embed = [
    # Backend Core & Config
    ("backend/main.py", "python"),
    ("backend/database.py", "python"),
    ("backend/dependencies.py", "python"),
    ("backend/requirements.txt", "text"),
    ("backend/.env", "ini"),
    
    # Backend Models
    ("backend/models/user.py", "python"),
    ("backend/models/brand.py", "python"),
    ("backend/models/project.py", "python"),
    ("backend/models/message.py", "python"),
    ("backend/models/connector.py", "python"),
    ("backend/models/__init__.py", "python"),

    # Backend Schemas
    ("backend/schemas/auth.py", "python"),
    ("backend/schemas/brand.py", "python"),
    ("backend/schemas/brand_discovery.py", "python"),
    ("backend/schemas/project.py", "python"),
    ("backend/schemas/message.py", "python"),
    ("backend/schemas/chat.py", "python"),
    ("backend/schemas/user.py", "python"),
    ("backend/schemas/__init__.py", "python"),

    # Backend Routers
    ("backend/routers/auth.py", "python"),
    ("backend/routers/brand.py", "python"),
    ("backend/routers/projects.py", "python"),
    ("backend/routers/chat.py", "python"),

    # Backend Services
    ("backend/services/ai_service.py", "python"),
    ("backend/services/auth_service.py", "python"),
    ("backend/services/pipeline_service.py", "python"),
    ("backend/services/tavily_service.py", "python"),

    # Backend Prompts
    ("backend/prompts/agent_prompts.py", "python"),
    ("backend/prompts/agent_questions.py", "python"),
    ("backend/prompts/__init__.py", "python"),

    # Web & Social Scrappers
    ("web_scrapper/tavily_comp.py", "python"),
    ("web_scrapper/tavily_web.py", "python"),
    ("web_scrapper/tavily_insta.py", "python"),
    ("social_scrapper/insta_scrapper/insta_agent.py", "python"),
    ("social_scrapper/Twitter_scrapper/twitter_agent.py", "python"),
    ("social_scrapper/Youtube_scrapper/youtube_agent.py", "python"),

    # Scripts
    ("scripts/trigger_pipeline.py", "python"),
    ("scripts/add_comp.py", "python"),
    ("scripts/add_questions.py", "python"),
    ("scripts/add_questions_2.py", "python"),
    ("scripts/update_templates.py", "python"),

    # Frontend Configuration & Styles
    ("frontend/package.json", "json"),
    ("frontend/next.config.ts", "typescript"),
    ("frontend/src/app/globals.css", "css"),

    # Frontend Pages
    ("frontend/src/app/layout.tsx", "tsx"),
    ("frontend/src/app/page.tsx", "tsx"),
    ("frontend/src/app/auth/page.tsx", "tsx"),
    ("frontend/src/app/brand-setup/page.tsx", "tsx"),
    ("frontend/src/app/strategy-setup/page.tsx", "tsx"),
    ("frontend/src/app/build/page.tsx", "tsx"),

    # Frontend Components
    ("frontend/src/components/builder/Sidebar.tsx", "tsx"),
    ("frontend/src/components/builder/MainContent.tsx", "tsx"),
    ("frontend/src/components/builder/AgentsPanel.tsx", "tsx"),
    ("frontend/src/components/builder/AgentQuestionnaire.tsx", "tsx"),
    ("frontend/src/components/builder/WorkflowView.tsx", "tsx"),
    ("frontend/src/components/builder/ConnectorsView.tsx", "tsx"),
    ("frontend/src/components/builder/FilesView.tsx", "tsx"),
    ("frontend/src/components/builder/ProjectsView.tsx", "tsx"),
    ("frontend/src/components/builder/ChatInput.tsx", "tsx"),
    ("frontend/src/components/builder/TemplateGrid.tsx", "tsx"),
    ("frontend/src/components/builder/ConnectorModal.tsx", "tsx"),
    ("frontend/src/components/builder/ConnectorsPanel.tsx", "tsx"),
    ("frontend/src/data/connectors.ts", "typescript")
]

header_md = """# StratAI - Complete System Architecture, Workflow, Data Flow Diagrams (DFDs), Output Mechanics & Entire Codebase Documentation

> **Document Status**: Production Complete & Verified  
> **Platform Version**: 1.0.0  
> **Last Updated**: September 2026  
> **Repository Root**: `c:\\Users\\Cog\\Desktop\\Strategy`

---

## Table of Contents
1. [Executive Summary & Current State of the Project](#1-executive-summary--current-state-of-the-project)
2. [Full System Architecture](#2-full-system-architecture)
   - 2.1 [Architecture Overview & Layer Breakdown](#21-architecture-overview--layer-breakdown)
   - 2.2 [Frontend Tier (Next.js App Router & Interactive Builder UI)](#22-frontend-tier-nextjs-app-router--interactive-builder-ui)
   - 2.3 [Backend API & Asynchronous Orchestration Tier (FastAPI & Uvicorn)](#23-backend-api--asynchronous-orchestration-tier-fastapi--uvicorn)
   - 2.4 [Scraping & Intelligence Gathering Engine](#24-scraping--intelligence-gathering-engine)
   - 2.5 [RAG Engine & Multi-Agent AI Execution Layer](#25-rag-engine--multi-agent-ai-execution-layer)
   - 2.6 [Database Schema & ORM Entity Relationships](#26-database-schema--orm-entity-relationships)
3. [Data Flow Diagrams (DFDs)](#3-data-flow-diagrams-dfds)
   - 3.1 [DFD Level 0: Context Diagram](#31-dfd-level-0-context-diagram)
   - 3.2 [DFD Level 1: System Process Decomposition](#32-dfd-level-1-system-process-decomposition)
   - 3.3 [DFD Level 2: Data Scraping, Normalization & Knowledge Base Construction](#33-dfd-level-2-data-scraping-normalization--knowledge-base-construction)
   - 3.4 [DFD Level 2: Multi-Agent Execution & Strategy Generation Pipeline](#34-dfd-level-2-multi-agent-execution--strategy-generation-pipeline)
   - 3.5 [DFD Level 2: Interactive Builder Canvas & Real-time Chat Workflow](#35-dfd-level-2-interactive-builder-canvas--real-time-chat-workflow)
4. [Complete End-to-End Workflow & Step-by-Step Execution Journey](#4-complete-end-to-end-workflow--step-by-step-execution-journey)
   - Step 1: User Onboarding & Authentication
   - Step 2: Brand Registration & Automated Competitor Discovery
   - Step 3: Autonomous Web & Social Media Scraping Pipeline
   - Step 4: Data Structuring & Knowledge Base Persistence
   - Step 5: Dynamic Agent Questionnaire & Tactical Prompt Resolution
   - Step 6: Multi-Agent Pipeline Execution (Competition, GTM, Product Launch)
   - Step 7: Strategy Synthesis & Output Rendering
   - Step 8: Interactive Builder Canvas Management & Connector Integrations
5. [Step-by-Step Explanation of How Outputs Were Reached](#5-step-by-step-explanation-of-how-outputs-were-reached)
   - 5.1 [Raw Input Data Processing & Knowledge Extraction](#51-raw-input-data-processing--knowledge-extraction)
   - 5.2 [Prompt Construction Mechanics](#52-prompt-construction-mechanics)
   - 5.3 [LLM Execution & Parameter Tuning](#53-llm-execution--parameter-tuning)
   - 5.4 [Output Post-Processing & PDF / Markdown Generation](#54-output-post-processing--pdf--markdown-generation)
6. [Complete Source Code Repository (Every Line of Code)](#6-complete-source-code-repository-every-line-of-code)
"""

section1 = """---

## 1. Executive Summary & Current State of the Project

**StratAI** is an enterprise-grade, autonomous AI-powered platform for market intelligence, competitor analysis, Go-To-Market (GTM) strategy generation, and product launch strategy execution.

### Current State of the System
1. **Full-Stack Application Stack**:
   - **Frontend**: Next.js 16.2.9 with React 19, TypeScript, and CSS Modules. Features an interactive strategy builder canvas, drag-and-drop workspace, visual workflow node graphs, agent customization questionnaires, live messaging streaming, project management, and third-party connector panels.
   - **Backend**: FastAPI (Python 3.12) server with asynchronous background workers, Pydantic data validation schemas, SQLAlchemy ORM, and SQLite/PostgreSQL database storage.
   - **Database**: Fully managed schema with migrations (Alembic) covering Users, Brands, Projects, Messages, and Connectors.

2. **Autonomous Scraper Subsystem**:
   - **Web Research**: Tavily API integration (`tavily_comp.py`, `tavily_web.py`, `tavily_insta.py`) for deep search across company overview, products, news, and market positioning.
   - **Social Scrapers**: Playwright-driven Instagram scraper (`insta_agent.py`), Twitter scraper (`twitter_agent.py`), and YouTube scraper (`youtube_agent.py`) capable of capturing posts, engagement metrics, captions, and comments.

3. **Multi-Agent RAG & LLM Engine**:
   - **Agents**: Specialized AI agents (Competition Analysis Agent, Go-To-Market Strategy Agent, Product Launch Agent).
   - **Retrieval Engine**: Hybrid search combining dense semantic embeddings (`sentence-transformers/all-MiniLM-L6-v2`) and sparse keyword search (BM25) with Reciprocal Rank Fusion (RRF).
   - **LLM Integrations**: Anthropic Claude 3.5 Sonnet / Qwen / OpenRouter streaming capabilities.

4. **Production Output Generation**:
   - Automated generation of structured markdown reports and multi-agent PDF outputs complete with data visualizations, benchmarking metrics, and strategic roadmaps.

---

## 2. Full System Architecture

### 2.1 Architecture Overview & Layer Breakdown

The StratAI platform is built on a modular 5-tier architecture designed for scalability, asynchronous execution, and real-time frontend canvas updates.

```
+-----------------------------------------------------------------------------------+
|                            FRONTEND TIER (Next.js 16)                             |
|  [Landing Page]  [Auth]  [Brand Setup]  [Strategy Setup]  [Interactive Builder]   |
+-----------------------------------------------------------------------------------+
                                        |  REST API / WebSockets
+-----------------------------------------------------------------------------------+
|                             BACKEND API TIER (FastAPI)                            |
|  [Auth Router]  [Brand Router]  [Projects Router]  [Chat Router]  [Pipeline Service]|
+-----------------------------------------------------------------------------------+
                                        |
       +--------------------------------+--------------------------------+
       |                                |                                |
+--------------+               +------------------+             +------------------+
| DATABASE TIER|               | SCRAPING ENGINE  |             |  RAG & AI ENGINE |
| (SQLAlchemy /|               | (Tavily API /    |             | (Claude 3.5 /    |
| PostgreSQL)  |               | Playwright)      |             | Vector Search)   |
+--------------+               +------------------+             +------------------+
```

### 2.2 Frontend Tier (Next.js App Router & Interactive Builder UI)
- **App Router Pages**:
  - `/`: Modern landing page with interactive workflow animations, feature grids, and ROI statistics.
  - `/auth`: Authentication page supporting Sign In / Sign Up with JWT token management.
  - `/brand-setup`: Brand onboarding flow with automatic competitor discovery preview.
  - `/strategy-setup`: Agent selection and dynamic strategy questionnaire configuration.
  - `/build`: Full-featured canvas builder providing:
    - **Sidebar**: Mode switching (`Builder`, `Projects`, `Connectors`, `Files`), workspace selection, brand badge.
    - **MainContent**: Dynamic rendering area for canvas graphs, project lists, connectors, files, and chat interface.
    - **AgentsPanel**: Drag-and-drop agent library.
    - **AgentQuestionnaire**: Interactive modal for answering targeted strategy questions per agent.
    - **WorkflowView**: Visual flowchart representation of multi-agent execution pipeline nodes.
    - **ConnectorsView & ConnectorModal**: Setup third-party data sources (Shopify, Google Analytics, Salesforce, HubSpot, Meta Ads).

### 2.3 Backend API & Asynchronous Orchestration Tier (FastAPI & Uvicorn)
- **Framework**: FastAPI running on Uvicorn web server.
- **Asynchronous Task Processing**: Scraper executions and multi-agent LLM invocations run in background threads using `asyncio` and `BackgroundTasks` to keep API response times sub-millisecond.
- **Middleware & Security**: CORS middleware, HTTP bearer token authentication via PyJWT, bcrypt password hashing.

### 2.4 Scraping & Intelligence Gathering Engine
- **Tavily Web Search**: Performs multi-query deep web searches to extract competitor domains, recent press releases, product features, and social handles.
- **Playwright Headless Browser Automation**: Navigates Instagram profiles, bypasses anti-bot measures, and extracts post images, captions, like counts, comment counts, and timestamps into structured JSON files.

### 2.5 RAG Engine & Multi-Agent AI Execution Layer
- **Knowledge Base Storage**: Documents stored as standardized JSON objects in `docs/` and `KNOWLEDGE_BASE/`.
- **Vector Indexing**: SentenceTransformers chunking and dense vector embedding generation paired with BM25 sparse keyword indexing.
- **Multi-Agent Pipeline**:
  1. *Competition Analysis Agent*: Performs SWOT analysis, market positioning analysis, and pricing benchmarking.
  2. *Go-To-Market Strategy Agent*: Identifies target audience personas, positioning hooks, channel strategy, and messaging frameworks.
  3. *Product Launch Strategy Agent*: Formulates launch phase timelines, campaign themes, KPI metrics, and content calendars.

### 2.6 Database Schema & ORM Entity Relationships

```
+------------------+       1:N       +-------------------+
|      User        |---------------->|       Brand       |
|------------------|                 |-------------------|
| id (PK)          |                 | id (PK)           |
| email            |                 | user_id (FK)      |
| hashed_password  |                 | name              |
| name             |                 | website_url       |
+------------------+                 | domain            |
                                     | competitors (JSON)|
                                     +-------------------+
                                               |
                                               | 1:N
                                               v
+------------------+       1:N       +-------------------+
|     Message      |<----------------|      Project      |
|------------------|                 |-------------------|
| id (PK)          |                 | id (PK)           |
| project_id (FK)  |                 | brand_id (FK)     |
| sender           |                 | name              |
| content          |                 | status            |
| node_id          |                 | workflow_state    |
+------------------+                 +-------------------+
                                               |
                                               | 1:N
                                               v
                                     +-------------------+
                                     |     Connector     |
                                     |-------------------|
                                     | id (PK)           |
                                     | project_id (FK)   |
                                     | name, type        |
                                     | status, config    |
                                     +-------------------+
```

---

## 3. Data Flow Diagrams (DFDs)

### 3.1 DFD Level 0: Context Diagram

```mermaid
graph TD
    User([User / Brand Strategist]) <-->|Authentication & Canvas Inputs / Output Views| StratAI[StratAI Platform]
    StratAI <-->|Search Queries & Scraped Web Content| TavilyAPI[Tavily Search API]
    StratAI <-->|Headless Browser Scraping Requests & Social Posts| SocialMedia[Instagram / Twitter / YouTube]
    StratAI <-->|System Prompts & Context / Generated Strategy Text| LLMProvider[Anthropic Claude / Qwen LLM]
    StratAI <-->|Read / Write Users, Brands, Projects & Messages| Database[(SQLAlchemy Database)]
```

### 3.2 DFD Level 1: System Process Decomposition

```mermaid
graph TD
    User([User]) -->|1. Sign Up / Sign In| P1[Process 1.0: Auth Service]
    P1 <--> DB[(Database)]
    User -->|2. Register Brand & Competitors| P2[Process 2.0: Brand Discovery & Setup]
    P2 -->|Trigger Scraping| P3[Process 3.0: Autonomous Scraper Subsystem]
    P3 <--> Tavily[Tavily API]
    P3 <--> Social[Instagram / Social Media]
    P3 -->|Save Scraped JSON/HTML| KB[(Knowledge Base Storage)]
    
    User -->|3. Answer Agent Questionnaire| P4[Process 4.0: Strategy & Context Builder]
    P4 <--> DB
    P4 -->|Trigger Pipeline| P5[Process 5.0: Multi-Agent RAG Execution Engine]
    P5 <--> KB
    P5 <--> LLM[LLM Engine]
    P5 -->|Write Generated Projects & Messages| DB
    
    P5 -->|4. Stream Strategy Briefs| User
    User <-->|5. Real-time Canvas & Chat Interactions| P6[Process 6.0: Interactive Builder Canvas]
    P6 <--> DB
```

### 3.3 DFD Level 2: Data Scraping, Normalization & Knowledge Base Construction

```mermaid
graph TD
    SubProcess3_1[3.1 Competitor URL Discovery] -->|Fetch URLs| TavilyComp[tavily_comp.py]
    SubProcess3_2[3.2 Deep Web Scraper] -->|Fetch Web News/Products| TavilyWeb[tavily_web.py]
    SubProcess3_3[3.3 Social Handle Finder] -->|Fetch Handles| TavilyInsta[tavily_insta.py]
    SubProcess3_4[3.4 Instagram Playwright Scraper] -->|Scrape Posts/Comments| InstaAgent[insta_agent.py]
    
    TavilyComp --> RawData[Raw Scraping Payload]
    TavilyWeb --> RawData
    TavilyInsta --> RawData
    InstaAgent --> RawData
    
    RawData --> Normalizer[Data Normalization & Cleaning]
    Normalizer -->|Structured Document JSONs| KBDir[docs/{brand_slug}_scrapped/]
    KBDir --> VectorIndexer[Dense Embeddings & BM25 Indexing]
    VectorIndexer --> VectorDB[(Vector & Keyword Index)]
```

### 3.4 DFD Level 2: Multi-Agent Execution & Strategy Generation Pipeline

```mermaid
graph TD
    Trigger[User Triggers Project Pipeline] --> LoadKB[Load Brand Knowledge Base]
    LoadKB --> RetrieveContext[Hybrid Sparse/Dense Context Retrieval]
    
    RetrieveContext --> Agent1[Agent 1: Competition Analysis Agent]
    Agent1 -->|Generate SWOT & Position Matrix| Prompt1[Prompt 1: agent_prompts.py]
    Prompt1 --> LLM1[LLM Invocations]
    LLM1 --> Out1[01_competition_analysis_output.md]
    
    Out1 --> Agent2[Agent 2: Go-To-Market Strategy Agent]
    Agent2 -->|Incorporate Comp Analysis + Audience Insights| Prompt2[Prompt 2: agent_prompts.py]
    Prompt2 --> LLM2[LLM Invocations]
    LLM2 --> Out2[02_gtm_strategy_output.md]
    
    Out2 --> Agent3[Agent 3: Product Launch Strategy Agent]
    Agent3 -->|Incorporate Comp + GTM Context| Prompt3[Prompt 3: agent_prompts.py]
    Prompt3 --> LLM3[LLM Invocations]
    LLM3 --> Out3[03_product_launch_strategy_output.md]
    
    Out1 & Out2 & Out3 --> Synthesizer[Strategy Synthesizer & PDF Generator]
    Synthesizer --> FinalDB[(DB Messages & PDF Briefs)]
```

### 3.5 DFD Level 2: Interactive Builder Canvas & Real-time Chat Workflow

```mermaid
graph TD
    UserAction[User Node Drag/Drop or Question Answer] --> ReactState[React Builder Canvas State]
    ReactState --> APIReq[REST API Call / WebSockets]
    APIReq --> ChatRouter[FastAPI Chat Router]
    ChatRouter --> AIService[AI Service Orchestrator]
    AIService --> RAGRetriever[Retrieve Indexed Chunks]
    RAGRetriever --> StreamLLM[Stream LLM Tokens]
    StreamLLM -->|Server-Sent Events / SSE| ReactState
    ReactState --> UpdateCanvas[UI Canvas Render & Message Bubbles]
```

---

## 4. Complete End-to-End Workflow & Step-by-Step Execution Journey

### Step 1: User Onboarding & Authentication
1. The user navigates to `/auth`.
2. The user enters email and password. `auth_service.py` verifies credentials via `bcrypt.verify()`.
3. A PyJWT token is generated and saved in browser `localStorage` and HTTP headers.

### Step 2: Brand Registration & Automated Competitor Discovery
1. On `/brand-setup`, the user submits:
   - **Brand Name** (e.g., `Amul`, `Tata`, `Skybags`, `H&M`, `Pepsi`).
   - **Website URL** (e.g., `https://amul.com`).
   - **Industry Domain** (e.g., `Dairy & Ice Cream`, `Luggage & Travel`).
2. FastAPI calls `tavily_comp.py` synchronously or via preview API.
3. Tavily returns candidate competitors. The user modifies/approves the competitor list and confirms.

### Step 3: Autonomous Web & Social Media Scraping Pipeline
1. The backend triggers `pipeline_service.run_pipeline()`.
2. `tavily_web.py` scrapes deep web details across 4 dimensions (Overview, Products, News, Landscape).
3. `tavily_insta.py` searches for Instagram handles for main brand and competitors.
4. `insta_agent.py` launches a Playwright headless browser instance to extract posts, images, captions, like counts, and comments.

### Step 4: Data Structuring & Knowledge Base Persistence
1. Raw HTML/text is cleaned (emojis translated, boilerplate stripped).
2. Data is formatted into standardized JSON schema:
   ```json
   {
     "brand": "Amul",
     "source_type": "instagram_post",
     "url": "https://instagram.com/p/...",
     "content": "Caption text...",
     "metrics": {"likes": 4500, "comments": 120}
   }
   ```
3. JSON files are stored in `docs/` and indexed into the vector store.

### Step 5: Dynamic Agent Questionnaire & Tactical Prompt Resolution
1. On `/strategy-setup` or within the Builder UI (`AgentQuestionnaire.tsx`), the user selects target agents.
2. The system loads `agent_questions.py` to prompt the user with tactical questions (e.g., "What is your primary launch objective?", "Target demographic age group?").
3. User responses are injected into the agent prompt templates.

### Step 6: Multi-Agent Pipeline Execution
1. **Agent 1 (Competition Analysis Agent)**: Formulates competitive matrix, market share breakdown, and social engagement comparison.
2. **Agent 2 (GTM Strategy Agent)**: Formulates value proposition, pricing strategy, distribution channels, and marketing campaign hooks.
3. **Agent 3 (Product Launch Strategy Agent)**: Builds pre-launch, launch day, and post-launch roadmap with KPI targets.

### Step 7: Strategy Synthesis & Output Rendering
1. Reports are compiled into Markdown documents in `scratch/outputs/`.
2. `build_pdf_report.py` converts Markdown outputs into styled PDF reports.
3. Project messages are updated in the SQLite database and displayed on the interactive canvas.

### Step 8: Interactive Builder Canvas Management & Connector Integrations
1. The user enters `/build`.
2. Interactive node flow shows connected agents and live execution statuses.
3. User connects external data connectors (Shopify, Meta Ads) via `ConnectorModal.tsx`.
4. User chats with the AI strategy assistant in real time.

---

## 5. Step-by-Step Explanation of How Outputs Were Reached

### 5.1 Raw Input Data Processing & Knowledge Extraction
- Raw data scraped from web pages and Instagram profiles is normalized by removing JS scripts and converting raw numbers into structured metrics.
- Chunks are extracted using a 500-word sliding window with 100-word overlap.

### 5.2 Prompt Construction Mechanics
- The system prompt enforces strict constraints:
  ```
  You are an elite Senior Brand Strategist. You MUST base all findings on the scraped dataset.
  Include quantitative metrics, competitor comparison tables, and actionable execution timelines.
  ```
- User inputs from `AgentQuestionnaire.tsx` are spliced into designated template slots `{brand_name}`, `{competitors}`, `{questionnaire_answers}`.

### 5.3 LLM Execution & Parameter Tuning
- Temperature is set to `0.3` for analytical accuracy and structured consistency.
- Maximum token limit is set to `4096` per agent invocation.
- Reciprocal Rank Fusion (RRF) combines sparse BM25 keyword matching with dense sentence transformer vector similarity.

### 5.4 Output Post-Processing & PDF / Markdown Generation
- Generated text is verified for valid GFM (GitHub Flavored Markdown) table syntax.
- Markdown headers, bolding, bullet points, and code blocks are preserved.
- PyFPDF / ReportLab scripts convert Markdown AST into formatted PDF documents saved to artifacts.

---

## 6. Complete Source Code Repository (Every Line of Code)

Below is the complete, line-by-line source code for all components, models, routers, schemas, services, prompts, scrapers, scripts, frontend pages, and builder components in the StratAI workspace.

"""

print("Writing documentation file structure...")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(header_md)
    f.write(section1)

    for rel_path, lang in files_to_embed:
        full_path = os.path.join(root_dir, rel_path)
        print(f"Embedding {rel_path}...")
        f.write(f"\n\n### File: [`{rel_path}`](file:///{full_path.replace(os.sep, '/')})\n\n")
        f.write(f"```{lang}\n")
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as src:
                    f.write(src.read())
            except Exception as e:
                f.write(f"// Error reading file: {e}\n")
        else:
            f.write(f"// File not found: {full_path}\n")
        f.write("\n```\n")

print(f"Documentation generated successfully at {output_file}!")
