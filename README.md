# ipo-analysis
Code analyses the mechanism which a prop trading firm uses to analyse Indian IPOs across industry segments and creates a framework for future analysis.
This analysis figures out a framework to rate an IPO across indstry segments.
It uses analysis already completed by a analyst.
We read those analyses, compile them by sectors and then find common patterns
    Which ratios are useful for which industry
    How to compare against peers
    How to spot issues in the RHP
    How to find growth opportunities.
Then we build this framework from this compilation.

Then we see the success of this analysis in short term IPO returns.
We note that short term IPO returns are a factor od demand supply factors rather than fundamental factors.

Nevertheless this framework is good to analyse IPO fundamentals if not for predicting short term outcomes.

Steps: 
1. We gather all the links on a publicly provided website which analyses selected IPOs.
The script for this is in the grab_blog_list_links along with argumnets to select a specific time period of article links

2. We the n grab the article text and metadata
Code for this is in grab_blog_articles_text

3. Parse this text with an LLM to find the factors of the analysis and IPO industry segment
Code is in structure_ipo_articles_with_openai

4. One we have this structured outputm, we push this to any LLM to make a framework by industry segemnts.
This aanalysis and its outcomes are in the outputs/verdict_vs_listing day return analysis.

5. The framework for analysing consumer anmd retail segment IPOs is presented as an infographic.

Disclaimers:
1. This is just a framework and not meant for any technical or financial analysis. Purely educative content and not an investment advise.
2. Data is sourced from public sources for analysis. No claims or warranties on data or its usage, ownership or outcomes.