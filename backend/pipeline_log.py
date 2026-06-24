import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).parent / "logs"


def setup_pipeline_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("pipeline")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def preview(data: object, max_len: int = 120) -> str:
    if isinstance(data, bytes):
        return f"<bytes len={len(data)}>"
    if isinstance(data, (int, float)):
        return str(data)
    text = str(data).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


@dataclass
class StepRecord:
    step: str
    model: str
    duration_ms: float
    input_preview: str
    output_preview: str
    metrics: dict[str, Any] = field(default_factory=dict)


class PipelineReport:
    def __init__(self, label: str = "pipeline"):
        self.request_id = uuid.uuid4().hex[:8]
        self.label = label
        self.started = time.perf_counter()
        self.steps: list[StepRecord] = []
        self.logger = setup_pipeline_logging()

    def record(
        self,
        step: str,
        model: str,
        duration_ms: float,
        input_data: object,
        output_data: object,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        record = StepRecord(
            step=step,
            model=model,
            duration_ms=round(duration_ms, 1),
            input_preview=preview(input_data),
            output_preview=preview(output_data),
            metrics=metrics or {},
        )
        self.steps.append(record)
        metrics_suffix = ""
        if record.metrics:
            metrics_suffix = f" | metrics: {json.dumps(record.metrics, ensure_ascii=False)}"
        self.logger.info(
            "[%s %s] %s | %s | %.1fms | in: %s | out: %s%s",
            self.label,
            self.request_id,
            step,
            model,
            duration_ms,
            record.input_preview,
            record.output_preview,
            metrics_suffix,
        )

    def total_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000

    def summary(self) -> dict:
        total = self.total_ms()
        step_total = sum(s.duration_ms for s in self.steps) or 1.0
        bottleneck = max(self.steps, key=lambda s: s.duration_ms) if self.steps else None
        return {
            "request_id": self.request_id,
            "label": self.label,
            "total_ms": round(total, 1),
            "steps": [asdict(s) for s in self.steps],
            "bottleneck": (
                {
                    "step": bottleneck.step,
                    "model": bottleneck.model,
                    "duration_ms": bottleneck.duration_ms,
                    "pct": round(bottleneck.duration_ms / step_total * 100, 1),
                }
                if bottleneck
                else None
            ),
        }

    def finish(self) -> dict:
        summary = self.summary()
        bottleneck = summary["bottleneck"]
        lines = [
            f"=== {self.label} {self.request_id} | total {summary['total_ms']:.1f}ms ===",
        ]
        for s in self.steps:
            metrics = f" | {json.dumps(s.metrics, ensure_ascii=False)}" if s.metrics else ""
            lines.append(
                f"  {s.step:<8} | {s.model:<22} | {s.duration_ms:>8.1f}ms | "
                f"in: {s.input_preview} | out: {s.output_preview}{metrics}"
            )
        if bottleneck:
            lines.append(
                f"BOTTLENECK: {bottleneck['step']} ({bottleneck['model']}) "
                f"{bottleneck['duration_ms']:.1f}ms ({bottleneck['pct']}%)"
            )
        report_text = "\n".join(lines)
        self.logger.info(report_text)
        return summary
