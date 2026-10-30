# Person B: scope, reasoning and presentation guide

Reviewed on 31 October 2026 against the friend's task split, the current shared Canva proposal, the course project briefing and the implemented evidence on `main` at `c730653`.

**Assessment: the implemented July-August analysis is a defensible inspection screen. The full Person B checklist remains partly complete.** Numerical reproducibility, completeness of the checklist and proof of physical degradation are separate questions. The [integration review](review_2026-10-31.md) establishes the first within its stated scope. This guide explains the other two and the presentation narrative. It adds no new modelling or result.

## 1. Start with the building decision

The intended user is a facilities manager who needs to decide which zones to inspect first and which records or site measurements to check. Our question is: which zones show unusual AC operation or recorded indoor conditions under reasonably comparable circumstances, and how much confidence should the manager place in each lead?

The official course briefing, *IS4001 Project Briefing - CU-BEMS Smart Building Energy Data.pptx*, slides 4, 6 and 8, prioritises a meaningful question, transparent quality checks, fair comparisons, useful action and a measurable KPI. It makes ML optional. The friend's AI-generated checklist is a working plan rather than evidence that every proposed algorithm is compulsory or physically valid. The briefing allows refinement of the project direction after proposal feedback. This pass read the current Canva text and its two visible comments, but it does not establish that all lecturer feedback has been captured.

## 2. Check the measurements before naming the outcome

