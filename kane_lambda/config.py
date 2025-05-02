# config.py
import os
"""
Configuration module for feature toggles and constants.
"""

# Feature toggles
ENABLE_K_SHEET_CLEAN = False
ENABLE_K_SELECTOR = False

# Toggle to choose split-version prioritizer instead of the standard one
USE_SPLIT_PRIORITIZER = True

# LLM backend selection: "openrouter" or "gemini"
LLM_BACKEND = "gemini"

# Gemini API key (for Google GenAI client)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Model name constants for split prioritizer and headscanner
CATEGORY_MODEL = "gemini-2.5-flash-preview-04-17"
SIGNIFICANCE_MODEL = "gemini-2.5-pro-preview-03-25"
RELEVANCE_MODEL = "gemini-2.5-flash-preview-04-17"
HEADSCANNER_MODEL = "gemini-2.5-pro-preview-03-25"

# Prioritizer settings
CATEGORIES = [
    "Product_Research",
    "Capital_Corporate_Moves",
    "Infrastructure_Supply",
    "Market_Financial_Signals",
    "Policy_Geopolitics",
]

# LLM prompt template for prioritizer; include placeholder {story_batch}
PROMPT_TEMPLATE = """
Role: AI Content Curator for "The One AI Email".
Audience: Senior Execs, Investors (Public & VC). Focus strictly on AI, Semiconductors, Enterprise Software, Cloud Infra, related Energy (data centers/tech demand), Capital Markets ($50M+ deals, M&A, IPOs, major AI/Tech stock moves), and specific AI/Tech Policy/Geopolitics.
Task: Process input "fact records". Filter ruthlessly based on audience relevance; exclude general news, minor updates, consumer reviews, etc. If unsure, exclude.
Output: Return a JSON list like this:
[
  {
    "story_id": "123",
    "fact_summary": "...",
    "category": "Product_Research",
    "category_reason": "reason...",
    "significance_score": 7
  },
  ...
]

Field Generation Rules:
CATEGORIES  (choose ONE—no ties)

1️⃣  Product_Research  
    • Launches or major upgrades of AI products, features, or models that ship ≤6 months out  
    • Benchmark-moving research results, open checkpoints, scaled deployments (≥100 M users/images/API calls)  

2️⃣  Capital_Corporate_Moves  
    • Full acquisitions or controlling stakes (M&A)  
    • Venture / growth / grant funding **≥ US $100 M**  
    • Strategic equity or commercial partnerships with disclosed value **≥ US $500 M** or multi-year revenue commitment  

3️⃣  Infrastructure_Supply  
    • Chips, HBM/HBM4, ASICs, foundry capacity, data-centre or network build-outs, cooling/power breakthroughs  
    • Critical minerals, batteries, energy/storage projects **explicitly sized or located for AI workloads**  

4️⃣  Market_Financial_Signals  
    • Earnings, guidance, index/sector moves **≥ ±10 %** at AI-exposed firms  
    • *NEW: Market or academic research that quantifies AI's economic or productivity impact*  
      – e.g., "HBS study: marketers +56 % productivity using GenAI"  
    • Capital-markets or macro data tied directly to AI demand/supply (e.g., "AI VC funding hits $113 B Q1")  
    • Revenue, margin, or KPI changes companies **attribute primarily to AI** (e.g., "Intuit +5 % revenue from AI upsell")  

5️⃣  Policy_Geopolitics  
    • Enacted or near-certain laws, executive orders, export controls  
    • Subsidies or incentives **≥ US $2 B**  
    • Multilateral pacts (G-, WTO, OECD) that meaningfully affect AI

If the blurb fails every definition above, output:  
{
    "story_id": "#NUMBER",
    "fact_summary": "PUT THE BLURB HERE",
    "category": "UNKNOWN",
    "categoryreason": "Not relevant",
    "significance_score": 1
  }

fact_summary: 25-35 words, neutral, factual summary of brief_factual_sentence. Include key numbers/metrics. Include ticker only if explicit or one of: (MSFT, GOOGL, AAPL, AMZN, NVDA, META, TSLA, TSM, INTC, AMD). End with "(Source: [source_name])". No markdown.
significance_score: Integer 1-10 based on importance to audience. Assess Relevance (Core AI/Tech focus?) & Scale/Impact (Major players/funds/policy?).
Not Relevant: 1-2
Relevant & Low Impact: 3-4
Relevant & Medium Impact: 5-7
Relevant & High Impact: 8-10

Ignore any source note or attribution—it never changes the label.  
• "Future-of-work / productivity" studies or company revenue bumps **belong in Market_Financial_Signals**.

EXAMPLES:
Blurb: "HBS study: marketers 56 % more productive using GenAI assistants."  
Blurb: "Humanoid-robot startup 1X raises $125 M Series B led by OpenAI."  
Blurb: "AWS to build €15 B Irish data-centre for GenAI workloads."  
Blurb: "EU formally adopts AI Act; rules take effect 2026."  
Blurb: "Nvidia posts record Q4 data-centre revenue of $35.6 B (+93 % YoY)."  
Blurb: "OpenAI COO: 700 M images created with GPT-4o in 60 days."  


[
  {
    "story_id": "1",
    "fact_summary": "HBS study: marketers 56 % more productive using GenAI assistants.",
    "category": "Market_Financial_Signals",
    "categoryreason": "Research quantifies productivity impact",
    "significance_score": 8
  },
  {
    "story_id": "2",
    "fact_summary": "Humanoid-robot startup 1X raises $125 M Series B led by OpenAI.",
    "category": "Capital_Corporate_Moves",
    "categoryreason": "Funding ≥$50 M",
    "significance_score": 8
  },
  {
    "story_id": "3",
    "fact_summary": "AWS to build €15 B Irish data-centre for GenAI workloads.",
    "category": "Infrastructure_Supply",
    "categoryreason": "AI-specific DC build-out",
    "significance_score": 9
  },
  {
    "story_id": "4",
    "fact_summary": "EU formally adopts AI Act; rules take effect 2026.",
    "category": "Policy_Geopolitics",
    "categoryreason": "Law enacted",
    "significance_score": 9
  },
  {
    "story_id": "5",
    "fact_summary": "Nvidia posts record Q4 data-centre revenue of $35.6 B (+93 % YoY).",
    "category": "Market_Financial_Signals",
    "categoryreason": "Revenue growth",
    "significance_score": 10
  }
]

NOW PROCESS THIS BATCH. RETURN NOTHING BUT THE JSON LIST.

BLURBS: {story_batch}
"""

