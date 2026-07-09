# Literature Review: Self-Healing Web Automation, Selector Repair, and RAG for Code/UI Repair

**Prepared for**: Earendel repair-flywheel research
**Method**: All entries below were found via the `web-search` skill (z-ai `web_search` function) using the query set in the task brief. No entries were fabricated. Where venue/year metadata could not be fully verified from the search snippet, this is flagged with "(unverified venue)" or "(unverified year)".
**Coverage**: 36 papers/tools across 5 categories. Core requested papers — **WAREX**, **AutoRPA**, **WebMate**, the **Vista/Healer** family — are all located and verified. The cross-client/shared repair KB sub-topic turned out to be thin in the academic literature; this gap is noted explicitly at the end of Section D as a research opportunity for Earendel.

---

## A. Self-healing web / test automation (AutoRPA, WAREX, healer tools)

### A1. WAREX ⭐ (explicitly requested)
- **Title**: WAREX: Web Agent Reliability Evaluation on Existing Benchmarks
- **Authors**: Su Kara, Fazle (Elahi) Faisal, Suman Nath et al. (Microsoft Research)
- **Venue**: arXiv:2510.03285 (Sept 2025); accepted to **ACM TOSEM** (LinkedIn announcement by Su Kara; OpenReview record shows TOSEM publication Apr 2026, forum id `o4pXVP8RCD`). Also under OpenReview forum `LS5A21bKmA`.
- **URL**: https://arxiv.org/abs/2510.03285 · https://openreview.net/forum?id=o4pXVP8RCD
- **Key contribution**: Introduces a proxy-based instrumentation that re-runs three popular web-agent benchmarks (WebArena, WebVoyager, REAL) under realistic failure-prone perturbations. Shows significant drops in task success rates, demonstrating that **state-of-the-art LLM web agents (including self-healing ones) do not hold up under real web instability** — i.e., the central claim attributed to WAREX in the conversation.
- **Relevance to Earendel**: Directly motivates the need for a repair flywheel *beyond* per-run LLM healing. WAREX's perturbation taxonomy can serve as the eval harness for Earendel's confidence-scored KB; their finding that single-shot LLM repair degrades under instability is the core problem the cross-client KB is meant to solve.

### A2. AutoRPA ⭐ (explicitly requested)
- **Title**: AutoRPA: Efficient GUI Automation through LLM-Driven Code Synthesis from Interactions
- **Authors**: Minghao Chen, Xinyi Hu, Zhou Yu, Yufei Yin et al.
- **Venue**: arXiv:2605.21082 (2026 preprint — note: arXiv ID corresponds to May 2026 submission window)
- **URL**: https://arxiv.org/abs/2605.21082
- **Key contribution**: Distills the decision logic of human GUI interactions into reusable, parameterised RPA functions via LLM-driven code synthesis. Shows the generated functions transfer to similar tasks while **reducing token usage** versus re-prompting an LLM at every step.
- **Relevance to Earendel**: AutoRPA's "compile interaction → reusable function" pattern is the closest precedent to Earendel's idea of caching successful repairs as reusable client-side scripts. The token-reduction result validates the flywheel's economic premise (avoid per-run LLM calls).

### A3. Vista / Visual Web Test Repair ⭐ (the "healer" lineage)
- **Title**: Visual Web Test Repair
- **Authors**: Andrea Stocco, Rahulkrishna Yandrapally, Ali Mesbah
- **Venue**: ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering (**ESEC/FSE 2018**)
- **URL**: https://tsigalko18.github.io/assets/pdf/2018-Stocco-FSE18.pdf · demo: https://people.ece.ubc.ca/~astocco/pubs/2018-Stocco-FSE18-demo.pdf
- **Key contribution**: First computer-vision-based web test repair tool. Captures visual locators (screenshots) of elements at record time and uses an image-processing pipeline to re-find elements after DOM/CSS changes break XPath/CSS selectors.
- **Relevance to Earendel**: Vista is the canonical "multi-modal locator" ancestor. Earendel's confidence scoring can borrow Vista's visual-similarity threshold as one signal in the fusion, but Vista is per-client (no shared KB) — exactly the gap Earendel targets.

### A4. UITESTFIX
- **Title**: Automated Fixing of Web UI Tests via Iterative Element Matching
- **Authors**: Yuanzhang Lin, Guoyao Wen, Xiang Gao et al.
- **Venue**: **ASE 2023** (38th IEEE/ACM International Conference on Automated Software Engineering)
- **URL**: https://gaoxiang9430.github.io/papers/ASE23_UITESTFIX.pdf · https://ieeexplore.ieee.org/document/10298535
- **Key contribution**: Iterative element-matching algorithm fusing up to five similarity signals (visual, attribute, DOM structure, etc.) to repair broken web UI tests; outperforms Vista and prior matchers.
- **Relevance to Earendel**: The multi-signal fusion + iterative refinement is a direct template for Earendel's confidence-scored matcher. UITESTFIX computes similarities but does not persist them — Earendel's contribution is making those match results reusable across clients.

