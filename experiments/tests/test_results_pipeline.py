from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments import generate_latex_chart_from_csv_data as charts
from experiments import validate_results


class OpenFoldingPipelineTests(unittest.TestCase):
    def test_validator_maps_variant_2_without_folding_to_fixed(self) -> None:
        rows = validate_results.normalize_folding([{"variant": "2"}])
        self.assertEqual(rows[0]["folding"], "fixed")

    def test_chart_reader_requires_folding_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing the required 'folding' column"):
            charts.normalize_folding({"variant": "2"})

    def test_chart_data_keeps_fixed_and_open_as_distinct_series(self) -> None:
        records = []
        for size in (0.5, 1.0):
            for index, series in enumerate(charts.SERIES, start=1):
                records.append(
                    {
                        "size_numeric": size,
                        "tool": series.tool,
                        "mode": series.mode,
                        "variant": series.variant,
                        "folding": series.folding,
                        "time_s_avg": str(index),
                    }
                )

        sizes, values = charts.metric_values(records, "time_s_avg", 1.0)
        fixed = values[(0.5, "yarspg", "normal", 2, "fixed")]
        opened = values[(0.5, "yarspg", "normal", 2, "open")]
        self.assertNotEqual(fixed, opened)
        rendered = charts.render_chart(sizes, values, "Time (s)", "Test")
        self.assertIn("Fold fixed", rendered)
        self.assertIn("Fold open", rendered)

    @unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is not installed")
    def test_rendered_open_folding_chart_compiles(self) -> None:
        records = []
        for series in charts.SERIES:
            records.append(
                {
                    "size_numeric": 0.5,
                    "tool": series.tool,
                    "mode": series.mode,
                    "variant": series.variant,
                    "folding": series.folding,
                    "time_s_avg": "1.0",
                }
            )
        sizes, values = charts.metric_values(records, "time_s_avg", 1.0)
        with tempfile.TemporaryDirectory() as directory:
            tex_path = Path(directory) / "chart.tex"
            tex_path.write_text(
                charts.render_chart(sizes, values, "Time (s)", "Test"),
                encoding="utf-8",
            )
            pdf_path = charts.compile_pdf(tex_path)
            self.assertTrue(pdf_path.is_file())
            self.assertGreater(pdf_path.stat().st_size, 0)

    def test_validator_accepts_complete_open_folding_conversion_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            raw_fields = (
                "size",
                "tool",
                "mode",
                "variant",
                "folding",
                "run",
                "exit_code",
                "output_bytes",
            )
            summary_fields = (
                "size",
                "tool",
                "mode",
                "variant",
                "folding",
                "runs",
            )
            with (results_dir / "conversion_raw.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=raw_fields)
                writer.writeheader()
                for size in sorted(validate_results.SIZES):
                    for tool, mode, variant, folding in sorted(
                        validate_results.OPEN_CONVERSION_FORMS
                    ):
                        for run in range(1, 11):
                            writer.writerow(
                                {
                                    "size": size,
                                    "tool": tool,
                                    "mode": mode,
                                    "variant": variant,
                                    "folding": folding,
                                    "run": run,
                                    "exit_code": 0,
                                    "output_bytes": 100,
                                }
                            )
            with (results_dir / "conversion_summary.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=summary_fields)
                writer.writeheader()
                for size in sorted(validate_results.SIZES):
                    for tool, mode, variant, folding in sorted(
                        validate_results.OPEN_CONVERSION_FORMS
                    ):
                        writer.writerow(
                            {
                                "size": size,
                                "tool": tool,
                                "mode": mode,
                                "variant": variant,
                                "folding": folding,
                                "runs": 10,
                            }
                        )

            validate_results.validate_conversion(results_dir, "Test workload")

    def test_validator_accepts_complete_open_folding_neo4j_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            raw_fields = (
                "size",
                "mode",
                "variant",
                "folding",
                "run",
                "exit_code",
                "cypher_bytes",
                "nodes",
                "relationships",
            )
            summary_fields = ("size", "mode", "variant", "folding", "runs")
            with (results_dir / "neo4j_load_raw.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=raw_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "size": "0.5mb",
                        "mode": "normal",
                        "variant": 1,
                        "folding": "",
                        "run": 1,
                        "exit_code": 0,
                        "cypher_bytes": 100,
                        "nodes": 10,
                        "relationships": 10,
                    }
                )
                for size in sorted(validate_results.SIZES):
                    for mode, variant, folding in sorted(
                        validate_results.OPEN_NEO4J_BATCHED_FORMS
                    ):
                        for run in range(1, 6):
                            writer.writerow(
                                {
                                    "size": size,
                                    "mode": mode,
                                    "variant": variant,
                                    "folding": folding,
                                    "run": run,
                                    "exit_code": 0,
                                    "cypher_bytes": 100,
                                    "nodes": 10,
                                    "relationships": 10,
                                }
                            )
            with (results_dir / "neo4j_load_summary.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=summary_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "size": "0.5mb",
                        "mode": "normal",
                        "variant": 1,
                        "folding": "",
                        "runs": 1,
                    }
                )
                for size in sorted(validate_results.SIZES):
                    for mode, variant, folding in sorted(
                        validate_results.OPEN_NEO4J_BATCHED_FORMS
                    ):
                        writer.writerow(
                            {
                                "size": size,
                                "mode": mode,
                                "variant": variant,
                                "folding": folding,
                                "runs": 5,
                            }
                        )

            validate_results.validate_neo4j(results_dir)


if __name__ == "__main__":
    unittest.main()
