# Paint Linestyle

![Paint Linestyle icon](icon.png)

A **pyRevit** tool for changing the boundary line styles of **Filled
Regions** and **Masking Regions** in Autodesk Revit.

Paint Linestyle provides two workflows:

-   **Apply to Selected Regions** --- change every boundary edge of one
    or more selected regions.
-   **Pick Edges** --- interactively click near individual region edges
    and change only those edges.

Unlike a whole-region line-style change, **Pick Edges** allows different
edges of the same Filled or Masking Region to use different project line
styles.

## Features

-   Supports **Filled Regions** and **Masking Regions**
-   Changes all edges of preselected regions
-   Paints individual boundary edges
-   Uses the project's existing **Line Styles**
-   Searchable line-style palette
-   Displays line color and approximate line-weight previews
-   Multi-word, case-insensitive filtering
-   Automatically selects the style when a search produces one match
-   Remembers the palette position and size between runs
-   Remembers the last selected style during the current command
-   View-scale-dependent edge-picking tolerance
-   Works directly with region boundary sketch curves
-   Attempts to force a Revit display refresh after changing an edge
-   Revit 2024+ `ElementId.Value` compatibility with fallback to
    `IntegerValue`

## User Interface

The palette contains:

1.  **Project line styles** --- all available project line styles.
2.  **Search** --- filters the list as you type.
3.  **Line-style preview** --- shows the line color and an approximate
    representation of line weight.
4.  **Apply to Selected Regions** --- changes all boundary edges of the
    selected regions.
5.  **Pick Edges...** --- enters interactive individual-edge painting.
6.  **Close** --- exits without making another change.

The palette remembers its last screen position and size.

## Workflow 1 --- Apply to Selected Regions

Use this workflow when all boundary edges of a region should use the
same line style.

1.  Select one or more Filled Regions and/or Masking Regions in Revit.
2.  Run **Paint Linestyle**.
3.  Search for and select the desired project line style.
4.  Click **Apply to Selected Regions**.
5.  The tool changes every accessible boundary edge of each selected
    region.

Non-region elements in the current Revit selection are ignored.

If no Filled or Masking Regions are selected, the tool asks you to
select regions first.

> **Note:** Apply to Selected Regions completes the command after the
> change is made.

## Workflow 2 --- Pick Individual Edges

Use this workflow when different sides of a region need different
graphic treatment.

1.  Run **Paint Linestyle**.
2.  Select the desired project line style.
3.  Click **Pick Edges...**.
4.  Click near a Filled Region or Masking Region boundary.
5.  Continue clicking additional edges to apply the same style.
6.  Press **Esc** to stop picking and return to the palette.
7.  Select another line style and repeat, or click **Close**.

You do not need to click exactly on the sketch curve. The script
searches for the nearest region boundary within a view-scale-dependent
tolerance of approximately **3 mm on paper**.

This makes it possible to create region graphics such as:

``` text
        Heavy / emphasized edge
        ========================
        |                     |
 Thin   |    FILLED REGION    |  Invisible / alternate style
 edge   |                     |
        -----------------------
             Thin edge
```

Each edge can retain its own project line style.

## Supported Views

**Apply to Selected Regions** operates on selected region elements.

**Pick Edges** is intended for 2D Revit views containing accessible
region sketch curves, including:

-   Floor Plans
-   Reflected Ceiling Plans
-   Sections
-   Elevations
-   Detail Views
-   Drafting Views

Individual edge picking is not supported in:

-   3D Views
-   Schedules

## How It Works

For individual edge painting, the script finds the `CurveElement`
objects that form the Filled Region or Masking Region boundary and
changes the selected curve's graphics style.

For whole-region changes, the tool first attempts to change each sketch
edge directly. This allows it to use project line styles that may not be
accepted by the normal `FilledRegion.SetLineStyleId()` method.

If accessible sketch curves cannot be found, the script falls back to:

``` python
FilledRegion.SetLineStyleId(style_id)
```

For an individual sketch curve, the script first attempts:

``` python
curve_element.LineStyle = graphics_style
```

and falls back to the curve's `BUILDING_CURVE_GSTYLE` parameter when
necessary.

## Display Refresh

