"""Lightweight, offline checks of the frozen revision package."""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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

    def keys(records):
        return {(r["user_code"], str(r["question_id"])) for r in records}

    assert len(keys(questions)) == 870 and keys(questions) == keys(observations)
    assert len({x["user_code"] for x in questions}) == 87
    assert Counter(x["user_code"] for x in questions) == Counter(
        x["user_code"] for x in observations
    )
    with (ROOT / "data/human_lcg_200.csv").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len({r["question_id"] for r in rows}) == 200
    assert {r["question_id"] for r in rows} <= {
        str(q["question_id"]) for q in questions
    }
    # The reviewed B/E/F case numbers and the corpus pseudonyms are different namespaces.
    # Join by question ID, then verify the chronological membership of all five turns.
    ordered = {}
    for record in sorted(
        observations, key=lambda x: (x["creation_date"], int(x["question_id"]))
    ):
        ordered.setdefault(record["user_code"], []).append(str(record["question_id"]))
    owner = {str(r["question_id"]): r["user_code"] for r in observations}
    used_users = set()
    for case in {r["sample_user_code"] for r in rows}:
        part = sorted(
            (r for r in rows if r["sample_user_code"] == case),
            key=lambda r: int(r["history_position"]),
        )
        ids = [r["question_id"] for r in part]
        user = owner[ids[0]]
        assert [int(r["history_position"]) for r in part] == [1, 2, 3, 4, 5]
        assert ids == ordered[user][:5] and user not in used_users
        used_users.add(user)
    print("Real questions: 870; sampled users: 87; reviewed L/C/G: 200")
    for scorer in ("archived", "revised"):
        differences = Counter()
        for dimension in "LCG":
            automatic = [int(row[f"{scorer}_{dimension}"]) for row in rows]
            reviewed = [int(row[f"human_reviewed_{dimension}"]) for row in rows]
            assert set(automatic + reviewed) <= {0, 1, 2}
            differences.update(abs(a - b) for a, b in zip(automatic, reviewed))
            agreement, value = kappa(automatic, reviewed)
            print(
                f"{scorer.title()} versus human-reviewed {dimension}: "
                f"agreement={agreement:.3f}, Cohen_kappa={value:.3f}"
            )
        print(
            f"{scorer.title()} across {sum(differences.values())} dimension scores: "
            f"{differences[0]} exact, {differences[1]} one point apart, "
            f"{differences[2]} two points apart"
        )
    cases = {r["sample_user_code"] for r in rows}
    assert len(cases) == 40
    expected = {f"{case}_{group}" for case in cases for group in "BEF"}
    for directory in ("answer_prompts_redacted", "answer_outputs_redacted"):
        files = list((ROOT / "data" / directory).glob("U*_?.txt"))
        assert {p.stem for p in files} == expected and all(
            p.stat().st_size > 0 for p in files
        )
        counts = Counter(p.stem.rsplit("_", 1)[-1] for p in files)
        assert counts == Counter({"B": 40, "E": 40, "F": 40})
        print(f"{directory}: B=40, E=40, F=40")


if __name__ == "__main__":
    main()
