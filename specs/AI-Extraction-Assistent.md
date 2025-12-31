# AI Hex Grid Extraction Expert
Extracting the tubercles (nodes) from our fish scale images with image processing technquies is a challenging tasks.
To this end we have implemented a number of algorithems with parameters that adjust their actions, also gathered into profiles,
see the section at the end for a current comprehensive list.

The desired outcome is to have the tubercles arranged in a hex-like grid, with uniform spaceing, and each tubercle having around 5-7 neihbors,
this is the pattern observed in nature. Different Fish species can be identified as they have characterist tubercle diamgeters and grid spacing.

## Challenges
This space of parameters is very large, and we have found it difficult to actually get satisfactory results.
The vast number of setting either yield far too many or occasionally too few.
While it is acceptable to have some gaps or false nodes that can be manually corrected later, our preliminary results from manual selection have not been even good enough for that.
it seems clear that our main problem is a poor selection of parmaters
Exploring the entire space of parameters is not feasible, what is needed is a selection of parameters from an expert.

## AI Assistant
Thus we would like to have an AI assistant explore our space. While we do not know if VLMs have a good understanding of these parameters, we
will start by assuming it does. If that fails, a possible next step might be to train a local VLM to be specialized on this.

> **[OPEN QUESTION 1: VLM Parameter Understanding]**
> Do VLMs understand the causal relationship between image processing parameters (CLAHE clip, LoG threshold, blur sigma) and their visual effects? This is not typical training data for general-purpose VLMs.
>
> **Feasibility estimate: 40-55%** - VLMs may have surface knowledge from papers/docs but lack deep causal understanding of how threshold=0.05 vs threshold=0.08 affects blob detection visually.

> **[OPEN QUESTION 2: Comparison with Existing Agent]**
> We already have a working agent (fish-scale-agent) that uses a different approach: VLM directly adds individual tubercles via visual analysis rather than tuning parameters. How does this proposal relate to/replace that system?
>
> **Alternative to consider:** The existing Phase 2 approach (VLM visually places tubercles) may be more reliable since VLMs are good at "I see a tubercle there" but potentially bad at "threshold 0.07 will detect that."

### Hilevel overall workflow
- Iterate to find detection methods and paramters so that we detect the overall hexagonal grid pattern in our sample.
- There should not be too many false positives or false negatives.
- In a second step we will go through and delete any obvious extra nodes, and add obvilusly missing ones
- Then we can determine the measurement values that pin down our fish.

### Parameter Optimizatinon details
- There are two participants, a python deterministic contoller, and a VLM assistent.
- The VLM assistent will be a configurable VLM model reachable over OpenRouter.
- 1st Iteration and Session Start
    - a summary of the task (using image detection to find the location of the tuberlces and their neihbors),
    - Addition detals like available parametes, some examples of how this has worked in the past, what a typical answer needs to look like (formating and paramters)
    - "Lessons learned" from past effors, are also included
    - A maximum number of iterations is communicated
    - Finally the current image makes up the main portion of the prompt
    - An initial estimate of what parameters should first be tried is asked for

    - The return value is a - or even multiple sets - of suggested parameters to try.

> **[OPEN QUESTION 3: Initial Parameter Suggestion]**
> On first iteration, the VLM has never seen this specific image's characteristics. How does it suggest meaningful parameters without seeing any detection results first?
>
> **Suggestion:** Consider a "blind" first extraction with default/conservative params, then VLM sees results and iterates. This gives VLM visual feedback from iteration 1.

- When the repsonse comes back, the contoller applies those values to the image