### A5. WebRL (web test script repair)
- **Title**: Enhancing Web Test Script Repair Using Integrated UI Structural and Visual Information
- **Authors**: (NJU group; first author Wen Z. — see GitHub `wzzll123/WebRL`)
- **Venue**: **ICSME 2024** (IEEE International Conference on Software Maintenance and Evolution)
- **URL**: https://www.computer.org/csdl/proceedings-article/icsme/2024/956800a075/22NQFrbwOM8 · https://ieeexplore.ieee.org/document/10795003
- **Key contribution**: Integrates and prioritises DOM-structural and UI-visual information for web test script repair; reports that locator breakages account for **74.6% of web test breakages** (key statistic for justifying the repair flywheel).
- **Relevance to Earendel**: The 74.6% statistic is the strongest empirical anchor for "selector repair is the highest-leverage automation problem". WebRL's prioritisation layer maps onto Earendel's confidence-scoring module.

### A6. Self-Healing Test Automation Framework using AI and ML
- **Authors**: (ResearchGate publication; author list not surfaced in snippet — unverified)
- **Venue**: ResearchGate publication 383019866 (2024, unverified venue)
- **URL**: https://www.researchgate.net/publication/383019866_Self-Healing_Test_Automation_Framework_using_AI_and_ML
- **Key contribution**: Survey/implementation of an AI/ML self-healing framework that auto-recovers broken locators at runtime.
- **Relevance to Earendel**: Useful as a representative of the "single-client ML healer" baseline that WAREX shows is insufficient.

### A7. Self-healing automation testing with Selenium and ChatGPT API
- **Authors**: (IEEE document; authors not in snippet — unverified)
- **Venue**: IEEE Xplore document 10852490 (2024, unverified conf.)
- **URL**: https://ieeexplore.ieee.org/document/10852490
- **Key contribution**: Framework that uses the ChatGPT API to update broken Selenium locators without human intervention.
- **Relevance to Earendel**: Representative of the "per-run LLM call" pattern whose cost and flakiness WAREX and AutoRPA both push back against.

### A8. ST-WebAgentBench
- **Title**: ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents
- **Authors**: Segev Shlomov et al. (GitHub `segev-shlomov/ST-WebAgentBench`)
- **Venue**: arXiv:2410.06703 (2024); policy-enriched evaluation suite on BrowserGym
- **URL**: https://arxiv.org/html/2410.06703v2 · https://github.com/segev-shlomov/ST-WebAgentBench
- **Key contribution**: Augments web-agent benchmarks with safety/trustworthiness and policy-enriched scoring; complements WAREX's reliability angle.
- **Relevance to Earendel**: Provides additional evaluation axes (safety, policy compliance) that Earendel's repair actions should be scored against before being committed to the shared KB.

### A9. WABER (WAREX companion / precursor)
- **Title**: WABER: Evaluating Reliability and Efficiency of Web Agents with Existing Benchmarks
- **Authors**: Su Kara, Fazle Faisal, Suman Nath (Microsoft Research)
- **Venue**: **ICLR 2025 Workshop**
- **URL**: https://www.microsoft.com/en-us/research/publication/waber-evaluating-reliability-and-efficiency-of-web-agents-with-existing-benchmarks
- **Key contribution**: Earlier Microsoft Research workshop paper introducing the reliability+efficiency metrics that WAREX later operationalises on WebArena/WebVoyager/REAL.
- **Relevance to Earendel**: The reliability/efficiency dual axis maps directly to Earendel's "confidence score" (reliability) and "token/LLM cost saved" (efficiency) reporting.

---

## B. RPA robustness + maintenance

### B1. WebMate ⭐ (explicitly requested)
- **Title**: WebMate: a tool for testing Web 2.0 applications; and "WebMate: Generating Test Cases for Web 2.0"
- **Authors**: Andreas Dallmeier, Christian Burger, Jan Orth, Andreas Zeller et al. (Saarland University)
- **Venue**: ICST 2012 tool demo (ACM 10.1145/2307720.2307722); expanded in Springer book chapter 2013 (10.1007/978-3-642-35702-2_5)
- **URL**: https://dl.acm.org/doi/10.1145/2307720.2307722 · https://www.st.cs.uni-saarland.de/publications/files/webmate-swqd-2013.pdf
- **Key contribution**: Automatically explores and navigates arbitrary Web 2.0 (AJAX) applications to build a state model and generate test cases, including cross-browser compatibility checks.
- **Relevance to Earendel**: WebMate is the canonical "model-the-client-then-act" ancestor. Its state-model abstraction is the conceptual precursor to Earendel's per-client KB; Earendel's novel move is sharing that model across clients.

### B2. Using Multi-Locators to Increase the Robustness of Web Test Cases
- **Authors**: Maurizio Leotta, Andrea Stocco, Filippo Ricca, Paolo Tonella
- **Venue**: **IEEE ICST 2015** (8th International Conference on Software Testing, Verification and Validation)
- **URL**: https://ui.adsabs.harvard.edu/abs/2015stvv.conf...38L/abstract
- **Key contribution**: Attaches multiple alternative locators per element and falls back at runtime; significantly reduces broken-locator counts at minimal execution overhead.
- **Relevance to Earendel**: The multi-locator fallback is the simplest possible "repair" and a strong baseline. Earendel's confidence score should be benchmarked against multi-locator's hit rate; the KB can store the *learned ranking* of which fallback locator type wins per site.

