import csv
import importlib
import os

try:
    App = importlib.import_module("FreeCAD")
    Import = importlib.import_module("Import")
except ModuleNotFoundError:
    App = None
    Import = None

def export_assembly(assembly_csv, parts_dir, outdir):
    if App is None or Import is None:
        raise RuntimeError(
            "FreeCAD modules are not available. Run this from a FreeCAD Python environment."
        )

    doc = App.newDocument("Assembly")
    with open(assembly_csv, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            part_file = os.path.join(parts_dir, row["part"] + ".step")
            if not os.path.exists(part_file):
                print(f"Warning: {part_file} not found, skipping")
                continue

            shape = Import.open(part_file)
            obj = doc.addObject("Part::Feature", row["part"])
            obj.Shape = shape[0].Shape  # import returns list
            obj.Placement.Base = App.Vector(float(row["tx"]), float(row["ty"]), float(row["tz"]))
            obj.Placement.Rotation = App.Rotation(
                float(row["rx"]), float(row["ry"]), float(row["rz"])
            )

    # save FreeCAD file
    fcstd_path = os.path.join(outdir, "assembly.FCStd")
    doc.saveAs(fcstd_path)

    # export STEP (AP242)
    step_path = os.path.join(outdir, "assembly.step")
    Import.export(doc.Objects, step_path)

    print(f"Assembly exported: {fcstd_path}, {step_path}")
