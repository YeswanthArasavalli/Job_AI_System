"""Test Behavior Engine v5.1.1 — Override + Reward + Graduated Penalty."""
import logging, os, json
logging.disable(logging.WARNING)
from pipeline.behavior_engine import (
    check_recovery_enforcement, apply_soft_override,
    compute_reward, apply_behavior_modifiers,
    run_behavior_engine, _load_state, _save_state, _STATE_FILE,
)

# Clean state
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)

print("=" * 65)
print("BEHAVIOR ENGINE v5.1.1 PATCH TEST")
print("=" * 65)

# ──────── Part 1: Graduated Penalty ────────
print("\n📊 GRADUATED PENALTY CONTROL:")
for progress, label in [(0, "no action"), (25, "some work"), (50, "half done"),
                         (67, "good progress"), (80, "almost done"), (100, "complete")]:
    # Simulate recovery with controlled completion
    state = {"recovery_pending": {"keywords_to_add": ["Spark"], "project_required": True}}
    if progress == 0:
        bullets = ["did some work"]
    elif progress <= 33:
        bullets = ["built data pipeline using Spark"]
    elif progress <= 66:
        bullets = ["built data pipeline using Spark",
                   "developed ML model and deployed end-to-end"]
    else:
        bullets = ["built data pipeline using Spark",
                   "developed ML model and deployed end-to-end on Kubernetes",
                   "designed project architecture"]
    r = check_recovery_enforcement(state, bullets)
    print(f"  {label:15s}: progress={r['progress_score']:3d}%, "
          f"penalty={r['penalty']:2d}%, enforced={'YES' if r['enforced'] else 'NO'}")

# ──────── Part 2: Soft Override ────────
print("\n🔓 SOFT OVERRIDE:")
state = {"override_count": 0}
ov = apply_soft_override("SKIP", 38, state)
print(f"  Original: {ov['original_decision']} → {ov['final_decision']}")
print(f"  Confidence: 38 → {ov['confidence']}")
print(f"  Message: {ov['override_message'][:50]}...")
print(f"  Count: {ov['override_count']}")

ov2 = apply_soft_override("EXPERIMENT APPLY", 45, state)
print(f"  Second override: conf=45 → {ov2['confidence']}, count={ov2['override_count']}")

# ──────── Part 3: Reward Loop ────────
print("\n🎁 REWARD LOOP:")
state = {"prev_progress_score": 0, "progress_score": 0}
for p in [0, 33, 50, 67, 100]:
    r = compute_reward(state, p)
    status = "🎉" if r["applied"] else "⏸️"
    print(f"  progress={p:3d}%: {status} delta={r['progress_delta']:+3d}%, "
          f"conf_boost={r['confidence_boost']}, penalty_cut={r['penalty_reduction']} "
          f"— {r['message'][:50]}")

# ──────── Part 4: Full Modifier Chain with Override ────────
print("\n🎛️ FULL MODIFIER CHAIN:")
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)

base = {"final": "SKIP", "confidence": 38, "reason": "Weak match",
        "signals": {"ats": "WEAK"}, "modifiers": []}
bullets = ["Built data pipeline using Python and SQL",
           "Developed ML model using TensorFlow"]

# Without override
fresh = {"exploration_used": 0, "weekly_applications": 1, "prev_progress_score": 0}
mod1 = apply_behavior_modifiers(base, fresh, bullets, ["Spark"], 44, user_override=False)
print(f"  No override:   {mod1['final']:25s} conf={mod1['confidence']}%")

# With override
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)
fresh2 = {"exploration_used": 0, "weekly_applications": 1, "prev_progress_score": 0}
mod2 = apply_behavior_modifiers(base, fresh2, bullets, ["Spark"], 44, user_override=True)
print(f"  With override: {mod2['final']:25s} conf={mod2['confidence']}%")
bc = mod2["behavior_control"]
print(f"    Override used: {bc['override_used']}")
print(f"    Reward applied: {bc['reward_applied']}")
print(f"    Progress: {bc['progress_score']}%, delta={bc['progress_delta']:+d}%")

# ──────── Part 5: Reward reduces penalty on 2nd run ────────
print("\n📈 REWARD ACROSS RUNS:")
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)

# Run 1: Weak bullets → penalty
weak_state = {"exploration_used": 0, "weekly_applications": 5, "prev_progress_score": 0,
              "recovery_pending": {"keywords_to_add": ["Spark", "MLOps"], "project_required": True}}
base_fix = {"final": "APPLY (FIX GAPS)", "confidence": 55,
            "reason": "Gaps", "signals": {"ats": "WEAK"}, "modifiers": []}
r1 = apply_behavior_modifiers(base_fix, weak_state, ["did data analysis"], ["Spark"], 44)
print(f"  Run 1 (weak):    conf={r1['confidence']}%, penalty enforced={'YES' if r1['behavior_control']['recovery_enforced'] else 'NO'}")

# Run 2: Improved bullets → reward
improved_state = dict(weak_state)
improved_state["prev_progress_score"] = 0  # From previous run
improved_state["recovery_pending"] = {"keywords_to_add": ["Spark", "MLOps"], "project_required": True}
r2 = apply_behavior_modifiers(
    base_fix, improved_state,
    ["Built data pipeline using Spark", "Developed ML model and deployed end-to-end"],
    ["MLOps"], 44,
)
print(f"  Run 2 (improved): conf={r2['confidence']}%, "
      f"reward={r2['behavior_control']['reward_applied']}, "
      f"delta={r2['behavior_control']['progress_delta']:+d}%")

# ──────── Part 6: Full Orchestration ────────
print("\n📊 FULL v5.1.1 ORCHESTRATION:")
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)

# Without override
full1 = run_behavior_engine(
    decision={"final": "SKIP", "confidence": 35, "reason": "Weak",
              "signals": {"ats": "BLOCK"}, "modifiers": []},
    bullets=["Built pipeline using Python", "Analyzed data with SQL"],
    missing_keywords=["Spark", "K8s"], recruiter_avg=44,
)
d1 = full1["decision"]
bc1 = full1["behavior_control"]
print(f"  Normal:   {d1['final']:25s} conf={d1['confidence']}%, "
      f"override={bc1['override_used']}, reward={bc1['reward_applied']}")

# With override
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)
full2 = run_behavior_engine(
    decision={"final": "SKIP", "confidence": 35, "reason": "Weak",
              "signals": {"ats": "BLOCK"}, "modifiers": []},
    bullets=["Built pipeline using Python", "Analyzed data with SQL"],
    missing_keywords=["Spark", "K8s"], recruiter_avg=44,
    user_override=True,
)
d2 = full2["decision"]
bc2 = full2["behavior_control"]
print(f"  Override: {d2['final']:25s} conf={d2['confidence']}%, "
      f"override={bc2['override_used']}, msg={bc2['override_message'][:40]}...")

# Clean up
if os.path.exists(_STATE_FILE):
    os.remove(_STATE_FILE)

print(f"\n✅ BEHAVIOR ENGINE v5.1.1 COMPLETE")
