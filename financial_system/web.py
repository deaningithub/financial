from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, jsonify, request

from financial_system.pipeline import run_daily_pipeline


app = Flask(__name__)


@app.get("/")
def health() -> tuple[dict, int]:
    return {
        "service": "financial-system",
        "status": "ok",
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }, 200


@app.get("/healthz")
def healthz() -> tuple[dict, int]:
    return {"status": "ok"}, 200


@app.post("/run")
def run_report():
    payload = request.get_json(silent=True) or {}
    day = payload.get("date") or request.args.get("date")
    no_ai = payload.get("no_ai")
    if no_ai is None:
        no_ai = request.args.get("no_ai", "").lower() in {"1", "true", "yes"}

    outputs = run_daily_pipeline(day=day, use_ai=not bool(no_ai))
    return jsonify({"status": "completed", "outputs": outputs})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