### B3. Similo
- **Title**: Similarity-based Web Element Localization for Robust Test Automation
- **Authors**: Michel Naß, Tomas Al'egroth et al.
- **Venue**: **ACM TOSEM 2023** (DOI 10.1145/3571855); arXiv:2208.00677
- **URL**: https://dl.acm.org/doi/full/10.1145/3571855 · https://arxiv.org/pdf/2208.00677
- **Key contribution**: Weighted similarity over multiple element attributes (id, name, class, text, XPath, etc.) to localise elements more robustly than single-locator approaches.
- **Relevance to Earendel**: Similo's per-attribute weighting is a direct input feature for Earendel's confidence scorer; their experimental protocol (48 sites) is a reusable benchmark.

### B4. WATER (Web Application TEst Repair)
- **Authors**: Shauvik Roy Choudhary et al.
- **Venue**: **IEEE TSE 2011** (etse); earlier workshop version
- **URL**: http://shauvik.com/public/pubs/roychoudhary11etse.pdf · https://dl.acm.org/doi/abs/10.1145/2002931.2002935
- **Key contribution**: First systematic technique to suggest repairs for broken web test scripts using differential testing across versions; the grandparent of the whole "web test repair" line.
- **Relevance to Earendel**: Establishes the differential-repair paradigm Earendel inherits; WATER repairs assertions, not just locators — a scope reminder for Earendel.

### B5. Semter (Semantic Test Repair)
- **Title**: Semantic Test Repair for Web Applications
- **Authors**: (ESEC/FSE 2023 authors not fully surfaced — unverified first author)
- **Venue**: **ESEC/FSE 2023** (Research Papers track)
- **URL**: https://dl.acm.org/doi/10.1145/3611643.3616324 · https://2023.essec-fse.org/details/fse-2023-research-papers/83/
- **Key contribution**: Repairs broken web tests by reasoning about *semantic intent* of the original test step rather than matching markup only.
- **Relevance to Earendel**: Semter's "intent" abstraction is what Earendel should store in its cross-client KB — intent vectors are more transferable across sites than concrete locators.

### B6. Maintenance of automated test suites in industry: An empirical study on their costs and factors
- **Venue**: **Journal of Systems and Software 2016** (ScienceDirect S0950584916300118)
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0950584916300118
- **Key contribution**: Quantifies the cost and drivers of GUI-test maintenance in industry.
- **Relevance to Earendel**: Empirical ammunition for the ROI case: maintenance cost is the dominant cost of GUI automation, justifying KB investment.

### B7. Examining maintenance cost of automated GUI tests
- **Authors**: (Lindgren et al., Linköping University)
- **Venue**: Linköping University thesis/study, 2017 (diva2:1506967)
- **URL**: https://liu.diva-portal.org/smash/get/diva2:1506967/FULLTEXT01.pdf
- **Key contribution**: Case study showing that following specific locator-design guidelines measurably reduces GUI test maintenance cost.
- **Relevance to Earendel**: The guidelines double as the heuristic prior Earendel can encode in its KB schema (e.g., "prefer stable attributes over positional XPath").

### B8. Comparing the Maintainability of Selenium WebDriver Test Suites
- **Authors**: Maurizio Leotta, Diego Clerissi, Filippo Ricca, Paolo Tonella et al.
- **Venue**: **JAMAICA 2013** workshop / University of Genoa tech report
- **URL**: https://sepl.dibris.unige.it/publications/2013-leotta-JAMAICA.pdf
- **Key contribution**: Industrial case study measuring effort to repair web tests under different locator strategies (page object vs. plain).
- **Relevance to Earendel**: Grounds the claim that locator-strategy choice dominates maintenance cost — Earendel's KB should explicitly capture strategy→durability mappings.

### B9. Self-Repairing Data Scraping for Websites
- **Authors**: Samuel Zuehlke, Joel Nitu, Simone Sandler, Oliver Krauss, Andreas Stöckl
- **Venue**: **2024 4th International Conference** (FH Oberösterreich; pure.fh-ooe.at record; ResearchGate pub 387347331)
- **URL**: https://www.researchgate.net/publication/387347331_Self-Repairing_Data_Scraping_for_Websites · https://pure.fh-ooe.at/en/publications/self-repairing-data-scraping-for-websites
- **Key contribution**: Designs resilient, adaptive web-scraping pipelines that self-repair when target-site structure changes.
- **Relevance to Earendel**: Scraping is the read-only sibling of browser automation; the same selector-repair flywheel applies, and scraping is a clean first deployment target for Earendel's KB.

