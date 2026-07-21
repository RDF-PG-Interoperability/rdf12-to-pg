#!/usr/bin/env python3
"""Generate standalone PGFPlots charts from conversion summary CSV data."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Series:
    tool: str
    mode: str
    variant: int
    folding: str
    colour: str


SERIES = tuple(
    Series(tool, mode, variant, folding, colour)
    for variant, folding, colour in (
        (1, "", "green"),
        (2, "fixed", "red"),
        (2, "open", "orange"),
        (3, "", "blue"),
    )
    for tool, mode in (
        ("yarspg", "normal"),
        ("cypher", "normal"),
        ("cypher", "large-file"),
    )
)

METRICS = {
    "time": ("time_s_avg", "Time (s)", 1.0),
    "peak-memory": ("peak_kb_avg", "Peak RSS (MiB)", 1.0 / 1024),
    "output-size": ("output_bytes_avg", "Output size (MB)", 1.0 / 1_000_000),
}


def numeric_size(raw: str) -> float:
    match = re.search(r"([0-9.]+)", raw.lower())
    if match is None:
        raise ValueError(f"cannot parse dataset size {raw!r}")
    return float(match.group(1))


def size_label(value: float) -> str:
    return f"{int(value) if value.is_integer() else value}MB"


def normalize_folding(row: dict[str, str]) -> str:
    if "folding" not in row:
        raise ValueError("CSV is missing the required 'folding' column")
    return row["folding"].strip().lower()


def read_records(path: Path) -> list[dict[str, str | int | float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        records: list[dict[str, str | int | float]] = []
        for source in csv.DictReader(handle):
            row: dict[str, str | int | float] = dict(source)
            row["tool"] = source["tool"].strip().lower()
            row["mode"] = source["mode"].strip().lower()
            row["variant"] = int(source["variant"])
            row["folding"] = normalize_folding(source)
            row["size_numeric"] = numeric_size(source["size"])
            records.append(row)
    return records


def metric_values(
    records: list[dict[str, str | int | float]],
    column: str,
    scale: float,
) -> tuple[list[float], dict[tuple[float, str, str, int, str], float]]:
    sizes = sorted({float(row["size_numeric"]) for row in records})
    values: dict[tuple[float, str, str, int, str], float] = {}
    for row in records:
        key = (
            float(row["size_numeric"]),
            str(row["tool"]),
            str(row["mode"]),
            int(row["variant"]),
            str(row["folding"]),
        )
        if key in values:
            raise ValueError(f"duplicate CSV row for {key}")
        values[key] = float(str(row[column])) * scale

    expected = {
        (size, item.tool, item.mode, item.variant, item.folding)
        for size in sizes
        for item in SERIES
    }
    missing = sorted(expected - values.keys())
    extra = sorted(values.keys() - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {len(missing)} combinations, first: {missing[0]}")
        if extra:
            details.append(f"unexpected {len(extra)} combinations, first: {extra[0]}")
        raise ValueError("CSV does not contain the expected open-folding matrix: " + "; ".join(details))
    return sizes, values


def tex_escape(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_")


def pattern_name(series: Series) -> str | None:
    if series.tool == "yarspg":
        return None
    if series.mode == "normal":
        return "dots"
    return "north east lines"


def render_chart(
    sizes: list[float],
    values: dict[tuple[float, str, str, int, str], float],
    ylabel: str,
    title: str,
) -> str:
    labels = ",".join(size_label(size) for size in sizes)
    shifts = [(-27.5 + index * 5.0) for index in range(len(SERIES))]
    lines = [
        r"\documentclass[tikz,border=5pt]{standalone}",
        r"\usepackage{pgfplots}",
        r"\usepgfplotslibrary{fillbetween}",
        r"\usetikzlibrary{patterns}",
        r"\pgfplotsset{compat=1.18}",
        r"\begin{document}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  ybar,",
        r"  bar width=4.5pt,",
        r"  width=16cm,",
        r"  height=8.5cm,",
        r"  ymin=0,",
        rf"  ylabel={{{tex_escape(ylabel)}}},",
        rf"  title={{{tex_escape(title)}}},",
        rf"  symbolic x coords={{{labels}}},",
        r"  xtick=data,",
        r"  enlarge x limits=0.10,",
        r"  scaled y ticks=false,",
        r"  tick label style={font=\small},",
        r"  legend columns=4,",
        r"  legend style={at={(0.5,-0.20)},anchor=north,draw=none,font=\small},",
        r"]",
    ]

    for series, shift in zip(SERIES, shifts, strict=True):
        coordinates = " ".join(
            f"({size_label(size)},{values[(size, series.tool, series.mode, series.variant, series.folding)]:.6f})"
            for size in sizes
        )
        lines.append(
            rf"\addplot+[forget plot,draw=black,fill={series.colour},"
            rf"bar shift={shift:.1f}pt] "
            rf"coordinates {{{coordinates}}};"
        )
        pattern = pattern_name(series)
        if pattern is not None:
            lines.append(
                rf"\addplot+[forget plot,draw=none,fill=none,pattern={pattern},"
                rf"pattern color=black,bar shift={shift:.1f}pt] "
                rf"coordinates {{{coordinates}}};"
            )

    lines.extend(
        [
            r"\addlegendimage{area legend,draw=black,fill=green}",
            r"\addlegendentry{Direct}",
            r"\addlegendimage{area legend,draw=black,fill=red}",
            r"\addlegendentry{Fold fixed}",
            r"\addlegendimage{area legend,draw=black,fill=orange}",
            r"\addlegendentry{Fold open}",
            r"\addlegendimage{area legend,draw=black,fill=blue}",
            r"\addlegendentry{Structural}",
            r"\addlegendimage{area legend,draw=black,fill=white}",
            r"\addlegendentry{YARS-PG}",
            r"\addlegendimage{area legend,draw=black,fill=white,pattern=dots,pattern color=black}",
            r"\addlegendentry{Cypher monolithic}",
            r"\addlegendimage{area legend,draw=black,fill=white,pattern=north east lines,pattern color=black}",
            r"\addlegendentry{Cypher batched}",
            r"\end{axis}",
            r"\end{tikzpicture}",
            r"\end{document}",
            "",
        ]
    )
    return "\n".join(lines)


def compile_pdf(tex_path: Path) -> Path:
    executable = shutil.which("pdflatex")
    if executable is None:
        raise RuntimeError("pdflatex is required with --compile")
    result = subprocess.run(
        [executable, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=tex_path.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdflatex failed for {tex_path}:\n{result.stdout[-4000:]}")
    for suffix in (".aux", ".log"):
        auxiliary = tex_path.with_suffix(suffix)
        if auxiliary.exists():
            auxiliary.unlink()
    return tex_path.with_suffix(".pdf")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--title", default="RDF 1.2 to property graph conversion")
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=tuple(METRICS),
        default=tuple(METRICS),
    )
    parser.add_argument("--compile", action="store_true", help="also compile PDFs with pdflatex")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = read_records(args.input_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for metric in args.metrics:
        column, ylabel, scale = METRICS[metric]
        sizes, values = metric_values(records, column, scale)
        tex_path = args.output_dir / f"conversion-{metric}.tex"
        tex_path.write_text(
            render_chart(sizes, values, ylabel, args.title),
            encoding="utf-8",
        )
        print(f"Written: {tex_path}")
        if args.compile:
            print(f"Written: {compile_pdf(tex_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
