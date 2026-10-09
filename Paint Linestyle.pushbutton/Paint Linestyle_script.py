# -*- coding: utf-8 -*-
"""Paint Region Edges

Modal palette of project line styles, centered on screen.

  * Apply to Selected Regions : sets the chosen line style on ALL edges of the
    Filled / Masking Regions currently selected.
  * Pick Edges                : the palette closes and you click near
    individual region edges in the active view; each click restyles that
    edge's sketch curve (same as Edit Boundary > Line Style). Press Esc to
    stop picking and the palette reopens.

Apply to Selected Regions finishes the command. Pick Edges keeps reopening
the palette after each Esc until you close it (Close button or the X).
The palette remembers its position and size between runs.
"""
__title__ = "Paint Linestyle"
__author__ = "Aaron Rumple, AIA"
__date__ = "2026-10-08"

import os
import json
import clr
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from pyrevit import forms, script
from Autodesk.Revit import DB
from Autodesk.Revit.Exceptions import OperationCanceledException
from System.Windows import (Thickness, VerticalAlignment, SystemParameters,
                            WindowStartupLocation, Visibility)
from System.Windows.Controls import (ListBoxItem, StackPanel, TextBlock,
                                     Orientation)
from System.Windows.Media import SolidColorBrush, Color
from System.Windows.Shapes import Rectangle

uidoc = __revit__.ActiveUIDocument  # noqa: F821  (provided by pyRevit)
doc = uidoc.Document
logger = script.get_logger()


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def id_value(eid):
    if hasattr(eid, "Value"):          # Revit 2024+
        return eid.Value
    return eid.IntegerValue


def lines_category():
    return doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_Lines)


def get_line_styles():
    """Return list of (name, graphics_style_id, weight, (r,g,b))."""
    result = []
    cat = lines_category()
    for sub in cat.SubCategories:
        gs = sub.GetGraphicsStyle(DB.GraphicsStyleType.Projection)
        if gs is None:
            continue
        w = sub.GetLineWeight(DB.GraphicsStyleType.Projection)
        try:
            w = int(w) if w is not None else 1
        except Exception:
            w = 1
        col = sub.LineColor
        rgb = (0, 0, 0)
        try:
            if col is not None and col.IsValid:
                rgb = (col.Red, col.Green, col.Blue)
        except Exception:
            pass
        result.append((sub.Name, gs.Id, w, rgb))
    result.sort(key=lambda t: t[0].lower())
    return result


def region_collector(view):
    return (DB.FilteredElementCollector(doc, view.Id)
            .OfClass(DB.FilledRegion)
            .WhereElementIsNotElementType())


def region_sketch_curves(fr):
    """The curve elements that make up a region's boundary sketch."""
    out = []
    try:
        ids = fr.GetDependentElements(DB.ElementClassFilter(DB.CurveElement))
    except Exception:
        return out
    for eid in ids:
        el = doc.GetElement(eid)
        if isinstance(el, DB.CurveElement):
            out.append(el)
    return out


def set_curve_style(ce, graphics_style):
    """Set the Line Style of one sketch curve. Returns True on success."""
    try:
        ce.LineStyle = graphics_style
        return True
    except Exception:
        pass
    try:
        p = ce.get_Parameter(DB.BuiltInParameter.BUILDING_CURVE_GSTYLE)
        if p is not None and not p.IsReadOnly:
            return bool(p.Set(graphics_style.Id))
    except Exception:
        pass
    return False


def shake_region(view, fr):
    """Nudge a region and put it straight back so Revit redraws its edges.

    Must be called inside an open transaction. Returns True on success; False
    if the region could not be moved (pinned, in a group, etc.).
    """
    try:
        v = view.RightDirection.Multiply(0.01)   # 0.01 ft in the view plane
        DB.ElementTransformUtils.MoveElement(doc, fr.Id, v)
        doc.Regenerate()
        DB.ElementTransformUtils.MoveElement(doc, fr.Id, v.Negate())
        return True
    except Exception as ex:
        logger.debug("shake_region failed: {}".format(ex))
        return False


def nearest_edge(view, pt):
    """Closest region sketch curve to pt within a view-scale tolerance.

    Returns (best, seen_any_curves); best is
    (distance, curve_element, filled_region) or None.
    """
    tol = 0.01 * max(view.Scale, 1)   # ~3 mm on paper, in feet
    best = None
    seen = False
    for fr in region_collector(view):
        for ce in region_sketch_curves(fr):
            seen = True
            try:
                crv = ce.GeometryCurve
                ir = crv.Project(pt) if crv is not None else None
            except Exception:
                ir = None
            if ir is None:
                continue
            d = ir.Distance
            if d <= tol and (best is None or d < best[0]):
                best = (d, ce, fr)
    return best, seen


