import cv2
from ultralytics import YOLO

from vision_utils import (
    enhance,
    load_stop_lines,
    collect_stop_lines,
    save_stop_lines,
    roi_center,
    line_side,
    side_sign,
)

from detect_helpers import (
    build_rois,
    get_direction,
)


def run_detection(video_path="traffic.mp4", model_path="yolov8s.pt"):
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Error opening video")
        return

    ret, first_frame = cap.read()

    if not ret:
        print("Error reading first frame")
        return

    height, width, _ = first_frame.shape

    rois = build_rois(width, height)

    stop_lines = load_stop_lines()

    if stop_lines is None:
        stop_lines = collect_stop_lines(first_frame, rois)

        if stop_lines is None:
            return

        save_stop_lines(stop_lines)

    approach_side = {}

    for direction, roi in rois.items():
        center = roi_center(roi)

        side = side_sign(
            line_side(
                stop_lines[direction],
                center,
            )
        )

        approach_side[direction] = side if side != 0 else 1

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    cv2.namedWindow("Traffic Detection")
    cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("Controls", 420, 160)

    cv2.createTrackbar(
        "Gamma x10",
        "Controls",
        14,
        30,
        lambda x: None,
    )

    cv2.createTrackbar(
        "CLAHE clip x10",
        "Controls",
        30,
        80,
        lambda x: None,
    )

    cv2.createTrackbar(
        "CLAHE tile",
        "Controls",
        8,
        16,
        lambda x: None,
    )

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        gamma = max(
            1,
            cv2.getTrackbarPos("Gamma x10", "Controls"),
        ) / 10.0

        clip_limit = max(
            1,
            cv2.getTrackbarPos("CLAHE clip x10", "Controls"),
        ) / 10.0

        tile_size = max(
            2,
            cv2.getTrackbarPos("CLAHE tile", "Controls"),
        )

        enhanced_frame = enhance(
            frame,
            gamma=gamma,
            clip_limit=clip_limit,
            tile_size=tile_size,
        )

        results = model(
            enhanced_frame,
            stream=True,
            conf=0.2,
            iou=0.5,
            classes=[2, 3, 5, 7],
            agnostic_nms=True,
            max_det=200,
            verbose=False,
        )

        counts = {
            "north": 0,
            "east": 0,
            "south": 0,
            "west": 0,
        }

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                direction = get_direction(
                    rois,
                    cx,
                    cy,
                )

                if direction is None:
                    continue

                side = side_sign(
                    line_side(
                        stop_lines[direction],
                        (cx, cy),
                    )
                )

                on_approach = (
                    side == approach_side[direction]
                    or side == 0
                )

                if not on_approach:
                    continue

                counts[direction] += 1

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2,
                )

        traffic_vector = (
            counts["north"],
            counts["east"],
            counts["south"],
            counts["west"],
        )

        cv2.putText(
            frame,
            f"Vector: {traffic_vector}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        print(traffic_vector)

        brown = (42, 42, 165)

        for line in stop_lines.values():
            cv2.line(
                frame,
                line[0],
                line[1],
                brown,
                2,
            )

        cv2.imshow(
            "Traffic Detection",
            frame,
        )

        if cv2.waitKey(100) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_detection()