# Prompt templates for split prioritizer
CATEGORY_PROMPT_TEMPLATE = """
You are CategoryClassifier-v2 for *The One AI Email*.  
Input: a single ~30-word factual blurb already judged AI-relevant.  
Output: exactly one category label (no lists) plus a ≤12-word category_reason, in flat JSON:

{"category":"<CategoryName>","category_reason":"<short-reason>"}

────────────────────────────────────────
CATEGORIES  (choose ONE—no ties)

1️⃣  Product_Research  
    • Launches or major upgrades of AI products, features, or models that ship ≤6 months out  
    • Benchmark-moving research results, open checkpoints, scaled deployments (≥100 M users/images/API calls)  

2️⃣  Capital_Corporate_Moves  
    • Full acquisitions or controlling stakes (M&A)  
    • Venture / growth / grant funding **≥ US $100 M**  
    • Strategic equity or commercial partnerships with disclosed value **≥ US $500 M** or multi-year revenue commitment  

3️⃣  Infrastructure_Supply  
    • Chips, HBM/HBM4, ASICs, foundry capacity, data-centre or network build-outs, cooling/power breakthroughs  
    • Critical minerals, batteries, energy/storage projects **explicitly sized or located for AI workloads**  

4️⃣  Market_Financial_Signals  
    • Earnings, guidance, index/sector moves **≥ ±10 %** at AI-exposed firms  
    • *NEW: Market or academic research that quantifies AI's economic or productivity impact*  
      – e.g., "HBS study: marketers +56 % productivity using GenAI"  
    • Capital-markets or macro data tied directly to AI demand/supply (e.g., "AI VC funding hits $113 B Q1")  
    • Revenue, margin, or KPI changes companies **attribute primarily to AI** (e.g., "Intuit +5 % revenue from AI upsell")  

5️⃣  Policy_Geopolitics  
    • Enacted or near-certain laws, executive orders, export controls  
    • Subsidies or incentives **≥ US $2 B**  
    • Multilateral pacts (G-, WTO, OECD) that meaningfully affect AI

If the blurb fails every definition above, output:  
{"category":"Unknown","category_reason":"No strong match"}

────────────────────────────────────────
RULES  
• Emit exactly one JSON object; no markdown, no extra keys, no whitespace padding.  
• Select the **single best category**.  
• Ignore any source note or attribution—it never changes the label.  
• "Future-of-work / productivity" studies or company revenue bumps **belong in Market_Financial_Signals**.

────────────────────────────────────────
EXAMPLES  

Input blurbs
	•	Story ID 1
"Nvidia (NVDA) posts record Q4 data-centre revenue of $35.6 B, up 93 % year-on-year."
	•	Story ID 2
"OpenAI COO says users created 700 M images with GPT-4o in just 60 days."
	•	Story ID 3
"Harvard Business School study finds marketers 56 % more productive when using GenAI assistants."
	•	Story ID 4
"Humanoid-robot start-up 1X raises a $125 M Series B led by OpenAI, valuing the firm at $1.2 B."
	•	Story ID 5
"AWS will build a €15 B data-centre campus in Ireland dedicated to generative-AI workloads."
	•	Story ID 6
"European Union formally adopts the AI Act; core rules will take effect in 2026."

⸻

Classifier output

[
  {"story_id":"1","category":"Market_Financial_Signals","category_reason":"Earnings move >±10 %"},
  {"story_id":"2","category":"Product_Research","category_reason":"Usage milestone >100 M"},
  {"story_id":"3","category":"Market_Financial_Signals","category_reason":"Research quantifies productivity impact"},
  {"story_id":"4","category":"Capital_Corporate_Moves","category_reason":"Funding ≥$100 M"},
  {"story_id":"5","category":"Infrastructure_Supply","category_reason":"AI-specific DC build-out"},
  {"story_id":"6","category":"Policy_Geopolitics","category_reason":"Law enacted"}
]
NOW PROCESS THIS BATCH. RETURN NOTHING BUT THE JSON LIST.

BLURBS: {story_batch}
"""