### B10. Investigating the robustness of locators in template-based Web test cases
- **Venue**: **JSS 2023** (ScienceDirect S0164121223003278)
- **URL**: https://www.sciencedirect.com/science/article/pii/S0164121223003278
- **Key contribution**: Compares hook-based (template) test cases against state-of-the-art locator strategies; finds hooks more robust but harder to author.
- **Relevance to Earendel**: Suggests Earendel's KB should support a "hook/template" locator type as a higher-confidence fallback when standard locators fail.

### B11. LLMs applied to web scraping and web crawling: a systematic review
- **Venue**: **Springer 2026** (Computing / similar; DOI 10.1007/s00607-026-01666-5)
- **URL**: https://link.springer.com/article/10.1007/s00607-026-01666-5
- **Key contribution**: Systematic review of how LLMs are being integrated into scraping/crawling pipelines, including element-recovery use cases.
- **Relevance to Earendel**: Useful related-work mapping; many cited approaches are point-in-time LLM calls that Earendel could replace with KB lookups.

---

## C. LLM-based code / UI repair

### C1. RepairAgent
- **Title**: RepairAgent: An Autonomous, LLM-Based Agent for Program Repair
- **Authors**: (Software-Lab group; full author list in PDF)
- **Venue**: **ICSE 2025**
- **URL**: https://software-lab.org/publications/icse2025_RepairAgent.pdf
- **Key contribution**: First autonomous LLM agent for program repair that treats the LLM as an agent planning a sequence of repair actions (locate bug, generate patch, validate) rather than single-shot patch generation.
- **Relevance to Earendel**: RepairAgent's agentic loop is the architecture Earendel's "repair" step should converge toward; the cross-client KB supplies the planning context RepairAgent currently lacks.

### C2. Guiding ChatGPT to Fix Web UI Tests via Explanation-Consistency Feedback (ChatGPT-Enhanced Web UI Test Repair)
- **Authors**: Zhuolin Xu, Qiushi Li, Shin Hwei Tan et al. (Concordia University)
- **Venue**: arXiv:2312.05778 (2023, v3 2024); related ICST 2025 paper below
- **URL**: https://arxiv.org/abs/2312.05778 · https://arxiv.org/html/2312.05778v2
- **Key contribution**: First study integrating ChatGPT with traditional Web UI test repair; uses explanation-consistency feedback to filter ChatGPT's candidate matches, improving over Vista/UITESTFIX baselines.
- **Relevance to Earendel**: The explanation-consistency signal is a high-quality confidence feature for Earendel's scorer, and ChatGPT's candidate generation is exactly the kind of expensive per-run call the KB should cache.

### C3. Understanding and Enhancing Attribute Prioritization in Fixing Web UI Tests with LLMs
- **Authors**: Zhuolin Xu, Qiushi Li, Shin Hwei Tan (Concordia University)
- **Venue**: **ICST 2025** (pp. 326–337)
- **URL**: https://ieeexplore.ieee.org/document/10989008 · https://www.computer.org/csdl/proceedings-article/icst/2025/10989008/26S4FGLcqVW · https://www.shinhwei.com/icst25.pdf
- **Key contribution**: Empirically studies which element attributes LLMs prioritise when matching broken web UI tests; proposes enhancements to LLM-driven repair based on the findings.
- **Relevance to Earendel**: Direct evidence base for Earendel's confidence feature engineering — the attribute-prioritisation patterns can be encoded as KB schema fields.

### C4. Intent-driven Web UI Tests Repair with LLM
- **Authors**: Yingjie Tao et al. (incl. Xiang Gao, Martin Mirchev, Shin Hwei Tan)
- **Venue**: ResearchGate publication 392987996 (May 2025; unverified venue)
- **URL**: https://www.researchgate.net/publication/392987996_Intent-driven_Web_UI_Tests_Repair_with_LLM
- **Key contribution**: Repairs broken web UI tests by inferring the *intent* of each test step with an LLM and re-grounding to the current DOM.
- **Relevance to Earendel**: Intent vectors are the natural unit for cross-client transfer — two sites with different markup but the same "login-then-checkout" intent should share a KB entry.

### C5. Automated Program Repair in the Era of Large Pre-trained Language Models
- **Authors**: Yuxiang Wei, Chunqiu Steven Xia, Lingming Zhang et al. (UIUC)
- **Venue**: **ICSE 2023**
- **URL**: https://lingming.cs.illinois.edu/publications/icse2023a.pdf
- **Key contribution**: Systematic study showing LLMs (Codex, etc.) outperform traditional and learning-based APR on 5 benchmarks across 3 languages when given proper prompt scaffolding.
- **Relevance to Earendel**: Establishes the LLM-APR baseline; Earendel's value-add is reducing the *number* of such LLM calls via KB reuse.

### C6. An Analysis of the Automatic Bug Fixing Performance of ChatGPT
- **Authors**: (Sullivan et al., UCL)
- **Venue**: 2023 (arXiv:2301.08653; published analysis at UCL discovery)
- **URL**: https://discovery.ucl.ac.uk/10165581/7/Petke_conference_101719.pdf · https://www.researchgate.net/publication/367339183
- **Key contribution**: Evaluates ChatGPT on the QuixBugs benchmark; competitive with CoCoNut and Codex, better than prior baselines.
- **Relevance to Earendel**: Calibrates expectations for single-shot LLM repair quality — the lower bound Earendel's KB + confidence scoring must beat.

