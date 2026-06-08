# L0 Source-only baseline prompt

You are helping a user choose among candidate products.

Use the user's request and the provided search results to recommend the best options. Return JSON with:

- `ranked_candidate_ids`: a ranked list of candidate IDs.
- `top_recommendations`: the top 3 candidate IDs.
- `answer`: a concise explanation for the recommendation.
- `citations`: source line citations for important claims you used.

Use only the provided sources.