SIGNIFICANCE_PROMPT_TEMPLATE = """
SIGNIFICANCE RATING PROMPT v2
------------------------------------------------------------

Role  
You are SignificanceScorer-v2 for *The One AI Email*.

Objective  
For every incoming fact record (a single 25-35-word factual blurb that has already been filtered for AI/tech relevance and categorised), estimate its importance to senior executives, institutional investors, and VCs by assigning an integer significance_score from **1** (low) to **10** (high).

Audience Lens — What Matters  
•   Artificial Intelligence: Model breakthroughs, large-scale deployments, enterprise adoption, significant research shifts.
•   Semiconductors, Cloud & Enterprise Software: Chip advancements, critical tooling, hyperscale infrastructure build-outs or constraints.
•   Energy for Tech Workloads: Generation or storage projects/tech sized for data-centres/AI impacting cost or availability.
•   Capital Markets: M&A, funding ≥ $50 M, major stock/index moves related to AI/tech players.
•   Policy, Geopolitics & Major Disruptions: Laws, subsidies, export controls; significant failures, security breaches, intense competitive conflicts, or major controversies involving key players that materially alter the AI/tech landscape or strategic positioning.

Scoring Framework  
(Start at 5 as a neutral baseline; adjust using the triggers below.)

  Score | Typical Triggers (illustrative, not exhaustive)
  ------|--------------------------------------------------
  9-10  | • Landmark AI model (state-of-the-art leap, paradigm shift)  
        | • Mega-deals: M&A ≥ $10 B, funding ≥ $1 B, DC/fab spend ≥ $10 B  
        | • Global-reach regulation (e.g., US/EU chip export bans)  
        | • Market jolts ≥ ±20 % in FAANG-plus or AI index  
  7-8   | • New models beating key benchmarks, mass-market product launches  
        | • Funding $250 M–$1 B, M&A $1 B–$10 B  
        | • Data-centre / fab projects ≥ $1 B  
        | • National AI subsidies or mandates ≥ $1 B  
        | • Stock moves 10–20 % in major AI names  
  5-6   | • Mid-tier deals (funding $50 M–$250 M, M&A $100 M–$1 B)  
        | • Competitive feature releases from secondary players  
        | • Early-stage regulatory drafts or regional incentives  
        | • Earnings beats/misses < 10 % at AI-leveraged firms  
  3-4   | • Minor product tweaks, small partnerships, seed/Series A < $50 M  
        | • Local or preliminary policy chatter  
        | • Limited-scope infra announcements (< $500 M)  
  1-2   | • Tangential or narrowly scoped updates with negligible strategic impact  
        | • Pure speculation or opinion without concrete action/metric  

Adjustment Rules  
1. Concentration of Impact (Power Elite) 
   If the story directly involves any of the major AI labs (OpenAI, Google, Meta, Anthropic, etc.) or any of these tickers—MSFT, GOOGL, AAPL, AMZN, NVDA, META, TSLA, TSM, INTC, AMD—add **+1** unless clearly trivial.

2. Novelty & Momentum  
   Down-rate incremental follow-ups unless fresh metrics or milestones show ≥ 10 % change or a materially new angle.

Output Specification  
Return ONLY a JSON list of objects with keys "story_id" and "significance_score". No extra characters.

EXAMPLES

Input Blurb
Story ID = 301
"OpenAI introduces GPT-6, outperforming GPT-5 by 45 % on MMLU, cutting inference cost four-fold, handling 128-k context windows, and shipping to Azure clients next month under priority access tiers."

Output

[{"story_id":"301","significance_score":10}]



⸻

Input Blurb
Story ID = 302
"Microsoft (MSFT) commits $15 billion for a 3 GW small-modular-reactor-powered data-centre campus in Wyoming, doubling Azure AI compute capacity and promising 24/7 zero-carbon electricity by 2028."

Output

[{"story_id":"302","significance_score":9}]



⸻

Input Blurb
Story ID = 303
"Independent researchers show GPT-4o consistently tailors politically sensitive answers to align with perceived user stance, scoring 0.85 probability in bias tests, raising concerns about unintended 'sycophantic' moderation behaviour."

Output

[{"story_id":"303","significance_score":8}]



⸻

Input Blurb
Story ID = 304
"Duolingo (DUOL) will phase out 5 % of freelance translators, redirecting $18 million annually toward GPT-4o content generation, as the language-learning platform declares itself 'AI-first', says CEO."

Output

[{"story_id":"304","significance_score":7}]



⸻

Input Blurb
Story ID = 305
"Spotify (SPOT) reports Q2 paying subscribers up 11 % YoY to 305 million; executives credit AI DJ playlists for boosting retention and outline expanded monetisation trials later this year."

Output

[{"story_id":"305","significance_score":6}]



⸻

Input Blurb
Story ID = 306
"Snowflake adds native vector search and embedding functions, matching Databricks while keeping current pricing; analysts estimate the feature could unlock an incremental $150 million in annual upsell revenue."

Output

[{"story_id":"306","significance_score":5}]



⸻

Input Blurb
Story ID = 307
"Brazilian startup PetNutri raises $18 million Series A to develop GPT-powered personalised dog-food plans, targeting 100 thousand Latin-American subscribers by 2027 amid a growing pet-wellness market."

Output

[{"story_id":"307","significance_score":3}]



⸻

Input Blurb
Story ID = 308
"Android 16.1 introduces an optional AI-generated wallpaper feature that restyles photos; Google says it's free, initially limited to Pixel 8, with user-feedback surveys guiding broader rollout."

Output

[{"story_id":"308","significance_score":2}]

# OUTPUT example JSON array for batch
OUTPUT
[
  {"story_id":"1","significance_score":10},
  {"story_id":"2","significance_score":8}
]

NOW PROCESS THIS BATCH. RETURN NOTHING BUT THE JSON LIST.

BLURBS: {story_batch}
"""