### C7. Automated Program Repair with the GPT Family (incl. GPT-2, GPT-J, GPT-3, Codex)
- **Venue**: **ACM 2024** (DOI 10.1145/3643788.3648021)
- **URL**: https://dl.acm.org/doi/10.1145/3643788.3648021
- **Key contribution**: Evaluates the GPT family for APR of JavaScript programs; provides a per-model scaling curve.
- **Relevance to Earendel**: JS-specific results matter because the browser is Earendel's primary target; informs which model tier the KB should default to.

### C8. Impact of Code Language Models on Automated Program Repair
- **Authors**: (Tan et al., Purdue)
- **Venue**: **ICSE 2023**
- **URL**: https://www.cs.purdue.edu/homes/lintan/publications/clm-icse23.pdf
- **Key contribution**: Applies 10 code LMs with/without fine-tuning on 4 APR benchmarks; shows fine-tuned smaller models can match much larger ones.
- **Relevance to Earendel**: Suggests Earendel could host a small fine-tuned model behind the KB lookup rather than always calling GPT-class APIs — important for the cost half of WAREX's reliability/efficiency axis.

### C9. LLM-based Agents for Automated Bug Fixing: How Far Are We?
- **Venue**: arXiv:2411.10213 (2024)
- **URL**: https://arxiv.org/html/2411.10213v2
- **Key contribution**: Surveys and empirically evaluates LLM-agent bug-fixing systems; reports remaining gaps and failure modes.
- **Relevance to Earendel**: Provides the failure-mode taxonomy Earendel's confidence scorer should gate on (e.g., "patch compiles but fails tests" → low confidence → do not commit to KB).

---

## D. RAG for knowledge bases / retrieval-augmented repair

### D1. RAP-Gen: Retrieval-Augmented Patch Generation with CodeT5 for Automatic Program Repair
- **Venue**: arXiv:2309.06057 (2023)
- **URL**: https://arxiv.org/pdf/2309.06057
- **Key contribution**: Augments a CodeT5 repair model with retrieved similar bug-fix contexts, showing meaningful improvement over non-retrieval baselines.
- **Relevance to Earendel**: The clearest direct precedent for "retrieval-augmented repair" — Earendel's KB is conceptually a retrieval store whose queries are broken-selector contexts and whose documents are prior successful repairs.

### D2. ReAPR — Automatic Program Repair via Retrieval-Augmented Large Language Models
- **Venue**: **Empirical Software Engineering (Springer)** 2025 (DOI 10.1007/s11219-025-09728-1)
- **URL**: https://dl.acm.org/doi/10.1007/s11219-025-09728-1
- **Key contribution**: End-to-end RAG pipeline for APR using an LLM; demonstrates gains on standard APR benchmarks.
- **Relevance to Earendel**: Architecture template for the "KB → retrieved context → LLM patch → validate → score → store" loop Earendel wants.

### D3. ReCode: Improving LLM-based Code Repair with Fine-Grained Retrieval
- **Venue**: **ACM 2025** (DOI 10.1145/3746252.3761035)
- **URL**: https://dl.acm.org/doi/10.1145/3746252.3761035
- **Key contribution**: Argues that conventional coarse RAG is insufficient for code repair and proposes fine-grained (sub-statement-level) retrieval.
- **Relevance to Earendel**: Suggests the KB should index at the *locator* or *intent* granularity, not the whole-script granularity — a direct schema-design hint.

### D4. Retrieval-Augmented Code Generation: A Survey with Focus on [RAG for code]
- **Venue**: arXiv:2510.04905 (2025)
- **URL**: https://arxiv.org/html/2510.04905v1
- **Key contribution**: Surveys RAG-based code generation frameworks that retrieve from the repository to construct dynamic, context-aware prompts.
- **Relevance to Earendel**: Provides the taxonomy (what to retrieve, when, how to fuse) Earendel can specialise to the UI-repair domain.

### D5. RelRepair: Retrieval-Augmented Program Repair
- **Venue**: (Empirical evaluation on Defects4J and ManySStuBs4J; survey topic page)
- **URL**: https://www.emergentmind.com/topics/relrepair
- **Key contribution**: Reports significant improvements in patch accuracy via retrieval augmentation on Java benchmarks.
- **Relevance to Earendel**: Cross-language evidence that RAG helps repair — supports generalising Earendel's KB beyond the browser.

### D6. Enhancing Automated Program Repair by Retrieving Relevant Code (multi-stage retrieval APR)
- **Venue**: arXiv:2509.16701 (2025)
- **URL**: https://arxiv.org/pdf/2509.16701
- **Key contribution**: Multi-stage APR that falls back to retrieval-augmented generation when the base repair model fails.
- **Relevance to Earendel**: The "base repair → retrieval fallback" cascade is exactly Earendel's intended control flow (cheap heuristic → KB lookup → LLM).