# ----------------------------------------------------------------------------
# actions
# ----------------------------------------------------------------------------
def apply_to_selected(style_id):
    regions = []
    for eid in uidoc.Selection.GetElementIds():
        el = doc.GetElement(eid)
        if isinstance(el, DB.FilledRegion):
            regions.append(el)
    if not regions:
        forms.alert("Select one or more Filled or Masking Regions first.",
                    title="Paint Region Edges")
        return
    t = DB.Transaction(doc, "Paint region edges (whole region)")
    t.Start()
    try:
        view = uidoc.ActiveView
        gs = doc.GetElement(style_id)
        failed = 0
        for fr in regions:
            # Restyle every sketch edge directly. FilledRegion.SetLineStyleId
            # only accepts a limited set of line styles, so it is used only
            # as a fallback when no sketch curves can be found.
            curves = region_sketch_curves(fr)
            if curves:
                results = [set_curve_style(ce, gs) for ce in curves]
                if not all(results):
                    failed += 1
            else:
                try:
                    fr.SetLineStyleId(style_id)
                except Exception:
                    failed += 1
            shake_region(view, fr)
        t.Commit()
        if failed:
            forms.alert("{} region(s) could not be fully restyled with this "
                        "line style.".format(failed),
                        title="Paint Region Edges")
    except Exception as ex:
        t.RollBack()
        forms.alert("Failed: {}".format(ex), title="Paint Region Edges")


def pick_edges(style_id):
    view = uidoc.ActiveView
    if isinstance(view, (DB.View3D, DB.ViewSchedule)):
        forms.alert("Open a 2D view (plan, section, drafting view...) first.",
                    title="Paint Region Edges")
        return
    gs = doc.GetElement(style_id)
    shake_warned = False
    prompt = "Click near a region edge to paint it (Esc to return to palette)"
    while True:
        try:
            pt = uidoc.Selection.PickPoint(prompt)
        except OperationCanceledException:
            return
        except Exception as ex:
            forms.alert("Could not start edge picking:\n{}".format(ex),
                        title="Paint Region Edges")
            return
        hit, seen = nearest_edge(view, pt)
        if hit is None:
            if not seen:
                forms.alert(
                    "No region sketch curves were found in this view.\n"
                    "Make sure the view contains Filled or Masking Regions.",
                    title="Paint Region Edges")
                return
            prompt = ("No region edge there - click closer to an edge "
                      "(Esc to return to palette)")
            continue
        prompt = "Click near a region edge to paint it (Esc to return to palette)"
        t = DB.Transaction(doc, "Paint region edge")
        t.Start()
        try:
            if not set_curve_style(hit[1], gs):
                t.RollBack()
                forms.alert("Revit would not let this edge's line style be "
                            "changed through the API.",
                            title="Paint Region Edges")
                return
            shaken = shake_region(view, hit[2])
            t.Commit()
            if not shaken and not shake_warned:
                shake_warned = True
                forms.alert(
                    "The edge was restyled, but the region could not be "
                    "nudged to refresh its display (pinned or in a group?).\n"
                    "The new style may not show until the region is "
                    "regenerated.",
                    title="Paint Region Edges")
        except Exception as ex:
            t.RollBack()
            forms.alert("Failed: {}".format(ex), title="Paint Region Edges")
            return


# ----------------------------------------------------------------------------
# palette
# ----------------------------------------------------------------------------
SETTINGS_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Paint_Region_Edges_palette.json")


def load_geometry():
    try:
        with open(SETTINGS_FILE) as f:
            g = json.load(f)
        return dict((k, float(g[k])) for k in ("left", "top", "width", "height"))
    except Exception:
        return None


def save_geometry(win):
    """Write the window's normal (non-maximized) bounds to the settings file.

    Called from the window's Closing event, so it runs for every way the
    palette can close: Apply, Pick Edges, Close, or the X.
    """
    try:
        rb = win.RestoreBounds          # valid whether or not maximized
        if rb.IsEmpty or rb.Width <= 0 or rb.Height <= 0:
            rb = None
        if rb is not None:
            g = {"left": rb.Left, "top": rb.Top,
                 "width": rb.Width, "height": rb.Height}
        else:
            g = {"left": win.Left, "top": win.Top,
                 "width": win.Width, "height": win.Height}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(g, f)
    except Exception as ex:
        logger.error("Could not save palette position/size: {}".format(ex))