**Electrical use:** daily energy is the sum of valid minute kW readings divided by 60, in kWh. Greater energy can reflect a longer operating schedule, higher load or a changed operating mode. Cooling efficiency also requires delivered cooling output. That output is unavailable here, so an electrical departure cannot by itself establish efficiency loss. [PNNL cooling-efficiency definition](https://basc.pnnl.gov/resource-guides/air-conditioning)

**Cooling response:** a room-temperature slope after startup measures the recorded room's response. Initial temperature, thermal storage, surrounding spaces, heat gains and controls also affect it. Comparable initial/operating conditions are required before interpreting a slower slope as declining performance. The implemented common-support check found insufficient overlap for a fair adjusted comparison in every zone. That is a valid withheld result, while a reliable monthly deterioration trend remains unavailable.

**Humidity:** `w_out - w_in`, in g/kg dry air, describes an outdoor-to-indoor humidity-ratio gap. Indoor moisture also depends on ventilation/infiltration, internal sources, other spaces and material exchange. A gap can support an AC investigation when conditions are matched. It cannot isolate AC removal. [EnergyPlus zone moisture balance](https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/2.4-moisture-predictor-corrector.html)

A coil-side removal rate would require airflow and the coil inlet/outlet humidity-ratio difference, with a suitable air/water balance and allowance for transient storage or re-evaporation. Those inputs are unavailable. The current comparisons therefore model recorded indoor humidity ratio during sustained AC operation, controlling for outdoor moisture and other available context. The legacy helper name `moisture_removal_gkg` is retained for compatibility and must be labelled as a proxy in presentation material. [EnergyPlus cooling-coil reference](https://energyplus.readthedocs.io/en/stable/guides/engineering-reference/15.2-coils.html)

**CUSUM:** a cumulative residual trace is useful descriptively. A decision rule additionally needs a defensible reference, a shift definition, decision limits and false-alarm/detection assessment. The saved F3-Z1 trace has no validated fault threshold. Gaps and unsupported conditions must remain visible. [NIST CUSUM design guidance](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm)

## 3. Map the friend's checklist to actual work

| Requested item | Current status | Evidence and practical boundary |
|---|---|---|
| Weather-normalised daily energy and residuals | Implemented for eligible July-August comparisons | `bq2_ac.ipynb`, `outputs/bq2-zone-screen/model_summary.csv` and `predictions.csv`. Models use weather plus plug-load context. Some references fail to improve on a simple benchmark and remain explicitly weaker evidence. |
| CUSUM | Exploratory F3-Z1 trace only | `outputs/f3z1-first-pass/cusum_available_days.csv`. No validated alarm, all-zone CUSUM assessment or progressive-failure claim is complete. |
| Pull-down rate after startup, tracked over time | Feature extraction and comparability assessment implemented; adjusted result withheld | Startups have continuity/coverage checks. No zone passes the adjusted comparison gates. An interpretable deterioration trend is unavailable. |
| Moisture while AC runs | Implemented as a supporting humidity indicator | `steady_on_features.csv` contains the humidity gap. Models use indoor humidity ratio with outdoor context after sustained operation. This provides no measured coil-removal rate. |
| Peer comparison against similar zones | Descriptive context only | `outputs/bq2-case-investigation/peer_context.csv`. Peers differ in meter configuration, operation and data coverage. Controlled peer benchmarking/ranking remains pending. |
| 2018 versus 2019 like-for-like comparison | Implemented within July-August and supported predictor conditions | Same calendar months, inferred working days, separate input versions, 2018 fitting and supported 2019 evaluation. This is not a full-year or multi-season comparison. |
| Joint F3-Z1 cross-check | B-side evidence available; joint attribution remains unresolved | Supported energy and recorded moisture departures are lower. Track A is still needed for the environmental/exposure interpretation. No envelope or sensor fault is established. |
| Final risk matrix | Planned joint deliverable | `inspection_shortlist.csv` retains 20 zone keys and statuses. The final AC handover schema and joint matrix have not been produced. |

Do not describe Person B as fully complete just because the current notebooks execute or the five implementation PRs were merged. State which outputs are implemented, unavailable under the quality rules, exploratory or still pending.

## 4. Explain the data-to-finding path

| Step | What happened | Reason and presentation evidence |
|---|---|---|
| Source collection | The original researchers collected CU-BEMS building telemetry. The project uses 14 floor/year CSVs for July 2018-December 2019. | These are existing observations. Lwin's contribution does not include installing sensors or collecting new site measurements. Sources: `data/`, original dataset citation. |
| Weather augmentation | The upstream baseline loader obtains hourly Bangkok ERA5 temperature, RH, dew point and rainfall through Open-Meteo and keeps a cache. Track B reuses that cache. | Adds outdoor context. Regional reanalysis is not an on-site station, and matching timestamp keys does not verify the building clock. Source: `baseline/humidity_risk_baseline.py`, `baseline/data/`. |
| Upstream cleaning | Reused the committed cleaning notebook/exports: date alignment, logged invalid readings, short-gap interpolation and long-gap preservation. | Explain shared preprocessing separately from the additional Track B audit. The upstream F5-Z1 supply-air placement explanation remains a hypothesis. Sources: `data-cleaning/main.ipynb`, quality/removal logs. |
| Zone selection | Floors 3-7, zones 1, 2, 4 and 5 give 20 zones. Floor 1 lacks environmental sensors, zone 3 lacks sensors, and Floor 2 has a different layout. | The agreed scope supports joint electrical/environmental comparison. QA checks still determine eligibility separately by metric. |
| Time selection | Used July-August 2018 as reference and July-August 2019 as evaluation. | Environmental outages limit other seasonal overlap. The same months reduce one source of seasonal mismatch. They do not establish year-round behaviour or a known healthy baseline. |
| Quality and input variants | Compared existing cleaned readings with present source values unchanged by cleaning. Replaced/filled values are absent from the second version. | This separates dependence on interpolation and cohort selection. It is a sensitivity check using overlapping evidence. Sources: input audit, channel-quality and cohort tables. |
| Daily energy eligibility | Required all 1,440 valid AC-plus-plug minutes, summed every AC channel assigned to the zone, and used inferred working days. | Avoids unknown-energy gaps and partial-day scaling. The strict rule is conservative and can discard days despite high overall coverage. Day labels are activity proxies, not measured occupancy. |
| Environmental/event eligibility | Required valid continuous power and environmental windows. Startup slopes use 60 minutes; steady-on moisture requires at least 120 continuous AC-on minutes ending at the hour's last minute. | Avoids bridging gaps or comparing startup transients with sustained operation. The AC-on threshold is an empirical power rule, not measured controller status. |
| Reference modelling | Compared temperature-plus-plug and enthalpy-plus-plug specifications using time-separated 2018 validation, with simple reference benchmarks. | Freeze the selected specification before 2019 evaluation. Selection-stage validation and nominal conditional intervals do not constitute independent fault validation. |
| Supported comparison | Retained 2019 conditions represented in the 2018 predictor support, balanced days, and used calendar-week bootstrap sensitivity. | Avoids silently extrapolating to unsupported conditions. Minimum days/weeks and support rules are project choices, not universal engineering standards. |
| Case investigation | Checked schedules, on-time/on-power accounting, matched states, long near-zero-power controls, monthly persistence and sensor scenarios. | Separates recorded changes from possible mechanisms. The cases are selected leads rather than an unbiased prevalence estimate of building faults. |
| Recommendation | Prioritise sensor/meter/controls and site-record checks for the identified cases. | The evidence supports investigation priorities. It supplies no verified repair outcome or recoverable-energy estimate. |

Rainfall is available in the shared weather source. The current Track B energy models use temperature or enthalpy with plug activity rather than a direct rainfall coefficient. Rainfall/lag/seasonal humidity analysis remains primarily Track A's scope. Do not imply every weather variable was used as a model predictor.

## 5. Findings to explain in the presentation

| Case | Observation | What it supports | What remains unknown |
|---|---|---|---|
| F3-Z1 | Supported energy departures are −9.0%/−10.2%, with recorded indoor moisture about −0.40/−0.41 g/kg. Descriptive sustained-on RH rises while temperature falls. | An RH rise alone does not demonstrate an increase in absolute moisture or loss of AC dehumidification in the matched July-August comparison. | Sensor continuity, controls and the envelope are unresolved. Lower energy does not prove better efficiency. |
| F3-Z4 | Screen energy is +13.3%/+15.2%. On-time and on-power rise, with fewer low-power periods inside usual business-hour windows. | A changed metered operating pattern merits a controls/load/schedule review. | Cooler readings persist in long inactive controls, so neither actual overcooling nor mechanical degradation is established. |
| F5-Z4 | On-power rises about 15.1 to 20.1 kW, with runtime near 7.45 hours/day. About 99% of the raw energy difference is an on-power accounting contribution. | Investigate electrical loading, controls, equipment changes and metering. | Weather-reference validation is weak. The +33.0% raw/mean-only comparison differs from the +36.7% weather-reference estimate. |
| F7-Z2 | Matched sustained-on moisture rises about 1.15/1.16 g/kg with little power change. The pattern appears in both July and August. | Joint sensor, ventilation/moisture-load, controls and AC checks are warranted. | Opposing year-specific nominal sensor-error scenarios can erase the absolute moisture difference. No progressive failure or physical dehumidification loss is established. |

Slash-separated figures give the fills-allowed and observed-only versions in that order. The F7-Z2 screen uses a separate cohort and gives +1.15/+1.14 g/kg. Keep the screen and focused-match cohorts distinct when labelling charts.

Use [the report's energy chart](figures/energy_contributions.png) to distinguish time and power contributions, [operating profiles](figures/operating_profiles.png) for descriptive context, and the [20-zone comparison](../../outputs/bq2-zone-screen/zone_comparison.png) with its weak-reference and unavailable-result cautions. The full [report](track_b_report.md) owns the detailed results and limitations.

## 6. Update the older proposal claims before presenting

The shared Canva proposal, design `DAHW9_ykerw`, still contains ambitions that exceed the measurements. This review read it without editing the group deck. The reviewed visible comments do not constitute lecturer approval of these claims.

| Proposal idea | Evidence-based treatment |
|---|---|
| Active AC kW per degree as cooling efficiency | Explain weather/activity-adjusted energy departures and operating indicators. Neither a room/outdoor temperature denominator nor kWh per cooling-degree-hour measures delivered cooling or COP. |
| Year-on-year extra power as efficiency decay | Report the electrical departure and competing operating/load/meter explanations. |
| Measured occupied/unoccupied segmentation | Label states as inferred activity, working-day labels or power-defined operation. |
| Refrigerant/drain leak diagnosis | Leave as a possible site investigation requiring additional records or measurements. |
| A real-time anomaly engine | Describe the implemented historical analysis. No live data feed or deployed alert engine exists. |
| Exact remaining useful life or a 30-day failure warning | Remove from achieved results. No dated failure/maintenance outcomes support training or validating these predictions. |
| Guaranteed 10% energy improvement | Present a proposed trial KPI with a validated reference and indoor-condition safeguards. No intervention or measured saving has occurred. |
| A finished composite risk score or 50% fewer high-risk zones | Leave pending Track A, an agreed matrix/score definition and measured post-action outcomes. |
| A validated 24-48-hour humidity forecast | Keep as an optional separate task requiring time-based evaluation and forecast-available inputs. It is not implemented in the current Track B work. |

The proposal can evolve as quality checks reveal what the data supports. Preserve that explanation in the presentation so methodological restraint is visible rather than appearing as an unexplained missing feature.

## 7. Presentation sequence

Timing for Lwin's individual section has not been assigned in this guide. These are speaking beats that can be combined to fit the group's 20-minute presentation, not a request to create eight new slides.

1. **Decision:** identify zones worth inspecting and distinguish evidence quality from physical cause.
2. **Data and ownership:** explain CU-BEMS, the weather cache and the shared cleaning work, then identify the additional Track B audit/modelling contribution.
3. **Scope and filtering:** show why these 20 zones and July-August were selected, how missingness affects cohorts, and why there are two input versions.
4. **Fair comparison:** explain the 2018 reference, 2019 evaluation, simple benchmarks and support gates in plain language. One residual means recorded energy minus expected energy under available conditions.
5. **Findings:** use the shortlist and two report charts to distinguish F3-Z4's more continuous operation, F5-Z4's higher on-power and F7-Z2's moisture lead. Add F3-Z1 as the example showing why RH alone can mislead.
6. **Evidence limits:** state the unavailable cooling comparison, weak references, sensor uncertainty and unmeasured operating causes alongside the affected results.
7. **Action and measurement:** specify which site checks should happen first and which matched follow-up measures would judge a later intervention.
8. **Handover:** explain what Person B supplies to Person A, what the joint matrix still needs, and which requested analyses remain exploratory or pending.

Suggested opening: "Our role was to check whether AC behaviour changed under comparable conditions and identify where an inspection would be useful. We first checked the data, then compared eligible periods and investigated the strongest leads."

Suggested closing: "The clearest findings are changes in operating pattern, electrical loading and recorded moisture. They support targeted checks. The available records do not establish a particular mechanical fault, so we recommend verifying the measurements and operating conditions before deciding on maintenance."

## 8. Proposed follow-up KPIs

These are measurement proposals. No target below is an achieved result, and no site intervention has been evaluated.

| KPI | Definition and use | Safeguard |
|---|---|---|
| Reference-adjusted energy departure | `100 × sum(actual kWh - expected kWh) / sum(expected kWh)` over eligible supported days using a suitable frozen reference. Compare verified pre/post or matched control periods if a trial is later run. | Reference must perform adequately and conditions must remain comparable. Do not label the historical departure as recoverable savings. |
| On-time | Hours above the frozen power threshold per complete eligible day. | Interpret with approved operating requirements and verified indoor conditions. Less runtime alone is not success. |
| On-power | Total above-threshold kWh divided by total above-threshold hours. | Check meter configuration, loads, equipment state and operating mode. Lower power alone does not prove efficiency. |
| Sustained-on indoor moisture | Day-balanced humidity ratio and matched departure under outdoor/clock/activity context. | Verify sensor comparability. This is neither coil moisture removal nor a mould diagnosis. |
| Data eligibility | Eligible days/hours divided by the relevant expected days/hours, reported by metric, year and input version. | Keep missing and withheld results visible instead of treating them as zero risk. |
| Inspection follow-through | Share of flagged cases with documented sensor, meter and operating-record checks. | Define completion evidence before use. Failure-warning lead time needs actual dated failures, which this dataset lacks. |

Any control or maintenance trial should preserve the site's approved temperature/humidity requirements and measurement quality, with Track A supplying relevant humidity-exposure context. Set numerical targets after agreeing the operational objective and credible comparison, rather than choosing a percentage to match an earlier slide.

## 9. Recommended next work

1. Use this guide to align the group's presentation claims with the implemented evidence and assign the speaking time. Carry the caveats into the slides.
2. Agree which remaining Person B deliverables are necessary for the final scope. Highest-value gaps are a clearly bounded residual/CUSUM diagnostic and defensible peer selection, if eligible data supports them. A validated fault alarm cannot be promised merely to fill a checklist row.
3. Keep the cooling result explicitly unavailable unless a separately justified cohort/method produces a fair comparison. Do not relax gates just to obtain a desired trend.
4. Agree the final Track B handover fields, coverage/status flags and sign conventions with Person A, then build the joint matrix after Track A is available.
5. Treat broader seasons, live deployment, forecasting or additional physical diagnoses as separate work with their own validation requirements.

## 10. Folder organisation

The [analysis-folder index](../../README.md) groups the current entry notebooks, reusable code, generated evidence and report material by purpose. Keep raw data and upstream preparation in their owning folders. Preserve the historical audit/first-pass evidence. Use the existing `reports/track-b/` for the presentation story and limitations.

The current analysis has only a small number of calculation files. A clear index and separate evidence/report folders make it navigable without moving notebooks or breaking relative imports. If the code later grows enough to justify `src/` and `notebooks/`, migrate imports, run paths and provenance references together in a separately verified change. No such migration is needed to explain the current findings.