RELEVANCE_PROMPT_TEMPLATE = """
You are a binary filter for an AI-only newsletter.

TASK
Read the 30-word blurb.  
If its main subject is inside the AI stack (see definitions), output exactly {"relevance":"IN"}.  
Else output exactly {"relevance":"SKIP"}.

AI-STACK DEFINITIONS (include any direct consequence):
• Core-AI-Tech – model development/training/benchmarks
• Application-Usage – AI-driven software, robotics, autonomous vehicles, smart devices
• Physical-Infrastructure – AI chips, fabs, data-centres, networks, cooling, critical minerals/batteries
• Foundation-Energy – energy/storage projects built for AI workloads
• Impact-Layer – strategy, capital markets, jobs, geopolitics, culture, education, daily life changes clearly caused by AI

STRICT RULES
– Choose only one value: "IN" or "SKIP".  
– No extra keys, text, or whitespace.

EXAMPLES

Blurb: "Nvidia unveils HBM4 memory quadrupling AI training speed."  
Output:  
[{"story_id":"1","relevant":"IN"}]

Blurb: "Boeing buys Spirit AeroSystems for fuselage supply chain."  
Output:  
[{"story_id":"2","relevant":"SKIP"}]

# OUTPUT example JSON array for batch
OUTPUT
[
  {"story_id":"1","relevant":"IN"},
  {"story_id":"2","relevant":"SKIP"}
]

NOW PROCESS THIS BATCH. RETURN NOTHING BUT THE JSON LIST.

BLURBS: {story_batch}
"""

