"""Shared shell proportions; keep the working head, grip and semantic sockets unchanged."""
from mathutils import Matrix, Vector

SLIM_HOUSING = (0.70, 0.64, 0.68)


def slim_housing(objects):
    anchor = Vector((0, 0.10, 0.084))
    transform = Matrix.Translation(anchor) @ Matrix.Diagonal((*SLIM_HOUSING, 1)) @ Matrix.Translation(-anchor)
    for obj in objects:
        if obj.type != "MESH" or "Grip" in obj.name:
            continue
        # Bake the affine change into local geometry, keeping exported scale exactly one.
        obj.data.transform(obj.matrix_world.inverted() @ transform @ obj.matrix_world)
        obj.data.update()
