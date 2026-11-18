"""Lightweight, offline checks of the frozen revision package."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def kappa(left, right):
    n = len(left)
    labels = sorted(set(left) | set(right))
    po = sum(a == b for a, b in zip(left, right)) / n
    ca, cb = Counter(left), Counter(right)
    pe = sum(ca[x] * cb[x] for x in labels) / (n * n)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")

def main():
    questions = jsonl(ROOT / "data/real_questions_870_redacted.jsonl")
    observations = jsonl(ROOT / "data/question_observations_870.jsonl")
    assert len(questions) == len(observations) == 870
    assert len({x["user_code"] for x in questions}) == 87
    assert Counter(x["user_code"] for x in questions) == Counter(x["user_code"] for x in observations)
    with (ROOT / "data/human_lcg_200.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len({r["question_id"] for r in rows}) == 200
    assert {r["question_id"] for r in rows} <= {str(q["question_id"]) for q in questions}
    print("Real questions: 870; sampled users: 87; reviewed L/C/G: 200")
    for scorer in ("archived", "revised"):
        differences = Counter()
        for dimension in "LCG":
            automatic = [int(row[f"{scorer}_{dimension}"]) for row in rows]
            reviewed = [int(row[f"human_reviewed_{dimension}"]) for row in rows]
            assert set(automatic + reviewed) <= {0, 1, 2}
            differences.update(abs(a - b) for a, b in zip(automatic, reviewed))
            agreement, value = kappa(automatic, reviewed)
            print(f"{scorer.title()} versus human-reviewed {dimension}: "
                  f"agreement={agreement:.3f}, Cohen_kappa={value:.3f}")
        print(f"{scorer.title()} across {sum(differences.values())} dimension scores: "
              f"{differences[0]} exact, {differences[1]} one point apart, "
              f"{differences[2]} two points apart")
    for directory in ("answer_prompts_redacted", "answer_outputs_redacted"):
        files = list((ROOT / "data" / directory).glob("U*_?.txt"))
        counts = Counter(p.stem.rsplit("_", 1)[-1] for p in files)
        assert counts == Counter({"B": 40, "E": 40, "F": 40})
        print(f"{directory}: B=40, E=40, F=40")

if __name__ == "__main__":
    main()