# Headscanner prompt template
HEADSCANNER_PROMPT_TEMPLATE = """
You are a structured news assistant.

        For each input item, extract:
        - "context_snippet": A short sentence that encapsulates the context of the news item. All relevant entities should be included and named in the sentence. The reader should be able to have a nice kurt takeaway of what happened.
        - "author": Extract only if has_author is false, else return an empty string.

        Return only a JSON array of objects. No commentary, no markdown, no formatting, no headings.

        Here are some examples of what the context_snippet should look like:
        [
            {
                "context_snippet": "Global startup funding surged to $113B in Q1, up 54% YoY, with AI dominating 77% of US deal value, demonstrating robust AI investment momentum.",
                "author": "Emily Carter"
            },
            {
                "context_snippet": "China's low-altitude economy is projected to reach $207B in 2025, with two Chinese companies receiving regulatory approval to launch autonomous passenger drones (flying taxis).",
                "author": "Liang Zhou"
            },
            {
                "context_snippet": "Figure AI has deployed fully autonomous humanoid robots at a BMW factory, achieving end-to-end autonomy in a major milestone for industrial robotics.",
                "author": "Patrick O'Neill"
            },
            {
                "context_snippet": "US companies face strategic uncertainty responding to Trump's trade war with China.",
                "author": "Amanda Reyes"
            },
            {
                "context_snippet": "Samsung has turned to Chinese customers like Baidu to prop up its ailing chip business and is the "biggest supplier of HBM into China".",
                "author": "David Kim"
            },
            {
                "context_snippet": "India's venture capital funding rebounded to $13.7 billion in 2024, up 1.4x from 2023, with 45% more deals (1,270 total).",
                "author": "Priya Nair"
            },
            {
                "context_snippet": "Apple is considering increasing the starting price of its iPhone due to tariffs imposed on its major production sources.",
                "author": "Olivia Bennett"
            },
            {
                "context_snippet": "Meta launched Llama 4 Maverick with 400B parameters and Scout with 109B parameters and a 10M context window.",
                "author": "Jason Park"
            },
            {
                "context_snippet": "Anthropic's Alignment Science team found that the "legibility" or "faithfulness" of reasoning models' Chain-of-Thought can't be trusted and models may actively hide reasoning.",
                "author": "Natalie Gomez"
            },
            {
                "context_snippet": "Google's Gemini 2.5 Pro achieved a high score on the GPQA Diamond test, outperforming human experts by 14 points, demonstrating exceptional reasoning capabilities.",
                "author": "Victor Singh"
            },
            {
                "context_snippet": "DeepMind's experimental AI model learned to collect diamonds in Minecraft without explicit instructions, showcasing emergent reasoning capabilities.",
                "author": "Hannah Laurent"
            },
            {
                "context_snippet": "Cognition launched Devin 2.0, an advanced AI coding tool that autonomously handles 80% of coding needs, representing a significant advancement in AI-assisted software development.",
                "author": "Kevin Morales"
            },
            {
                "context_snippet": "Meta is expected to share news about a Llama 4 Reasoning model "in the next month" according to Mark Zuckerberg.",
                "author": "Rachel Stein"
            },
            {
                "context_snippet": "Amazon is experimenting with an "agentic 'Buy for Me' button" that lets AI make purchases on behalf of users, potentially revolutionizing e-commerce with autonomous shopping assistance.",
                "author": "Ethan Brooks"
            },
            {
                "context_snippet": "Genspark has launched a general-purpose Super Agent that outperforms Butterfly Effect's Manus agent and OpenAI's Deep Research on the GAIA benchmark.",
                "author": "Sofia Alvarez"
            },
            {
                "context_snippet": "SandboxAQ raised a $150M Series E extension from Google, Nvidia, and others, taking its total funding to $950M+.",
                "author": "Marcus Lee"
            },
            {
                "context_snippet": "Investors have poured $7.2B into 50+ humanoid robot startups since 2015, with $1.6B invested in 2024 alone.",
                "author": "Isabella Rossi"
            },
            {
                "context_snippet": "Miami-based remittance startup Felix Pago raised a $75M Series B led by QED, following impressive growth with over $1B in WhatsApp money transfers via stablecoins in 2024.",
                "author": "Gabriel Silva"
            },
            {
                "context_snippet": "Runway, an AI video startup, closed a $308M funding round, more than doubling its valuation to $3B, highlighting continued investor confidence in generative video AI.",
                "author": "Chloe Martin"
            },
            {
                "context_snippet": "Chef Robotics has raised $43.1M in Series A funding to develop meal assembly robots, accelerating automation in food preparation.",
                "author": "Daniel Cooper"
            },
            {
                "context_snippet": "New US tariffs on Chinese goods could increase the bill of materials for the iPhone 16 Pro with 256GB storage from $550 to $850.",
                "author": "Alexis Wright"
            },
            {
                "context_snippet": "OpenAI and Google rejected the UK's proposal to allow training AI on copyrighted work without permission unless rights holders opt out.",
                "author": "Hiroshi Tanaka"
            },
            {
                "context_snippet": "US Commerce Secretary Howard Lutnick signals withholding promised CHIPS Act grants as he pushes companies to substantially expand their US projects.",
                "author": "Lauren Mitchell"
            },
            {
                "context_snippet": "The BBC has complained to the UK CMA about Apple and Google's news aggregators downplaying BBC branding, raising concerns about platform power in digital media.",
                "author": "Ahmed Hassan"
            },
            {
                "context_snippet": "Intel and TSMC have reached a preliminary agreement to form a joint venture that will operate Intel's chipmaking facilities with TSMC taking a 20% stake.",
                "author": "Julia Schneider"
            },
            {
                "context_snippet": "Accenture and Schaeffler are teaming up to overhaul industrial automation using NVIDIA Omniverse, potentially transforming manufacturing processes.",
                "author": "Fernando Costa"
            },
            {
                "context_snippet": "Hyundai Motor Group is set to buy tens of thousands of robots from Boston Dynamics, marking one of the largest humanoid robot deals to date.",
                "author": "Yuna Kim"
            },
            {
                "context_snippet": "Amazon has bid to buy TikTok as its April 5 sell-off deadline approaches, potentially marking a major consolidation in the social media landscape.",
                "author": "Benjamin Clark"
            } 
        ]

        Format:
        [
        {
            "context_snippet": "A direct sentence from summary.",
            "author": "Author Name"
        },
        ...
        ]


        INPUT:
        {batch}
"""