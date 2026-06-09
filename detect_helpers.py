def build_rois(width, height):
    north = (width // 3, 0, width, height // 3)
    south = (0, 2 * height // 3, 2 * width // 3, height)
    west = (0, 0, width // 3, 2 * height // 3)
    east = (2 * width // 3, height // 3, width, height)

    return {
        "north": north,
        "south": south,
        "east": east,
        "west": west,
    }


def in_roi(roi, x, y):
    return (
        roi[0] < x < roi[2]
        and roi[1] < y < roi[3]
    )


def get_direction(rois, x, y):
    for name, roi in rois.items():
        if in_roi(roi, x, y):
            return name

    return None