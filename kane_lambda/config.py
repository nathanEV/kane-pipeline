# config.py
"""
Configuration module for feature toggles and constants.
"""

# Feature toggles
ENABLE_K_SHEET_CLEAN = False
ENABLE_K_SELECTOR = False

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
    "fact_summary": "BLURB",
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