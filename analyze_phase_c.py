"""Merge completed shards and compute seed-clustered paired policy differences."""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from audit import ROOT, TASKS
from phase_c import POLICIES, FINAL_SEEDS, RUNS, summarize


def quantile(values, q):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,max(0,round((len(ordered)-1)*q)))]


def paired(rows,task,policy,metric):
    by={(r["task"],r["seed"],r["run"],r["policy"]):r for r in rows}
    per_seed=[];wins=losses=ties=0
    for seed in FINAL_SEEDS:
        diffs=[]
        for run in RUNS:
            a=by[(task,seed,run,policy)][metric]
            b=by[(task,seed,run,"unverified")][metric]
            delta=float(a)-float(b)
            diffs.append(delta)
            wins+=delta>0;losses+=delta<0;ties+=delta==0
        per_seed.append(statistics.mean(diffs))
    rng=random.Random(20261016)
    samples=[statistics.mean(rng.choices(per_seed,k=len(per_seed))) for _ in range(20000)]
    return {"difference":round(statistics.mean(per_seed),4),
            "seed_bootstrap_95":[round(quantile(samples,.025),4),round(quantile(samples,.975),4)],
            "episode_wins":wins,"episode_losses":losses,"episode_ties":ties}


def main():
    paths=[ROOT/"results"/f"phase_c_shard{i}.jsonl" for i in range(4)]
    rows=[json.loads(line) for path in paths for line in path.read_text().splitlines()]
    expected={(task,seed,policy,run) for task in TASKS for seed in FINAL_SEEDS
              for policy in POLICIES for run in RUNS}
    keys=[(r["task"],r["seed"],r["policy"],r["run"]) for r in rows]
    if len(rows)!=720 or len(set(keys))!=720 or set(keys)!=expected:
        raise RuntimeError("Missing or duplicate final episodes")
    order={task:i for i,task in enumerate(TASKS)}
    rows.sort(key=lambda r:(order[r["task"]],r["seed"],POLICIES.index(r["policy"]),r["run"]))
    merged=ROOT/"results"/"phase_c.jsonl"
    merged.write_text("".join(json.dumps(r)+"\n" for r in rows))
    result=summarize(rows)
    result["paired_vs_unverified"]={task:{policy:{metric:paired(rows,task,policy,metric)
            for metric in ("task_success","browser_actions","elapsed_s","cost_usd")}
            for policy in POLICIES[1:]} for task in TASKS}
    for task in TASKS:
        for policy in POLICIES:
            group=[r for r in rows if r["task"]==task and r["policy"]==policy]
            item=result["by_task"][task][policy]
            item["cost_per_episode_usd"]=round(item["cost_usd"]/len(group),6)
            item["page_goal_count"]=sum(r["page_goal"] for r in group)
            item["model_calls"]=sum(r["model_calls"] for r in group)
    result["parse_failures"]=sum(r["final_decision"]=={"action":"unparsed"} for r in rows)
    result["all_model_stops"]={reason:sum(s["usage"]["stop_reason"]==reason for r in rows for s in r["steps"])
                               for reason in {s["usage"]["stop_reason"] for r in rows for s in r["steps"]}}
    prior_files=[ROOT/"results"/"phase_c_dev.jsonl",
                 ROOT/"results"/"archive"/"phase_c_dev_v1_unstructured.jsonl",
                 ROOT/"results"/"archive"/"phase_c_v1_partial_serial.jsonl"]
    prior=sum(json.loads(line)["cost_usd"] for path in prior_files if path.exists()
              for line in path.read_text().splitlines())
    result["all_project_api_spend_usd"]=round(result["phase_c_cost_usd"]+prior+
        json.loads((ROOT/"results"/"pilot.summary.json").read_text())["cost_usd"]+
        json.loads((ROOT/"results"/"phase_b.summary.json").read_text())["cost_usd"],6)
    path=ROOT/"results"/"phase_c.summary.json"
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(f"merged {len(rows)} episodes; Phase C ${result['phase_c_cost_usd']}; all API work ${result['all_project_api_spend_usd']}")
    for task in TASKS:
        print(task)
        for policy in POLICIES:
            g=result["by_task"][task][policy]
            print(f"  {policy}: {g['successes']}/{g['episodes']} successes; runs {g['success_by_run']}; "
                  f"actions {g['mean_browser_actions']}; median {g['median_elapsed_s']}s; "
                  f"${g['cost_per_episode_usd']}/episode")
        for policy in POLICIES[1:]:
            print("  paired",policy,result["paired_vs_unverified"][task][policy]["task_success"])


if __name__=="__main__":main()
