#!/usr/bin/env python3

import csv
import re
from collections import OrderedDict


##############################################################################
# Configuration
##############################################################################

INPUT_CSV = "conversion_summary.csv"
OUTPUT_TEX = "barchart.tex"

Y_AXIS_MIN = 0
Y_AXIS_MAX = 10

BAR_WIDTH = "6pt"

COLORS = {
    1: "green",
    2: "red",
    3: "blue"
}

# Orden EXACTO que has solicitado
BAR_ORDER = [

    ("yarspg", "normal",     1),
    ("cypher", "normal",     1),
    ("cypher", "large-file", 1),

    ("yarspg", "normal",     2),
    ("cypher", "normal",     2),
    ("cypher", "large-file", 2),

    ("yarspg", "normal",     3),
    ("cypher", "normal",     3),
    ("cypher", "large-file", 3)

]

# Desplazamiento horizontal de las nueve barras
BAR_SHIFTS = [
    "-24pt",
    "-18pt",
    "-12pt",
    "-6pt",
    "0pt",
    "6pt",
    "12pt",
    "18pt",
    "24pt"
]


##############################################################################
# Utility functions
##############################################################################

def numeric_size(size_string):
    """
    Converts

        0.5mb
        1mb
        1.5mb
        ...

    into

        0.5
        1.0
        1.5
        ...
    """

    m = re.search(r"([0-9.]+)", size_string.lower())

    if m is None:
        raise ValueError(f"Cannot parse size '{size_string}'")

    return float(m.group(1))


def canonical_size_label(value):
    """
    Converts

        1.0 -> 1MB
        1.5 -> 1.5MB
    """

    if value.is_integer():
        return f"{int(value)}MB"

    return f"{value}MB"


##############################################################################
# Read CSV
##############################################################################

records = []

with open(INPUT_CSV, newline="") as f:

    reader = csv.DictReader(f)

    for row in reader:

        row["tool"] = row["tool"].strip().lower()
        row["mode"] = row["mode"].strip().lower()

        row["variant"] = int(row["variant"])

        row["size_numeric"] = numeric_size(row["size"])

        row["time"] = float(row["time_s_avg"])

        records.append(row)


##############################################################################
# Sort dataset sizes
##############################################################################

sizes = sorted(
    {
        r["size_numeric"]
        for r in records
    }
)

size_labels = [
    canonical_size_label(s)
    for s in sizes
]


##############################################################################
# Build lookup table
##############################################################################

#
# Dictionary indexed by
#
#   (size, tool, mode, variant)
#
# returning
#
#   execution time
#

times = {}

for r in records:

    key = (
        r["size_numeric"],
        r["tool"],
        r["mode"],
        r["variant"]
    )

    if key in times:
        raise ValueError(
            f"Duplicated row in CSV: {key}"
        )

    times[key] = r["time"]


##############################################################################
# Verify completeness
##############################################################################

missing = []

for size in sizes:

    for tool, mode, variant in BAR_ORDER:

        key = (
            size,
            tool,
            mode,
            variant
        )

        if key not in times:

            missing.append(key)

if missing:

    print("Missing combinations:\n")

    for m in missing:
        print(m)

    raise RuntimeError(
        "CSV does not contain the expected 45 rows."
    )

print("CSV successfully loaded.")
print(f"{len(records)} rows.")
print()

####################################3
##############################################################################
# Start writing PGFPlots
##############################################################################

latex = []

latex.append(r"\begin{tikzpicture}")

latex.append(
r"""
\begin{axis}[
ybar,
bar width=%s,
width=\textwidth,
height=9cm,
ymin=%s,
ymax=%s,
ylabel={Time (s)},
symbolic x coords={%s},
xtick=data,
enlarge x limits=0.08,
legend columns=3,
legend style={
at={(0.5,-0.23)},
anchor=north,
draw=none
}]
""" % (
BAR_WIDTH,
Y_AXIS_MIN,
Y_AXIS_MAX,
",".join(size_labels)
)
)

##############################################################################
# Generate the nine series
##############################################################################

##############################################################################
# Generate the nine series
##############################################################################

for index, (tool, mode, variant) in enumerate(BAR_ORDER):

    shift = BAR_SHIFTS[index]
    color = COLORS[variant]

    coordinates = []

    for size in sizes:

        value = times[(size, tool, mode, variant)]

        coordinates.append(
            "(%s,%s)" %
            (
                canonical_size_label(size),
                value
            )
        )

    coordinates_text = "\n".join(coordinates)

    ######################################################################
    # First pass:
    # background colour + black border
    ######################################################################

    latex.append(
        "\\addplot+["
        "draw=black,"
        "fill=%s,"
        "bar shift=%s"
        "] coordinates {\n%s\n};"
        %
        (
            color,
            shift,
            coordinates_text
        )
    )

    ######################################################################
    # Second pass:
    # only the pattern
    ######################################################################

    if tool == "cypher":

        if mode == "normal":

            latex.append(
                "\\addplot+["
                "draw=none,"
                "fill=none,"
                "pattern=dots,"
                "pattern color=black,"
                "bar shift=%s"
                "] coordinates {\n%s\n};"
                %
                (
                    shift,
                    coordinates_text
                )
            )

        elif mode == "large-file":

            latex.append(
                "\\addplot+["
                "draw=none,"
                "fill=none,"
                "pattern=north east lines,"
                "pattern color=black,"
                "bar shift=%s"
                "] coordinates {\n%s\n};"
                %
                (
                    shift,
                    coordinates_text
                )
            )

##############################################################################
# Legend
##############################################################################
##############################################################################
# Close axis
##############################################################################

latex.append(r"\end{axis}")

##############################################################################
# Manual legend
##############################################################################

# Parámetros de la leyenda
legend_y1 = -1.05
legend_y2 = -1.70

box_w = 0.32
box_h = 0.22

x1 = 1.0
x2 = 5.2
x3 = 9.7

text_dx = 0.15

###########################################################################
# Primera fila: variantes
###########################################################################

for x, colour, label in [
    (x1, "green", r"\maximevar"),
    (x2, "red",   r"\katjavar"),
    (x3, "blue",  r"\rubenvar"),
]:

    latex.append(
        "\\draw[draw=black,fill=%s] "
        "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
        %
        (
            colour,
            x,
            legend_y1,
            box_w,
            box_h
        )
    )

    latex.append(
        "\\node[anchor=west] at (%.2f,%.2f) {%s};"
        %
        (
            x + box_w + text_dx,
            legend_y1 + box_h/2,
            label
        )
    )

###########################################################################
# Segunda fila
###########################################################################

#
# YARSPG
#

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x1,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {YARS-PG};"
    %
    (
        x1 + box_w + text_dx,
        legend_y2 + box_h/2
    )
)

#
# Cypher normal
#

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x2,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\fill[pattern=dots,pattern color=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x2,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {Cypher monolithic};"
    %
    (
        x2 + box_w + text_dx,
        legend_y2 + box_h/2
    )
)

#
# Cypher large-file
#

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x3,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\fill[pattern=north east lines,pattern color=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x3,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {Cypher batched};"
    %
    (
        x3 + box_w + text_dx,
        legend_y2 + box_h/2
    )
)

##############################################################################
# Finish figure
##############################################################################

latex.append(r"\end{tikzpicture}")
##############################################################################
# Write output file
##############################################################################

with open(OUTPUT_TEX, "w", encoding="utf8") as f:

    f.write("\n".join(latex))

print()
print(f"Written: {OUTPUT_TEX}")
print()
