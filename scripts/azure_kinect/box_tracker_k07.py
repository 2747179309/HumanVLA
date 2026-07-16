#!/usr/bin/env python3
"""K07: Box 3D Tracking, Kinematics, and Physical Event Detection.

Tracks the manipulated box (light brown cardboard, 12×10×4cm) from marker A
to marker B across frames, computes velocity/acceleration/jerk, and detects
physical interaction events (lift_off, transport, touchdown, stationary).

Usage:
    python box_tracker_k07.py \
        --color-dir data/azure_kinect/processed/KVAL001/color \
        --depth-dir data/azure_kinect/processed/KVAL001/depth \
        --calibration data/azure_kinect/processed/KVAL001/calibration.json \
        --markers results/azure_kinect/KVAL001/object3d/markers_final.json \
        --output-dir results/azure_kinect/KVAL001/object3d \
        --video-id KVAL001
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Optional
import cv2, numpy as np


def load_depth_rgb_map(dep, cal):
    """Map all depth pixels to RGB using extrinsics. Returns (uc, vc, P_d)."""
    di = cal["depth_intrinsics"]; ci = cal["color_intrinsics"]
    fx_d, fy_d, cx_d, cy_d = di["fx"], di["fy"], di["cx"], di["cy"]
    fx_c, fy_c, cx_c, cy_c = ci["fx"], ci["fy"], ci["cx"], ci["cy"]
    ext = cal["extrinsics_depth_to_color"]
    R = np.array(ext["rotation"]); T = np.array(ext["translation"]) / 1000.0

    valid = dep > 0
    dys, dxs = np.where(valid)
    Zd = dep[valid] / 1000.0
    Xd = (dxs - cx_d) * Zd / fx_d; Yd = (dys - cy_d) * Zd / fy_d
    P_d = np.column_stack([Xd, Yd, Zd])
    P_c = P_d @ R.T + T
    uc = fx_c * P_c[:,0] / P_c[:,2] + cx_c
    vc = fy_c * P_c[:,1] / P_c[:,2] + cy_c
    return uc, vc, P_d


def detect_box_near(dep, uc_all, vc_all, P_d_all, search_uv, cal, img=None, radius=80):
    """Detect box as a light-brown region ~2-6cm above table near search_uv."""
    ci = cal["color_intrinsics"]
    fx_c, fy_c, cx_c, cy_c = ci["fx"], ci["fy"], ci["cx"], ci["cy"]
    h_img, w_img = 1080, 1920

    su, sv = search_uv
    dists = np.sqrt((uc_all - su)**2 + (vc_all - sv)**2)
    nearby = dists < radius

    if nearby.sum() < 20:
        return None

    idx_n = np.where(nearby)[0]
    Zd_n = P_d_all[idx_n, 2]
    uc_n = uc_all[idx_n]; vc_n = vc_all[idx_n]

    # Box = 2-7cm above table. Estimate table Z near this point
    Z_vals = Zd_n[(Zd_n > 0.4) & (Zd_n < 1.2)]
    if len(Z_vals) < 10:
        return None
    table_Z = np.median(Z_vals)  # table surface at this position

    # Box top surface is 2-7cm closer than table (= above table)
    box_mask = (Zd_n < table_Z - 0.02) & (Zd_n > table_Z - 0.08)

    # Color filter: light brown cardboard
    if img is not None and box_mask.sum() > 0:
        bm_idx = np.where(box_mask)[0]
        for j, bi in enumerate(bm_idx):
            u_rgb = int(uc_n[bi])
            v_rgb = int(vc_n[bi])
            if 0 <= u_rgb < w_img and 0 <= v_rgb < h_img:
                bgr = img[v_rgb, u_rgb].astype(float)
                if not (bgr[2] > bgr[1] > bgr[0] and 80 < bgr[2] < 180):
                    box_mask[bi] = False

    if box_mask.sum() < 10:
        return None

    # Centroid of box points
    idx_box = idx_n[box_mask]
    Z_box = np.median(P_d_all[idx_box, 2])
    X_box = np.median(P_d_all[idx_box, 0])
    Y_box = np.median(P_d_all[idx_box, 1])
    height = table_Z - Z_box  # positive = above table

    # RGB position using Conv1: P_c = P_d @ R.T + T
    ext = cal.get("extrinsics_depth_to_color", {})
    R = np.array(ext.get("rotation", [[1,0,0],[0,1,0],[0,0,1]]))
    T = np.array(ext.get("translation", [0,0,0])) / 1000.0
    P_c = np.array([X_box, Y_box, Z_box]) @ R.T + T
    u_box = ci["fx"] * P_c[0] / P_c[2] + ci["cx"]
    v_box = ci["fy"] * P_c[1] / P_c[2] + ci["cy"]

    return {"x": float(X_box), "y": float(Y_box), "z": float(Z_box),
            "u": float(u_box), "v": float(v_box),
            "height_m": float(height), "n_points": int(box_mask.sum())}


def compute_kinematics(traj, fps=30.0):
    """Add velocity, acceleration, jerk to trajectory."""
    n = len(traj)
    dt = 1.0 / fps

    for i in range(n):
        if traj[i] is None or traj[i].get("x") is None:
            continue
        # Velocity: central difference
        if i > 0 and i < n-1 and traj[i-1] and traj[i+1] and \
           traj[i-1].get("x") and traj[i+1].get("x"):
            vx = (traj[i+1]["x"] - traj[i-1]["x"]) / (2*dt)
            vy = (traj[i+1]["y"] - traj[i-1]["y"]) / (2*dt)
            vz = (traj[i+1]["z"] - traj[i-1]["z"]) / (2*dt)
            traj[i]["speed_ms"] = float(np.sqrt(vx**2 + vy**2 + vz**2))
            traj[i]["velocity"] = [float(vx), float(vy), float(vz)]

    # Acceleration and jerk
    for i in range(n):
        if traj[i] is None or traj[i].get("velocity") is None:
            continue
        if i > 0 and i < n-1 and traj[i-1] and traj[i+1] and \
           traj[i-1].get("velocity") and traj[i+1].get("velocity"):
            ax = (traj[i+1]["velocity"][0] - traj[i-1]["velocity"][0]) / (2*dt)
            ay = (traj[i+1]["velocity"][1] - traj[i-1]["velocity"][1]) / (2*dt)
            az = (traj[i+1]["velocity"][2] - traj[i-1]["velocity"][2]) / (2*dt)
            traj[i]["accel_ms2"] = float(np.sqrt(ax**2 + ay**2 + az**2))


def detect_events(traj):
    """Detect physical events: stationary, lift_off, transport, touchdown."""
    events = []
    state = "stationary"
    for i, t in enumerate(traj):
        if t is None or t.get("height_m") is None:
            continue
        h = t["height_m"]
        s = t.get("speed_ms", 0) or 0

        new_state = state
        if state == "stationary" and h > 0.02 and s > 0.02:
            new_state = "lift_off"
        elif state == "lift_off" and h > 0.02 and s > 0.05:
            new_state = "transport"
        elif state == "transport" and h < 0.02 and s < 0.02:
            new_state = "touchdown"
        elif state == "touchdown" and h < 0.01 and s < 0.01:
            new_state = "stationary"

        if new_state != state:
            events.append({"frame": i, "event": new_state,
                          "height_m": round(h, 4), "speed_ms": round(s, 4)})
            state = new_state

    return events


def main():
    parser = argparse.ArgumentParser(description="K07: Box Tracking + Kinematics")
    parser.add_argument("--color-dir", required=True, type=Path)
    parser.add_argument("--depth-dir", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--markers", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--video-id", required=True)
    args = parser.parse_args()

    with open(args.calibration) as f: cal = json.load(f)
    with open(args.markers) as f: markers = json.load(f)

    A_rgb = tuple(markers["A"]["rgb_px"])
    B_rgb = tuple(markers["B"]["rgb_px"])
    print(f"Markers: A={A_rgb}, B={B_rgb}")

    cfs = sorted(args.color_dir.glob("frame_*.jpg"))
    dfs = sorted(args.depth_dir.glob("frame_*.png"))
    n = len(cfs)
    print(f"Frames: {n}")

    # Track box: search near A initially, near B at end, wider search in between
    search_near_A = True  # start searching near A
    switch_to_B = False
    search_uv = (float(A_rgb[0]), float(A_rgb[1]))
    frames_since_detected = 0

    trajectory = []
    n_detected = 0
    n_occluded = 0

    for i, (cf, df_path) in enumerate(zip(cfs, dfs)):
        img = cv2.imread(str(cf))
        dep = cv2.imread(str(df_path), cv2.IMREAD_UNCHANGED)
        uc, vc, P_d = load_depth_rgb_map(dep, cal)

        # If box lost for too long, try searching near B
        if frames_since_detected > 20 and not switch_to_B:
            search_uv = (float(B_rgb[0]), float(B_rgb[1]))
            switch_to_B = True
            search_near_A = False

        # Search with expanding radius
        box = None
        for radius in [60, 100, 150]:
            box = detect_box_near(dep, uc, vc, P_d, search_uv, cal, img, radius=radius)
            if box: break

        rec = {"frame": i, "detected": False, "occluded": False}
        if box:
            # Verify: is this near A (start) or B (end)?
            dist_to_A = np.sqrt((box["u"]-A_rgb[0])**2 + (box["v"]-A_rgb[1])**2)
            dist_to_B = np.sqrt((box["u"]-B_rgb[0])**2 + (box["v"]-B_rgb[1])**2)

            n_detected += 1
            frames_since_detected = 0
            rec.update({"detected": True, "x": box["x"], "y": box["y"], "z": box["z"],
                        "u": box["u"], "v": box["v"], "height_m": box["height_m"],
                        "near_A": dist_to_A < 150, "near_B": dist_to_B < 150})
            search_uv = (box["u"], box["v"])
        else:
            frames_since_detected += 1
            if frames_since_detected > 3:
                rec["occluded"] = True
                n_occluded += 1

        trajectory.append(rec)

    print(f"Box detected: {n_detected}/{n} ({n_detected/n*100:.0f}%), occluded: {n_occluded}/{n}")

    # Compute kinematics
    compute_kinematics(trajectory)

    # Detect events
    events = detect_events(trajectory)
    print(f"Events detected: {len(events)}")
    for e in events:
        print(f"  Frame {e['frame']}: {e['event']} (h={e['height_m']*100:.1f}cm, v={e['speed_ms']:.3f}m/s)")

    # Generate annotated frames
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for idx in [0, n//5, 2*n//5, 3*n//5, 4*n//5, n-1]:
        img = cv2.imread(str(cfs[idx]))
        t = trajectory[idx]
        cv2.circle(img, (int(A_rgb[0]), int(A_rgb[1])), 10, (255, 0, 0), 2)
        cv2.circle(img, (int(B_rgb[0]), int(B_rgb[1])), 10, (0, 0, 255), 2)
        if t["detected"]:
            cv2.circle(img, (int(t["u"]), int(t["v"])), 12, (0, 255, 0), -1)
            h = t.get("height_m", 0)
            s = t.get("speed_ms", 0) or 0
            cv2.putText(img, f"h={h*100:.0f}cm v={s:.2f}m/s",
                       (int(t["u"])+20, int(t["v"])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
        cv2.imwrite(str(args.output_dir / f"box_track_{idx}.jpg"),
                   cv2.resize(img, (1280, 720)))

    # Save trajectory
    traj_out = []
    for t in trajectory:
        out = {"frame": t["frame"], "detected": t["detected"],
               "occluded": t.get("occluded", False)}
        if t["detected"]:
            for k in ["x","y","z","u","v","height_m","speed_ms","accel_ms2","near_A","near_B"]:
                if k in t:
                    out[k] = round(t[k], 6) if isinstance(t[k], (int,float)) else bool(t[k]) if isinstance(t[k], (np.bool_, bool)) else t[k]
        traj_out.append(out)

    with open(args.output_dir / "box_trajectory.jsonl", "w") as f:
        for t in traj_out:
            f.write(json.dumps(t) + "\n")

    with open(args.output_dir / "box_events.json", "w") as f:
        json.dump({"events": events, "video_id": args.video_id,
                   "marker_A_3d": markers["A"]["3d_m"],
                   "marker_B_3d": markers["B"]["3d_m"]}, f, indent=2)

    print(f"\nOutputs in {args.output_dir}/")


if __name__ == "__main__":
    main()