- 2st Iteration - Controler to VLM
    - The image (or images in the case that multiple sets were requested) is overlaid with the nodes found, made smaller (to reduce tokens since the original image has already and the results are sent back
    - The VLM is asked to judge the results with a numerical score (10 perfect, 0 very bad), and either suggest another set of parameters to try, or say it is done.

    - The return value is a set of suggested values to try or a stop message

> **[OPEN QUESTION 4: Image Downscaling]**
> How small can the overlay image be while still allowing the VLM to assess individual tubercles? If scaled too aggressively, VLM can't see whether detections are accurate.
>
> **Feasibility estimate: 65-75%** for scoring. VLMs are reasonably good at pattern assessment ("too clustered", "big gaps") even at lower resolution, but may struggle with precise "is this circle on a real tubercle?" assessment.

> **[OPEN QUESTION 5: Scoring Consistency]**
> Will VLM scoring be consistent across iterations? Different context = different scores for similar results. The VLM might score 6/10 on iteration 2 then 8/10 for worse results on iteration 5 due to context drift.
>
> **Mitigation:** Include a reference "score anchor" in each prompt (e.g., "a perfect result looks like X").

- When the repsonse comes back, the contoller either
    - applies those values to the image, and starts a Nth iteration identical to the 2nd Iteration
    - If the VLM says it can't do any better, it sets the values to the parameter set with the highst score and terminates
    - If the maximum number of iterations has been met, it sets the values to the parameter set with the highst score and terminates

> **[OPEN QUESTION 6: Convergence Behavior]**
> Will the VLM's parameter suggestions actually converge toward better results, or oscillate/random-walk? The parameter space has complex non-linear interactions (threshold × blur × CLAHE).
>
> **Feasibility estimate: 50-60%** for convergence. VLM may struggle to reason "last time threshold 0.08 gave too few, 0.04 gave too many, so try 0.06" systematically.
>
> **Alternative:** Controller could use the VLM's qualitative feedback ("too many detections") and apply a deterministic step (threshold += 0.02), rather than asking VLM for specific numbers.

- A running tall of consumed input and output tokens as well as estimated cost and elapsed time should be visible in a status line torwards the top of the application

- Finally the LLM is queried as to what lessons it learned that should be added to the "Lessons Learned" section for next time. Thse are added.

> **[OPEN QUESTION 7: Lessons Learned Quality]**
> Will accumulated lessons actually help, or become noise/contradictions over time? No mechanism for pruning bad lessons.
>
> **Feasibility estimate: 50-65%** - Good idea in principle, but needs:
> - Validation mechanism (did the lesson actually help?)
> - Curation (remove contradictory/outdated lessons)
> - Context awareness (lessons from Polypterus may not apply to Lepisosteus)

- Queries for total input and output tokens, total costs are calcuated.
- A session-record-image (an single image composed of multiple images containing all the images and nodes found as well as the parameters tried) will be recorded and placed in a subfolder
- A jsonl log of the session will also be saved in that subfolder, with a reference to the session-record-image

> **[POSITIVE: Good Diagnostics]**
> The session record image and JSONL logging are excellent for debugging and understanding what worked/failed. This will be valuable for tuning the system.
   

## Detection Methods, Parameters, and Profiles
 Detection Methods

  - LoG (Laplacian of Gaussian) � Detects bright circular spots; best for most images (default)
  - DoG (Difference of Gaussian) � Faster approximation of LoG; best for large images where speed matters
  - Ellipse � Threshold segmentation with ellipse fitting; best for high-contrast images
  - Lattice � Hexagonal lattice-aware detection; best for regularly arranged tubercles

  Detection Parameters

  - Threshold (0.01�0.50, default: 0.05) � Detection sensitivity for blob detection
    - Lower (0.01�0.03): More sensitive, may include noise
    - Medium (0.04�0.08): Balanced for most images
    - Higher (0.10�0.20): Only strong features, may miss faint tubercles
  - Min Diameter (0.5�20.0 �m, default: 2.0 �m) � Minimum expected tubercle diameter; smaller blobs are filtered out
  - Max Diameter (1.0�50.0 �m, default: 10.0 �m) � Maximum expected tubercle diameter; larger blobs are filtered out
  - Circularity (0.0�1.0, default: 0.5) � Minimum circularity filter (1.0 = perfect circle, 0.0 = any shape)
    - 0.0�0.3: Accept elongated/irregular shapes
    - 0.4�0.6: Roughly circular shapes (recommended)
    - 0.7�1.0: Only near-perfect circles

  Preprocessing Parameters

  - CLAHE Clip Limit (0.01�0.20, default: 0.03) � Controls contrast amplification for adaptive histogram equalization
    - Lower (0.01�0.02): Subtle enhancement
    - Medium (0.03�0.05): Standard enhancement
    - Higher (0.08�0.15): Strong enhancement for low-contrast images
  - CLAHE Kernel Size (4�32, default: 8) � Size of contextual region for adaptive histogram equalization
    - Smaller (4�6): More local contrast, may enhance noise
    - Medium (8�12): Balanced local/global contrast
    - Larger (16�32): More global effect, smoother result
  - Blur Sigma (0.0�5.0, default: 1.0) � Standard deviation for Gaussian blur (noise reduction)
    - 0.0: No blur
    - 0.5�1.0: Light smoothing (recommended)
    - 1.5�2.5: Moderate smoothing for noisy images
    - 3.0+: Heavy smoothing, may merge nearby features

  Neighbor Graph Types

  - Delaunay � Full Delaunay triangulation; most edges
  - Gabriel � Gabriel graph; removes edges with points inside diameter circle; moderate edges
  - RNG (Relative Neighborhood Graph) � Only natural neighbors; fewest edges (recommended for spacing measurements)

  Preset Profiles

  - default – General-purpose parameters for most images
  - paralepidosteus – Large tubercles (5–15 µm), wide spacing
  - lepisosteus – Medium tubercles (3–8 µm), close spacing
  - polypterus – Small tubercles (1.5–4 µm), wide spacing
  - high-contrast – High-quality images with clear boundaries
  - low-contrast – Noisy images with unclear boundaries
  - scanned-pdf – Images extracted from scanned PDF documents

---

## Overall Feasibility Assessment

### Summary of Open Questions

| # | Question | Feasibility | Risk Level |
|---|----------|-------------|------------|
| 1 | VLM parameter understanding | 40-55% | HIGH |
| 2 | Relation to existing agent | N/A | DESIGN |
| 3 | Cold-start parameter suggestion | 60% | MEDIUM |
| 4 | Image downscaling for scoring | 65-75% | MEDIUM |
| 5 | Scoring consistency | 55-65% | MEDIUM |
| 6 | Convergence behavior | 50-60% | HIGH |
| 7 | Lessons learned quality | 50-65% | MEDIUM |

### Overall Probability of Success

**55-65% chance of being "useful enough"** – defined as producing results that require less manual correction than current approaches.

### Reasons for Optimism
- VLMs excel at visual pattern assessment (hexagonal grid, gaps, clusters)
- The iterative feedback loop is well-designed
- Session logging enables debugging and improvement
- Score-tracking ensures best result is kept even if VLM oscillates
- OpenRouter gives access to many models to find what works

### Reasons for Skepticism
- **Core assumption is unproven:** VLMs may not understand parameter→visual effect mapping
- **Complex parameter interactions:** 9 parameters with non-linear interactions is a difficult optimization space
- **Existing agent may be superior:** Direct tubercle placement (current Phase 2) leverages VLM strengths (visual recognition) rather than weaknesses (numerical optimization)
- **Cost concerns:** Each iteration requires vision tokens; 10+ iterations × multiple test images = significant cost
- **Convergence not guaranteed:** May oscillate or get stuck without gradient-like reasoning

### Recommended Hybrid Approach

Consider combining this proposal's strengths with the existing agent:

1. **Use VLM for qualitative feedback only:**
   - VLM reports: "too many false positives", "missing tubercles in corners", "spacing looks good"
   - Controller applies deterministic parameter adjustments based on feedback type

2. **Profile-first approach:**
   - VLM selects most appropriate profile from existing set (paralepidosteus, polypterus, etc.)
   - Then fine-tunes 1-2 parameters rather than full parameter space

3. **Fallback to direct placement:**
   - If parameter optimization fails after N iterations, switch to existing Phase 2 (VLM adds individual tubercles)
   - This provides a reliable backup

4. **A/B testing:**
   - Run both approaches on test images
   - Compare: iterations needed, final accuracy, cost, manual corrections required

### Minimum Viable Test

Before full implementation, test the core assumption with a quick experiment:

1. Take 3 diverse images with known good parameters
2. Show VLM the image + current detection results
3. Ask: "Detection found 45 tubercles. The threshold is 0.08. To get better results, should threshold be higher or lower?"
4. Check if VLM reasoning aligns with ground truth

If VLM can't reliably answer this directional question, the full system is unlikely to work.