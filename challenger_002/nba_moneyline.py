#!/usr/bin/env python3
"""Challenger-002 NBA moneyline research model. Standard library only.

Input JSONL schema (one row per game, home-team perspective):
event_id, tipoff_utc, captured_utc, source_id, home_win [training only],
home_win_pct_pre, away_win_pct_pre, home_rest_days, away_rest_days.
All feature values must be known before tipoff; source_id must identify provenance.
No betting odds or postgame information may be used as model features.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

FEATURES = ("home_win_pct_pre", "away_win_pct_pre", "home_rest_days", "away_rest_days")
MIN_ROWS = 200
UTC = dt.timezone.utc

def stamp(value):
    d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamps must have a timezone")
    return d.astimezone(UTC)

def load(path, training):
    rows = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        for k in ("event_id", "tipoff_utc", "captured_utc", "source_id", *FEATURES):
            if k not in r or r[k] in ("", None):
                raise ValueError(f"line {line_no}: missing {k}")
        if not isinstance(r["source_id"], str) or not r["source_id"].strip():
            raise ValueError("source_id must be nonempty")
        if stamp(r["captured_utc"]) >= stamp(r["tipoff_utc"]):
            raise ValueError(f"line {line_no}: feature capture is not pregame")
        x = [float(r[k]) for k in FEATURES]
        if not all(math.isfinite(v) for v in x):
            raise ValueError("non-finite feature")
        if not (0 <= x[0] <= 1 and 0 <= x[1] <= 1 and 0 <= x[2] <= 14 and 0 <= x[3] <= 14):
            raise ValueError("feature outside expected range")
        if training:
            if type(r.get("home_win")) is not int or r["home_win"] not in (0, 1):
                raise ValueError("training rows need actual home_win label 0/1")
        rows.append((r, x))
    if len({r["event_id"] for r, _ in rows}) != len(rows):
        raise ValueError("duplicate event IDs")
    return rows

def sigmoid(z):
    return 1 / (1 + math.exp(-max(-35, min(35, z))))

def vector(x):
    return [1, (x[0] - 0.5) * 2, (x[1] - 0.5) * 2,
            min(x[2], 7) / 7, min(x[3], 7) / 7]

def fit(rows, epochs=1200, lr=0.15, penalty=0.005):
    w = [0.] * (len(FEATURES) + 1)
    for _ in range(epochs):
        grad = [0.] * len(w)
        for r, x in rows:
            v = vector(x)
            error = sigmoid(sum(a*b for a,b in zip(w,v))) - r["home_win"]
            for j in range(len(w)):
                grad[j] += error * v[j]
        for j in range(len(w)):
            w[j] -= lr * (grad[j] / len(rows) + (penalty * w[j] if j else 0))
    return w

def brier(rows, w):
    return sum((sigmoid(sum(a*b for a,b in zip(w, vector(x)))) - r["home_win"])**2
               for r,x in rows) / len(rows)

def train(args):
    rows = load(args.input, True)
    if len(rows) < MIN_ROWS:
        raise ValueError(f"HOLD: requires at least {MIN_ROWS} authenticated pregame rows")
    rows.sort(key=lambda item: stamp(item[0]["tipoff_utc"]))
    cutoff = int(len(rows) * 0.8)
    before, after = rows[:cutoff], rows[cutoff:]
    if stamp(before[-1][0]["tipoff_utc"]) >= stamp(after[0][0]["tipoff_utc"]):
        raise ValueError("chronological split overlaps on tipoff timestamp")
    w = fit(before)
    score = brier(after, w)
    baseline = sum(r["home_win"] for r,_ in before) / len(before)
    baseline_score = sum((baseline-r["home_win"])**2 for r,_ in after) / len(after)
    digest = hashlib.sha256(Path(args.input).read_bytes()).hexdigest()
    model = {"model":"Challenger-002", "status":"research_only",
             "features":list(FEATURES), "weights":w, "training_rows":len(before),
             "holdout_rows":len(after), "holdout_brier":score,
             "holdout_baseline_brier":baseline_score, "input_sha256":digest,
             "training_end_utc":before[-1][0]["tipoff_utc"],
             "holdout_start_utc":after[0][0]["tipoff_utc"],
             "validated_for_betting":False, "independently_certified":False}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(model, indent=2)+"\n")
    print(json.dumps({"status":"RESEARCH", "holdout_brier":score,
                      "baseline_brier":baseline_score, "holdout_rows":len(after)}))

def predict(args):
    model = json.loads(Path(args.model).read_text())
    if (model.get("model") != "Challenger-002" or model.get("status") != "research_only"
            or model.get("features") != list(FEATURES)
            or model.get("training_rows", 0) < 160 or model.get("holdout_rows", 0) < 40
            or len(model.get("weights", [])) != 5):
        raise ValueError("HOLD: invalid or missing fitted Challenger-002 research model")
    rows = load(args.input, False)
    now = dt.datetime.now(UTC)
    for r,x in rows:
        age = (now - stamp(r["captured_utc"])).total_seconds()
        if age < -300 or age > 3600 or stamp(r["tipoff_utc"]) <= now:
            print(json.dumps({"event_id":r["event_id"], "decision":"HOLD",
                              "reason":"stale/future capture or event started"}))
            continue
        p = sigmoid(sum(a*b for a,b in zip(model["weights"],vector(x))))
        print(json.dumps({"event_id":r["event_id"], "tipoff_utc":r["tipoff_utc"],
                          "captured_utc":r["captured_utc"], "source_id":r["source_id"],
                          "model":"Challenger-002", "home_win_probability":round(p,6),
                          "decision":"RESEARCH", "certified":False}))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--input", required=True)
    t.add_argument("--output", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--input", required=True)
    p.add_argument("--model", required=True)
    args = ap.parse_args()
    try:
        (train if args.cmd == "train" else predict)(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise SystemExit(f"HOLD: {e}")

if __name__ == "__main__":
    main()
