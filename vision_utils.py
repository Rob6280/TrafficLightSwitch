import cv2
import numpy as np
import json
import os

def enhance(frame, gamma=1.4, clip_limit=3.0, tile_size=8):
    # Gamma correction to lift shadows before local contrast enhancement.
    inv_gamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv_gamma * 255 for i in range(256)], dtype="uint8")
    corrected = cv2.LUT(frame, table)

    lab = cv2.cvtColor(corrected, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    cl = clahe.apply(l)

    limg = cv2.merge((cl, a, b))
    return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)


def line_side(line, point):
    (x1, y1), (x2, y2) = line
    return (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)


def side_sign(value, eps=1e-6):
    if value >= eps:
        return 1
    if value <= -eps:
        return -1
    return 0


def roi_center(roi):
    return ((roi[0] + roi[2]) // 2, (roi[1] + roi[3]) // 2)


def lines_path():
    return os.path.join(os.path.dirname(__file__), "stop_lines.json")


def load_stop_lines():
    path = lines_path()
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = {}
    for key, pts in data.items():
        if len(pts) == 2:
            lines[key] = (tuple(pts[0]), tuple(pts[1]))
    return lines if lines else None


def save_stop_lines(lines):
    path = lines_path()
    data = {k: [list(v[0]), list(v[1])] for k, v in lines.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def collect_stop_lines(frame, rois):
    directions = ["north", "south", "east", "west"]
    colors = {
        "north": (255, 0, 0),
        "south": (0, 255, 0),
        "west": (0, 0, 255),
        "east": (255, 255, 0),
    }
    brown = (42, 42, 165)
    window = "Mark Stop Lines"
    points = []
    lines = {}
    mouse_pos = None
    idx = 0

    def on_mouse(event, x, y, flags, param):
        nonlocal points, mouse_pos
        mouse_pos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_mouse)
    print("Mark stop lines: click 2 points per direction in order North, South, East, West.")
    print("Keys: r=redo current, c=clear all, q=quit.")

    while True:
        canvas = frame.copy()
        for name, roi in rois.items():
            cv2.rectangle(
                canvas,
                (roi[0], roi[1]),
                (roi[2], roi[3]),
                colors[name],
                2,
            )
            cv2.putText(
                canvas,
                name.upper(),
                (roi[0] + 6, roi[1] + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                colors[name],
                2,
            )

        for name, line in lines.items():
            cv2.line(canvas, line[0], line[1], brown, 2)

        if idx < len(directions):
            label = directions[idx].upper()
            cv2.putText(
                canvas,
                f"Click 2 points for {label} line (r redo, c clear, q quit)",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        if len(points) == 1 and mouse_pos is not None:
            cv2.circle(canvas, points[0], 4, (0, 255, 255), -1)
            cv2.line(canvas, points[0], mouse_pos, (0, 255, 255), 1)

        cv2.imshow(window, canvas)
        key = cv2.waitKey(20) & 0xFF

        if key == ord("q"):
            cv2.destroyWindow(window)
            return None
        if key == ord("r"):
            points = []
        if key == ord("c"):
            points = []
            lines = {}
            idx = 0

        if len(points) == 2 and idx < len(directions):
            lines[directions[idx]] = (points[0], points[1])
            points = []
            idx += 1
            if idx >= len(directions):
                break

    cv2.destroyWindow(window)
    return lines