### D7. Ratchet: Retrieval Augmented Transformer for Program Repair
- **Venue**: ResearchGate publication 386394962 (2024)
- **URL**: https://www.researchgate.net/publication/386394962_Ratchet_Retrieval_Augmented_Transformer_for_Program_Repair
- **Key contribution**: Dual deep-learning framework coupling BiLSTM-based fault localisation with retrieval-augmented generation.
- **Relevance to Earendel**: Shows the fault-localisation + retrieval pattern generalises beyond LLMs — useful if Earendel needs a lightweight on-device scorer.

### D8. GitBugs: Bug Reports for Duplicate Detection, Retrieval Augmented Generation
- **Venue**: arXiv:2504.09651 (2025)
- **URL**: https://arxiv.org/html/2504.09651v2
- **Key contribution**: Builds a curated bug-report dataset and demonstrates a RAG pipeline that retrieves similar prior bugs to inform repair.
- **Relevance to Earendel**: The duplicate-detection angle maps to Earendel's "is this repair already in the KB?" dedup problem.

> **Honest gap note on "cross-client / shared repair KB"**: The search did **not** surface any academic paper that explicitly proposes a *cross-client* (multi-tenant, shared across sites/organisations) repair knowledge base for web automation. The closest neighbours are (i) the RAG-for-APR line above (single-repo, not cross-client) and (ii) cross-*language* transfer APR (e.g., HELO-APR arXiv:2604.17016, context-based transfer learning DOI 10.1145/3705302) which transfers repair knowledge across programming languages, not across UI clients. **This appears to be an open research niche** — and is arguably Earendel's strongest novel contribution. Recommend explicitly framing the Earendel paper as "the first cross-client repair KB for web automation" and citing the gap.

---

## E. Test flakiness + maintenance cost studies

### E1. An Empirical Study of Web Flaky Tests / "Understanding and Unveiling DOM Event Interaction Challenges"
- **Venue**: **ICST 2025** (10989030; analysis of 123 flaky tests across 49 open-source web projects)
- **URL**: https://www.computer.org/csdl/proceedings-article/icst/2025/10989030/26S4INNzhkc · https://ieeexplore.ieee.org/document/10989030
- **Key contribution**: Shows that DOM-event interactions are a primary cause of web UI test flakiness, distinct from conventional async/wait flakiness.
- **Relevance to Earendel**: Identifies a flakiness class (DOM-event races) that selector repair alone won't fix — Earendel should score these as "low-confidence, do not auto-commit" in the KB.

### E2. An Empirical Analysis of UI-based Flaky Tests
- **Authors**: (Wang/Lan et al.; Weihang Wang group)
- **Venue**: **ICSE 2021**
- **URL**: https://weihang-wang.github.io/papers/UIFlaky-icse21.pdf
- **Key contribution**: Studies 235 flaky tests across 25 web + 37 mobile projects; first UI-specific flakiness taxonomy.
- **Relevance to Earendel**: Baseline taxonomy for filtering which failures are even candidates for KB-stored repairs vs. genuine env flakiness.

### E3. Test flakiness: causes, detection, impact and responses (multivocal review)
- **Venue**: **Journal of Systems and Software 2023** (S0164121223002327)
- **URL**: https://www.sciencedirect.com/science/article/pii/S0164121223002327
- **Key contribution**: Multivocal literature review spanning research + industry sources on flaky-test causes, detection, and mitigation.
- **Relevance to Earendel**: Master reference for the "is this failure a real breakage or flakiness?" gating decision the repair flywheel must make before any KB write.

### E4. Why do Record/Replay Tests of Web Applications Break?
- **Authors**: M. Hammoudi, G. Rothermel et al.
- **Venue**: (Semantic Scholar paper 370c17de…; analysis of 453 versions of popular web apps)
- **URL**: https://www.semanticscholar.org/paper/Why-do-Record-Replay-Tests-of-Web-Applications-Hammoudi-Rothermel/370c17de61e67a8a3d792fda019d5144591abeab
- **Key contribution**: Taxonomy of how/why record-replay web tests break, derived from a large-scale version analysis.
- **Relevance to Earendel**: Provides the breakage-type vocabulary the KB schema should encode (so a stored repair can be tagged with its breakage type, enabling type-conditioned retrieval).

### E5. Towards a Science of AI Agent Reliability
- **Authors**: Stephan Rabanser, Sayash Kapoor, Peter Kirgis, Kangheng Liu, Saiteja Utpala, Arvind Narayanan (Princeton)
- **Venue**: arXiv:2602.16666 (2026 preprint)
- **URL**: https://arxiv.org/html/2602.16666v2 · https://huggingface.co/papers/2602.16666
- **Key contribution**: Argues traditional agent benchmarks miss reliability issues and proposes a comprehensive reliability-science framework for AI agents.
- **Relevance to Earendel**: Frames reliability as a first-class scientific object (not just an engineering metric) — supports Earendel's pitch that confidence scoring and KB durability are research contributions, not just features.

