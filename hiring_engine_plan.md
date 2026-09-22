# Sreejita Hiring Engine v1.0 — Implementation Plan

## Architecture Assessment

### Already Exists (Upgrade Only)
| Component | Location | Status |
|-----------|----------|--------|
| Skill Extraction | `jd_processor/` | ✅ Complete |
| Bullet Rewriting | `improver.py` | ✅ Hardened |
| ATS Scoring | `ats_scoring/scorer.py` | ✅ Complete |
| Decision Engine | `app.py:run_analysis` | ⚠️ Basic (APPLY/MAYBE/IMPROVE) |
| Signal Dominance | `improver.py` steps 14a-14b | ✅ Complete |
| Shortlist Scoring | `pipeline/core.py:compute_shortlist_score` | ⚠️ Exists but not integrated |
| Quality Scoring | `pipeline/core.py:evaluate_resume_quality` | ✅ Complete |

### Net-New Components
| Component | Destination | Priority |
|-----------|-------------|----------|
| **Hiring Simulation Engine** | `pipeline/hiring_simulation.py` | 🔴 CRITICAL |
| **Skill → Proof Audit** | Enhance `pipeline/core.py` | 🔴 CRITICAL |
| **Competitive Differentiation** | In hiring simulation | 🔴 CRITICAL |
| **Recruiter Persona Sim** | In hiring simulation | 🟡 HIGH |
| **Gap Intelligence** | In hiring simulation | 🟡 HIGH |
| **Dashboard Integration** | `dashboard.py`, `manual_mode.py` | 🟡 HIGH |

---

## Phase 1: Hiring Simulation Engine (Core Module)

### New file: `pipeline/hiring_simulation.py`

```python
class HiringSimulator:
    """3-Layer Hiring Simulation: ATS → Recruiter → Hiring Manager"""

    def simulate(resume, jd, ats_score) -> HiringSimulationResult:
        # Layer 1: ATS Filter (keyword match, format, parsing)
        # Layer 2: Recruiter Scan (6-10 sec: summary, top bullets, clarity)
        # Layer 3: Hiring Decision (depth, fit, differentiation)
        # + Competitive positioning
        # + Recruiter persona (Amazon/Google/Microsoft)
        # + Gap intelligence
```

### Integration into `pipeline/core.py`
- Call `HiringSimulator.simulate()` after improvement
- Add `hiring_simulation` field to `PipelineResult`

### Integration into `manual_mode.py` / `dashboard.py`
- Display 3-layer simulation results
- Show competitive positioning
- Show per-persona feedback

---

## Phase 2: Skill → Proof Audit

### Enhancement to `pipeline/core.py`
- For each matched skill, check if it has PURPOSE-DRIVEN evidence in bullets
- Output: `{skill: {proven: bool, bullet_idx: int, proof_type: "purpose"|"bare"|"none"}}`
- Feed gaps into Gap Intelligence

---

## Phase 3: Dashboard Display

### New sections in `dashboard.py:render_analyze_resume()`
- **Hiring Simulation Panel** — 3 layers with pass/fail
- **Competitive Position** — rare skills, scale evidence
- **Recruiter Personas** — Amazon/Google/Microsoft feedback
- **Skill → Proof Matrix** — what's proven vs what's missing

---

## Execution Order
1. Build `pipeline/hiring_simulation.py` (core engine)
2. Integrate into `pipeline/core.py` (add to PipelineResult)
3. Integrate into `manual_mode.py` (pass results through)
4. Display in `dashboard.py` (new UI sections)
5. Validate with diagnostic script