XAML = """
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Paint Region Edges" Width="270" Height="460"
        MinWidth="220" MinHeight="300" ShowInTaskbar="False"
        WindowStartupLocation="CenterScreen">
    <Grid Margin="8">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        <TextBlock Grid.Row="0" Text="Project line styles" FontWeight="SemiBold"
                   Margin="0,0,0,4"/>
        <TextBox x:Name="search_box" Grid.Row="1" Height="24" Margin="0,0,0,4"
                 VerticalContentAlignment="Center"
                 ToolTip="Type to filter line styles"
                 TextChanged="search_changed"/>
        <ListBox x:Name="style_list" Grid.Row="2" HorizontalContentAlignment="Stretch"/>
        <StackPanel Grid.Row="3" Margin="0,8,0,0">
            <Button Content="Apply to Selected Regions" Height="28"
                    Click="apply_selected" Margin="0,0,0,4"/>
            <Button Content="Pick Edges..." Height="28"
                    Click="pick_edges_click" Margin="0,0,0,4"/>
            <Button Content="Close" Height="24" Click="close_click"/>
        </StackPanel>
        <TextBlock x:Name="status" Grid.Row="4" Margin="0,6,0,0"
                   TextWrapping="Wrap" Foreground="#666666" FontSize="11"
                   Text="Pick a style, then choose an action."/>
    </Grid>
</Window>
"""


class PaintPalette(forms.WPFWindow):
    def __init__(self, last_style_id=None):
        forms.WPFWindow.__init__(self, XAML, literal_string=True)
        self.action = None      # "apply", "pick" or None (closed)
        self.style_id = None
        self.all_items = []     # (lower-case name, ListBoxItem)
        self.populate(last_style_id)
        self.restore_geometry()
        self.Closing += self.on_closing
        self.Loaded += self.on_loaded

    def on_loaded(self, sender, args):
        self.search_box.Focus()

    def on_closing(self, sender, args):
        save_geometry(self)

    def search_changed(self, sender, args):
        self.apply_filter()

    def apply_filter(self):
        text = (self.search_box.Text or "").strip().lower()
        terms = text.split()
        shown = []
        for name, item in self.all_items:
            match = all(t in name for t in terms)
            item.Visibility = Visibility.Visible if match else Visibility.Collapsed
            if match:
                shown.append(item)
        sel = self.style_list.SelectedItem
        if sel is not None and sel.Visibility != Visibility.Visible:
            self.style_list.SelectedItem = None
        if terms and len(shown) == 1:
            self.style_list.SelectedItem = shown[0]
        if not shown:
            self.status.Text = "No line styles match."
        elif self.status.Text == "No line styles match.":
            self.status.Text = "Pick a style, then choose an action."

    def restore_geometry(self):
        g = load_geometry()
        if not g:
            return
        vl, vt = SystemParameters.VirtualScreenLeft, SystemParameters.VirtualScreenTop
        vw, vh = SystemParameters.VirtualScreenWidth, SystemParameters.VirtualScreenHeight
        w = max(g["width"], self.MinWidth)
        h = max(g["height"], self.MinHeight)
        # ignore saved bounds that would leave the title bar off every screen
        if (g["left"] + 50 > vl + vw or g["left"] + w - 50 < vl or
                g["top"] < vt - 5 or g["top"] + 30 > vt + vh):
            return
        self.WindowStartupLocation = WindowStartupLocation.Manual
        self.Left = g["left"]
        self.Top = g["top"]
        self.Width = w
        self.Height = h

    def populate(self, last_style_id):
        self.style_list.Items.Clear()
        self.all_items = []
        for name, gid, weight, rgb in get_line_styles():
            item = ListBoxItem()
            item.Tag = gid
            sp = StackPanel()
            sp.Orientation = Orientation.Horizontal

            swatch = Rectangle()
            swatch.Width = 56
            swatch.Height = max(1, min(weight, 16))
            swatch.Fill = SolidColorBrush(Color.FromRgb(rgb[0], rgb[1], rgb[2]))
            swatch.VerticalAlignment = VerticalAlignment.Center
            swatch.Margin = Thickness(0, 0, 8, 0)

            label = TextBlock()
            label.Text = name
            label.VerticalAlignment = VerticalAlignment.Center

            sp.Children.Add(swatch)
            sp.Children.Add(label)
            item.Content = sp
            self.style_list.Items.Add(item)
            self.all_items.append((name.lower(), item))
            if (last_style_id is not None and
                    id_value(gid) == id_value(last_style_id)):
                self.style_list.SelectedItem = item
                self.style_list.ScrollIntoView(item)

    def choose(self, action):
        item = self.style_list.SelectedItem
        if item is None:
            self.status.Text = "Select a line style first."
            return
        self.style_id = item.Tag
        self.action = action
        self.Close()

    def apply_selected(self, sender, args):
        self.choose("apply")

    def pick_edges_click(self, sender, args):
        self.choose("pick")

    def close_click(self, sender, args):
        self.action = None
        self.Close()


# ----------------------------------------------------------------------------
# main loop: palette -> action -> palette ... until the palette is closed
# ----------------------------------------------------------------------------
last_style_id = None
while True:
    palette = PaintPalette(last_style_id)
    palette.show_dialog()      # geometry is saved by the window's Closing event
    if palette.action is None:
        break
    last_style_id = palette.style_id
    if palette.action == "apply":
        apply_to_selected(last_style_id)
        break
    elif palette.action == "pick":
        pick_edges(last_style_id)