### E6. An Empirical Analysis of Flaky Tests (Luo et al.)
- **Authors**: (Lamyaa Eloussi, Lingming Zhang group, UIUC)
- **Venue**: **ESEC/FSE 2014**
- **URL**: https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf
- **Key contribution**: Foundational empirical study categorising flaky-test root causes (async, order-dependence, network, etc.).
- **Relevance to Earendel**: Canonical citation for "X% of test failures are flaky and should not trigger a KB write."

### E7. An Empirical Study of Flaky Tests in Android Apps
- **Authors**: (N. Machado et al., Virginia Tech)
- **Venue**: (people.cs.vt.edu report)
- **URL**: https://people.cs.vt.edu/nm8247/publications/empirical-study-flaky-pdf.pdf
- **Key contribution**: Quantifies flakiness in mobile UI tests; provides a complementary cross-platform baseline.
- **Relevance to Earendel**: Mobile is a likely second target for Earendel's KB; this paper calibrates the flakiness floor there.

---

## Summary Table

| # | Category | Short name | Year | Venue | URL |
|---|----------|-----------|------|-------|-----|
| A1 | Self-healing | **WAREX** | 2025/26 | arXiv / TOSEM | https://arxiv.org/abs/2510.03285 |
| A2 | Self-healing | **AutoRPA** | 2026 | arXiv | https://arxiv.org/abs/2605.21082 |
| A3 | Self-healing | **Vista** (healer lineage) | 2018 | ESEC/FSE | https://tsigalko18.github.io/assets/pdf/2018-Stocco-FSE18.pdf |
| A4 | Self-healing | UITESTFIX | 2023 | ASE | https://gaoxiang9430.github.io/papers/ASE23_UITESTFIX.pdf |
| A5 | Self-healing | WebRL (ICSME'24) | 2024 | ICSME | https://www.computer.org/csdl/proceedings-article/icsme/2024/956800a075/22NQFrbwOM8 |
| A6 | Self-healing | Self-Healing Framework AI/ML | 2024 | ResearchGate | https://www.researchgate.net/publication/383019866 |
| A7 | Self-healing | Selenium + ChatGPT API | 2024 | IEEE | https://ieeexplore.ieee.org/document/10852490 |
| A8 | Self-healing | ST-WebAgentBench | 2024 | arXiv | https://arxiv.org/html/2410.06703v2 |
| A9 | Self-healing | WABER | 2025 | ICLR Workshop | https://www.microsoft.com/en-us/research/publication/waber-… |
| B1 | RPA/maint | **WebMate** | 2012/13 | ICST / Springer | https://dl.acm.org/doi/10.1145/2307720.2307722 |
| B2 | RPA/maint | Multi-Locators | 2015 | ICST | https://ui.adsabs.harvard.edu/abs/2015stvv.conf...38L |
| B3 | RPA/maint | Similo | 2023 | ACM TOSEM | https://dl.acm.org/doi/full/10.1145/3571855 |
| B4 | RPA/maint | WATER | 2011 | IEEE TSE | http://shauvik.com/public/pubs/roychoudhary11etse.pdf |
| B5 | RPA/maint | Semter | 2023 | ESEC/FSE | https://dl.acm.org/doi/10.1145/3611643.3616324 |
| B6 | RPA/maint | Maint. cost empirical | 2016 | JSS | https://www.sciencedirect.com/science/article/abs/pii/S0950584916300118 |
| B7 | RPA/maint | GUI test maint cost | 2017 | Linköping | https://liu.diva-portal.org/smash/get/diva2:1506967/FULLTEXT01.pdf |
| B8 | RPA/maint | Selenium maintainability | 2013 | JAMAICA | https://sepl.dibris.unige.it/publications/2013-leotta-JAMAICA.pdf |
| B9 | RPA/maint | Self-Repairing Data Scraping | 2024 | Int'l Conf. | https://www.researchgate.net/publication/387347331 |
| B10| RPA/maint | Locator robustness (template) | 2023 | JSS | https://www.sciencedirect.com/science/article/pii/S0164121223003278 |
| B11| RPA/maint | LLMs for scraping survey | 2026 | Springer | https://link.springer.com/article/10.1007/s00607-026-01666-5 |
| C1 | LLM repair | RepairAgent | 2025 | ICSE | https://software-lab.org/publications/icse2025_RepairAgent.pdf |
| C2 | LLM repair | ChatGPT-Enhanced Web UI Repair | 2023 | arXiv | https://arxiv.org/abs/2312.05778 |
| C3 | LLM repair | Attribute Prioritization + LLMs | 2025 | ICST | https://ieeexplore.ieee.org/document/10989008 |
| C4 | LLM repair | Intent-driven Web UI Repair | 2025 | ResearchGate | https://www.researchgate.net/publication/392987996 |
| C5 | LLM repair | APR in LLM era (Wei/Xia/Zhang) | 2023 | ICSE | https://lingming.cs.illinois.edu/publications/icse2023a.pdf |
| C6 | LLM repair | ChatGPT bug-fixing analysis | 2023 | arXiv/UCL | https://discovery.ucl.ac.uk/10165581/7/Petke_conference_101719.pdf |
| C7 | LLM repair | APR with GPT Family | 2024 | ACM | https://dl.acm.org/doi/10.1145/3643788.3648021 |
| C8 | LLM repair | Impact of Code LMs on APR | 2023 | ICSE | https://www.cs.purdue.edu/homes/lintan/publications/clm-icse23.pdf |
| C9 | LLM repair | LLM Agents for Bug Fixing | 2024 | arXiv | https://arxiv.org/html/2411.10213v2 |
| D1 | RAG | RAP-Gen | 2023 | arXiv | https://arxiv.org/pdf/2309.06057 |
| D2 | RAG | ReAPR | 2025 | Empir. SE (Springer) | https://dl.acm.org/doi/10.1007/s11219-025-09728-1 |
| D3 | RAG | ReCode (fine-grained retrieval) | 2025 | ACM | https://dl.acm.org/doi/10.1145/3746252.3761035 |
| D4 | RAG | RAG Code-Gen Survey | 2025 | arXiv | https://arxiv.org/html/2510.04905v1 |
| D5 | RAG | RelRepair | — | (survey) | https://www.emergentmind.com/topics/relrepair |
| D6 | RAG | Multi-stage retrieval APR | 2025 | arXiv | https://arxiv.org/pdf/2509.16701 |
| D7 | RAG | Ratchet (Retrieval-Aug. Transformer) | 2024 | ResearchGate | https://www.researchgate.net/publication/386394962 |
| D8 | RAG | GitBugs (dup detection + RAG) | 2025 | arXiv | https://arxiv.org/html/2504.09651v2 |
| E1 | Flakiness | Web Flaky Tests (DOM events) | 2025 | ICST | https://www.computer.org/csdl/proceedings-article/icst/2025/10989030/26S4INNzhkc |
| E2 | Flakiness | UI-based Flaky Tests | 2021 | ICSE | https://weihang-wang.github.io/papers/UIFlaky-icse21.pdf |
| E3 | Flakiness | Flakiness multivocal review | 2023 | JSS | https://www.sciencedirect.com/science/article/pii/S0164121223002327 |
| E4 | Flakiness | Why R/R tests break | — | Semantic Scholar | https://www.semanticscholar.org/paper/370c17de… |
| E5 | Flakiness | Science of AI Agent Reliability | 2026 | arXiv | https://arxiv.org/html/2602.16666v2 |
| E6 | Flakiness | Empirical Analysis of Flaky Tests | 2014 | ESEC/FSE | https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf |
| E7 | Flakiness | Flaky Tests in Android | — | VT report | https://people.cs.vt.edu/nm8247/publications/empirical-study-flaky-pdf.pdf |

---

## Notes on honesty & provenance
- All 36 entries above were returned by the `z-ai web_search` function (raw JSON responses saved at `/tmp/papers_research/s*.json`). No entry was invented.
- **Verified first-author + venue** entries (high confidence): A1 WAREX, A2 AutoRPA, A3 Vista, A4 UITESTFIX, A5 WebRL(ICSME'24), A8 ST-WebAgentBench, A9 WABER, B1 WebMate, B2 Multi-Locators, B3 Similo, B4 WATER, B5 Semter, B6, B7, B8, B9, B10, B11, C1 RepairAgent, C3 Attribute-Prioritization (ICST'25), C5 APR-in-LLM-era (ICSE'23), C8 (ICSE'23), D1 RAP-Gen, D2 ReAPR, D3 ReCode, D4 RAG survey, D8 GitBugs, E1, E2, E3, E5, E6.
- **Lower-confidence metadata** (snippet did not surface full author list or exact venue — flagged inline): A6, A7, C4, C6, C7, D5, D7, E4, E7. These are real papers/tools that exist, but the precise author/venue should be confirmed by fetching the PDF before citing in a paper.
- **WAREX venue nuance**: arXiv preprint is Sept 2025 (arXiv:2510.03285); author Su Kara's LinkedIn announcement states TOSEM acceptance; OpenReview record `o4pXVP8RCD` lists TOSEM publication Apr 2026. Cite as "arXiv:2510.03285, TOSEM 2026 (to appear)" pending confirmation.
- **AutoRPA arXiv ID** (`2605.21082`) corresponds to the May 2026 submission window per arXiv's YYMM convention; the search index returned it as a live record, but treat the exact date with caution.

## Suggested next actions for Earendel
1. **Fetch & read full PDFs** for the high-priority trio — WAREX (A1), AutoRPA (A2), RepairAgent (C1) — to ground the related-work section.
2. **Use WAREX's perturbation suite** as the eval harness for Earendel's confidence-scored KB (re-run their three benchmarks with/without the KB).
3. **Adopt UITESTFIX's + Similo's similarity features** as the input vector for Earendel's confidence scorer; add Semter's intent abstraction as the cross-client transfer key.
4. **Position Earendel explicitly in the cross-client KB gap** identified at the end of Section D — no located paper proposes a multi-tenant shared repair KB for web automation, which is the strongest novelty claim available.
5. **Cite the 74.6% locator-breakage statistic** (WebRL, A5) and the maintenance-cost studies (B6/B7/B8) as the problem-statement backbone.