After changing a region boundary, Paint Linestyle briefly moves the
region approximately `0.01 ft` in the view plane and immediately moves
it back.

This is used only to encourage Revit to redraw the modified boundary. It
is **not intended to change the region's final location**.

Pinned, grouped, or otherwise constrained regions may prevent this
refresh operation. The line-style change can still succeed, but the new
appearance may not become visible until Revit regenerates or refreshes
the element.

## Search Behavior

The line-style search is:

-   Case-insensitive
-   Space-delimited
-   An **AND** search

For example:

``` text
detail med
```

matches a line style only when both `detail` and `med` occur in its
name.

When only one matching style remains, the tool automatically selects it.

## Installation

Place the pushbutton files in a pyRevit extension structure similar to:

``` text
PyPiPie.extension/
└── PyPiPie.tab/
    └── Annotation.panel/
        └── Filled Regions.pulldown/
            └── Paint Linestyle.pushbutton/
                ├── Paint Linestyle_script.py
                ├── bundle.yaml
                ├── help.html
                └── icon.png
```

The exact tab, panel, and pulldown names may be changed to match your
extension.

A typical `bundle.yaml` is:

``` yaml
title: Paint Linestyle
tooltip: |
  Paints edges in a masking or filled region with a new linestyle.
author: Aaron Rumple, AIA
date: 2026-10-08
```

## Requirements

-   Autodesk Revit
-   pyRevit
-   IronPython-compatible pyRevit environment
-   .NET/WPF
-   A Revit project containing Filled Regions or Masking Regions

The script uses the Revit API, pyRevit forms, and WPF controls directly.

## Settings

Palette position and size are stored in:

``` text
%APPDATA%\Paint_Region_Edges_palette.json
```

Deleting this file resets the saved palette geometry. The script will
recreate it the next time the palette closes.

## Limitations

-   Only existing **project line styles** are listed; the tool does not
    create line styles.
-   Individual edge painting depends on accessible region boundary
    sketch curves.
-   Edge picking searches Filled/Masking Regions in the active view.
-   A click must fall within the calculated picking tolerance of a
    region boundary.
-   Revit may reject some line-style changes depending on the region,
    sketch curve, project state, grouping, ownership, or other API
    restrictions.
-   Pinned or grouped regions may not visually refresh immediately.
-   The display-refresh nudge is not guaranteed to work on every region.
-   Pick Edges is not available in 3D views or schedules.
-   The tool changes graphics only; it does not alter the region's
    intended boundary geometry.

## Messages and Troubleshooting

### Select a line style first.

Choose a line style in the palette before clicking an action.

### No region edge there --- click closer to an edge

The selected point is outside the edge-picking tolerance. Click closer
to the visible region boundary.

### No region sketch curves were found in this view.

The active view does not contain region boundary curves that the tool
can access.

### Revit would not let this edge's line style be changed through the API.

Revit rejected the boundary graphics change. Confirm that the region is
editable and try another edge or region.

### The new style does not immediately appear.

The style may already have been changed, but Revit could not perform the
temporary display-refresh nudge. Regenerate the view or otherwise
refresh the region.

## Recommended Use

Use **Apply to Selected Regions** when the entire perimeter should have
one consistent graphic style.

Use **Pick Edges** when only selected sides need:

-   Emphasis
-   Suppression
-   Invisible lines
-   Different line weights
-   Different colors
-   Project-specific graphic conventions

A fast workflow is:

``` text
Search style
    ↓
Pick Edges
    ↓
Paint several edges
    ↓
Esc
    ↓
Choose another style
    ↓
Continue painting
```

## Files

  File                          Purpose
  ----------------------------- --------------------------
  `Paint Linestyle_script.py`   Main pyRevit command
  `bundle.yaml`                 pyRevit button metadata
  `icon.png`                    Toolbar icon
  `help.html`                   Detailed in-product help
  `README.md`                   GitHub documentation

## Author

**Aaron Rumple, AIA**

Script date: **October 8, 2026**

## License

Add the license used by the parent **PyPiPie** repository here, or
remove this section if licensing is documented at the repository root.

------------------------------------------------------------------------

Part of the **PyPiPie** pyRevit toolset.
