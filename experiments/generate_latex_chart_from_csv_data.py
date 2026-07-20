#!/usr/bin/env python3

import csv
import re
from collections import OrderedDict




##############################################################################
# Configuration
##############################################################################

TARGET_DATA_COLUMN = "time_s_avg"
Y_AXIS_MIN = 0
Y_AXIS_MAX = 10
Y_AXIS_TEXT = "Time (s)"
HEIGHT = "4.5cm"
ENLARGE_SEP_VALUE = 0.065

INPUT_CSV = "conversion_summary.csv"
OUTPUT_TEX = "barchart.tex"

BAR_WIDTH = "5pt"

COLORS = {
    ("variant1", "fixed"): "green",
    ("variant2", "fixed"): "red",
    ("variant2", "open"): "orange",
    ("variant3", "fixed"): "blue",
}


# Orden EXACTO que has solicitado
BAR_ORDER = [

    # Variant 1
    ("variant1", 1, "fixed", "yarspg", "normal"),
    ("variant1", 1, "fixed", "cypher", "normal"),
    ("variant1", 1, "fixed", "cypher", "large-file"),

    # Variant 2 - fixed folding
    ("variant2", 2, "fixed", "yarspg", "normal"),
    ("variant2", 2, "fixed", "cypher", "normal"),
    ("variant2", 2, "fixed", "cypher", "large-file"),

    # Variant 2 - open folding
    ("variant2", 2, "open", "yarspg", "normal"),
    ("variant2", 2, "open", "cypher", "normal"),
    ("variant2", 2, "open", "cypher", "large-file"),

    # Variant 3
    ("variant3", 3, "fixed", "yarspg", "normal"),
    ("variant3", 3, "fixed", "cypher", "normal"),
    ("variant3", 3, "fixed", "cypher", "large-file"),

]

# Desplazamiento horizontal de las nueve barras
BAR_SHIFTS = [
    "-27.5pt",
    "-22.5pt",
    "-17.5pt",
    "-12.5pt",
    "-7.5pt",
    "-2.5pt",
    "2.5pt",
    "7.5pt",
    "12.5pt",
    "17.5pt",
    "22.5pt",
    "27.5pt",
]


##############################################################################
# Utility functions
##############################################################################

_TARGET_DATA = "tg"

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
        row["folding"] = row["folding"].strip().lower()

        row["variant"] = int(row["variant"])

        row["size_numeric"] = numeric_size(row["size"])

        row[_TARGET_DATA] = float(row[TARGET_DATA_COLUMN])

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
        r["variant"],
        r["folding"]
    )

    if key in times:
        raise ValueError(
            f"Duplicated row in CSV: {key}"
        )

    times[key] = r[_TARGET_DATA]


##############################################################################
# Verify completeness
##############################################################################

missing = []

for size in sizes:

    for _, variant, folding, tool, mode in BAR_ORDER:

        key = (
            size,
            tool,
            mode,
            variant,
            folding,
        )

        if key not in times:

            missing.append(key)

if missing:

    print("Missing combinations:\n")

    for m in missing:
        print(m)

    raise RuntimeError(
        "CSV does not contain all the expected combinations."
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
height=%s,
ymin=%s,
ymax=%s,
ylabel={%s},
symbolic x coords={%s},
xtick=data,
enlarge x limits=%s,
legend columns=3,
legend style={
at={(0.5,-0.23)},
anchor=north,
draw=none
}]
""" % (
    BAR_WIDTH,
    HEIGHT,
    Y_AXIS_MIN,
    Y_AXIS_MAX,
    Y_AXIS_TEXT,
",".join(size_labels),
    ENLARGE_SEP_VALUE
)
)

##############################################################################
# Generate the nine series
##############################################################################

##############################################################################
# Generate the nine series
##############################################################################

for index, (
    strategy,
    variant,
    folding,
    tool,
    mode
) in enumerate(BAR_ORDER):

    shift = BAR_SHIFTS[index]

    color = COLORS[
        (strategy, folding)
    ]

    coordinates = []

    for size in sizes:

        value = times[
            (
                size,
                tool,
                mode,
                variant,
                folding,
            )
        ]

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
    # pattern only
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

legend_y1 = -1.05
legend_y2 = -1.70

box_w = 0.32
box_h = 0.22

text_dx = 0.15


###########################################################################
# First row: strategies
###########################################################################

for x, colour, label in [

    (0.8, "green", r"\maximevar"),
    (3.8, "red", r"\katjavar~(fixed)"),
    (6.8, "orange", r"\katjavar~(open)"),
    (10.0, "blue", r"\rubenvar"),

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
            legend_y1 + box_h / 2,
            label
        )
    )


###########################################################################
# Second row: execution types
###########################################################################

# YARSPG

x = 1.0

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {YARSPG};"
    %
    (
        x + box_w + text_dx,
        legend_y2 + box_h / 2
    )
)


# Cypher normal

x = 4.5

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x,
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
        x,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {Cypher normal};"
    %
    (
        x + box_w + text_dx,
        legend_y2 + box_h / 2
    )
)


# Cypher large-file

x = 9

latex.append(
    "\\draw[draw=black]"
    "(%.2f,%.2f) rectangle +(%.2f,%.2f);"
    %
    (
        x,
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
        x,
        legend_y2,
        box_w,
        box_h
    )
)

latex.append(
    "\\node[anchor=west] at (%.2f,%.2f) {Cypher large-file};"
    %
    (
        x + box_w + text_dx,
        legend_y2 + box_h / 2
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
