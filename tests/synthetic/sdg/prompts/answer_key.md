# Stage 6 — Answer key / grader rubric

From the scenario spec and generated evidence, emit `answer` block fields consistent with tests/synthetic/schemas.py expectations for the synthetic suite.

Include:

- root_cause_category aligned with failure_mode
- required_keywords agents must cite
- forbidden_keywords / forbidden_categories for common wrong paths
- optimal_trajectory tool sequence if applicable
- model_response: concise gold narrative

If running the investigation agent is preferred, use its successful trace to fill optimal_trajectory and validate keywords against generated logs.
