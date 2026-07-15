#!/usr/bin/env python3
"""Shared constants and definitions for Azure Kinect data processing.

This module provides the canonical reference for:
- Kinect SDK 32-joint names and indices
- Confidence level enum mapping
- Bone (skeleton connection) definitions
- BODY_25 to Kinect joint mapping
- Quality classification rules

All other scripts in this directory should import from here rather than
duplicating these definitions.
"""

from __future__ import annotations
from enum import IntEnum
from typing import Dict, List, Tuple

# ============================================================================
# 1. Azure Kinect SDK 32-joint topology (in SDK index order)
# ============================================================================

KINECT_JOINT_NAMES: List[str] = [
    "PELVIS",              # 0
    "SPINE_NAVAL",         # 1
    "SPINE_CHEST",         # 2
    "NECK",                # 3
    "CLAVICLE_LEFT",       # 4
    "SHOULDER_LEFT",       # 5
    "ELBOW_LEFT",          # 6
    "WRIST_LEFT",          # 7
    "CLAVICLE_RIGHT",      # 8
    "SHOULDER_RIGHT",      # 9
    "ELBOW_RIGHT",         # 10
    "WRIST_RIGHT",         # 11
    "HIP_LEFT",            # 12
    "KNEE_LEFT",           # 13
    "ANKLE_LEFT",          # 14
    "FOOT_LEFT",           # 15
    "HIP_RIGHT",           # 16
    "KNEE_RIGHT",          # 17
    "ANKLE_RIGHT",         # 18
    "FOOT_RIGHT",          # 19
    "HEAD",                # 20
    "NOSE",                # 21
    "EYE_LEFT",            # 22
    "EAR_LEFT",            # 23
    "EYE_RIGHT",           # 24
    "EAR_RIGHT",           # 25
    "WRIST_THUMB_LEFT",    # 26 (hand tip)
    "BICEPS_LEFT",         # 27 (arm)
    "WRIST_THUMB_RIGHT",   # 28 (hand tip)
    "BICEPS_RIGHT",        # 29 (arm)
    "BACK_LEFT",           # 30
    "BACK_RIGHT",          # 31
]

KINECT_JOINT_COUNT: int = len(KINECT_JOINT_NAMES)
assert KINECT_JOINT_COUNT == 32, f"Expected 32 Kinect joints, got {KINECT_JOINT_COUNT}"

# Reverse lookup: joint name -> SDK index
KINECT_JOINT_INDEX: Dict[str, int] = {name: i for i, name in enumerate(KINECT_JOINT_NAMES)}


# ============================================================================
# 2. Confidence level enum (matching k4abt_joint_confidence_level_t)
# ============================================================================

class KinectConfidence(IntEnum):
    """Azure Kinect Body Tracking SDK confidence levels.

    Source: k4abt_joint_confidence_level_t in <k4abt/types.h>
    """
    NONE = 0     # Joint is not observed; position is inferred or default
    LOW = 1      # Joint is inferred from limited depth evidence
    MEDIUM = 2   # Joint is based on medium-quality depth data
    HIGH = 3     # Joint is based on high-quality depth data

    @classmethod
    def to_normalized(cls, level: int) -> float:
        """Convert SDK confidence level to [0, 1] range."""
        mapping = {0: 0.0, 1: 0.33, 2: 0.67, 3: 1.0}
        return mapping.get(level, 0.0)

    @classmethod
    def is_reference_valid(cls, level: int) -> bool:
        """Whether a confidence level qualifies as reference_valid."""
        return level >= cls.MEDIUM

    @classmethod
    def quality_tier(cls, level: int) -> str:
        """Map confidence level to quality tier string."""
        if level == cls.HIGH:
            return "high"
        elif level == cls.MEDIUM:
            return "medium"
        elif level == cls.LOW:
            return "low"
        else:
            return "unusable"


# ============================================================================
# 3. Skeleton bone connections (for visualization and bone-length analysis)
# ============================================================================

# Each tuple is (parent_joint_index, child_joint_index) in SDK order
KINECT_BONES: List[Tuple[int, int]] = [
    # Spine / torso
    (0, 1),   # PELVIS -> SPINE_NAVAL
    (1, 2),   # SPINE_NAVAL -> SPINE_CHEST
    (2, 3),   # SPINE_CHEST -> NECK
    (3, 26),  # (not standard) NECK -> WRIST_THUMB_LEFT (placeholder)
    # Left arm
    (2, 4),   # SPINE_CHEST -> CLAVICLE_LEFT
    (4, 5),   # CLAVICLE_LEFT -> SHOULDER_LEFT
    (5, 6),   # SHOULDER_LEFT -> ELBOW_LEFT
    (6, 7),   # ELBOW_LEFT -> WRIST_LEFT
    # Right arm
    (2, 11),  # SPINE_CHEST -> ... (legacy, incorrect)
    (11, 12), # ...
    (12, 13),
    (13, 14),
    # Left leg
    (0, 22),  # PELVIS -> EYE_LEFT (legacy, incorrect)
    (22, 23),
    (23, 24),
    # Right leg
    (0, 18),  # PELVIS -> ANKLE_RIGHT (legacy, incorrect)
    (18, 19),
    (19, 20),
]

# Corrected bone definitions based on Kinect SDK anatomy
KINECT_BONES_CORRECTED: List[Tuple[int, int]] = [
    # Torso
    (0, 1),   # PELVIS -> SPINE_NAVAL
    (1, 2),   # SPINE_NAVAL -> SPINE_CHEST
    (2, 3),   # SPINE_CHEST -> NECK
    (3, 20),  # NECK -> HEAD
    (20, 21), # HEAD -> NOSE
    # Left arm
    (3, 4),   # NECK -> CLAVICLE_LEFT
    (4, 5),   # CLAVICLE_LEFT -> SHOULDER_LEFT
    (5, 6),   # SHOULDER_LEFT -> ELBOW_LEFT
    (6, 7),   # ELBOW_LEFT -> WRIST_LEFT
    # Right arm
    (3, 8),   # NECK -> CLAVICLE_RIGHT
    (8, 9),   # CLAVICLE_RIGHT -> SHOULDER_RIGHT
    (9, 10),  # SHOULDER_RIGHT -> ELBOW_RIGHT
    (10, 11), # ELBOW_RIGHT -> WRIST_RIGHT
    # Left leg
    (0, 12),  # PELVIS -> HIP_LEFT
    (12, 13), # HIP_LEFT -> KNEE_LEFT
    (13, 14), # KNEE_LEFT -> ANKLE_LEFT
    (14, 15), # ANKLE_LEFT -> FOOT_LEFT
    # Right leg
    (0, 16),  # PELVIS -> HIP_RIGHT
    (16, 17), # HIP_RIGHT -> KNEE_RIGHT
    (17, 18), # KNEE_RIGHT -> ANKLE_RIGHT
    (18, 19), # ANKLE_RIGHT -> FOOT_RIGHT
]

# Bones relevant for upper-body task analysis
UPPER_BODY_BONES: List[Tuple[int, int, str]] = [
    (3, 20, "neck_to_head"),
    (3, 4, "neck_to_l_clavicle"),
    (4, 5, "l_clavicle_to_shoulder"),
    (5, 6, "l_shoulder_to_elbow"),
    (6, 7, "l_elbow_to_wrist"),
    (3, 8, "neck_to_r_clavicle"),
    (8, 9, "r_clavicle_to_shoulder"),
    (9, 10, "r_shoulder_to_elbow"),
    (10, 11, "r_elbow_to_wrist"),
]

# ============================================================================
# 4. BODY_25 to Kinect mapping
# ============================================================================

# Mapping from BODY_25 OpenPose ID to Kinect joint index
# -1 means unavailable in Kinect
BODY25_TO_KINECT: Dict[int, int] = {
    0:  21,  # Nose          -> NOSE
    1:  3,   # Neck          -> NECK
    2:  9,   # RShoulder     -> SHOULDER_RIGHT
    3:  10,  # RElbow        -> ELBOW_RIGHT
    4:  11,  # RWrist        -> WRIST_RIGHT
    5:  5,   # LShoulder     -> SHOULDER_LEFT
    6:  6,   # LElbow        -> ELBOW_LEFT
    7:  7,   # LWrist        -> WRIST_LEFT
    8:  0,   # MidHip        -> PELVIS (approximate)
    9:  16,  # RHip          -> HIP_RIGHT
    10: 17,  # RKnee         -> KNEE_RIGHT
    11: 18,  # RAnkle        -> ANKLE_RIGHT
    12: 12,  # LHip          -> HIP_LEFT
    13: 13,  # LKnee         -> KNEE_LEFT
    14: 14,  # LAnkle        -> ANKLE_LEFT
    15: 24,  # REye          -> EYE_RIGHT
    16: 22,  # LEye          -> EYE_LEFT
    17: 25,  # REar          -> EAR_RIGHT
    18: 23,  # LEar          -> EAR_LEFT
    19: 15,  # LBigToe       -> FOOT_LEFT (approximate)
    20: -1,  # LSmallToe     -> UNAVAILABLE
    21: -1,  # LHeel         -> UNAVAILABLE
    22: 19,  # RBigToe       -> FOOT_RIGHT (approximate)
    23: -1,  # RSmallToe     -> UNAVAILABLE
    24: -1,  # RHeel         -> UNAVAILABLE
}

# Reverse mapping: Kinect index -> BODY_25 OpenPose ID
KINECT_TO_BODY25: Dict[int, int] = {v: k for k, v in BODY25_TO_KINECT.items() if v >= 0}

# BODY_25 joint names (OpenPose convention)
BODY25_JOINT_NAMES: List[str] = [
    "Nose", "Neck", "RShoulder", "RElbow", "RWrist",
    "LShoulder", "LElbow", "LWrist", "MidHip",
    "RHip", "RKnee", "RAnkle", "LHip", "LKnee", "LAnkle",
    "REye", "LEye", "REar", "LEar",
    "LBigToe", "LSmallToe", "LHeel", "RBigToe", "RSmallToe", "RHeel",
]

# ============================================================================
# 5. Quality classification rules
# ============================================================================

# Bone length stability thresholds
BONE_LENGTH_VARIATION_WARN = 0.10   # 10% coefficient of variation -> warning
BONE_LENGTH_VARIATION_FAIL = 0.30   # 30% coefficient of variation -> fail

# Reference quality depends on:
#   1. Confidence level (HIGH=3, MEDIUM=2, LOW=1, NONE=0)
#   2. Bone length stability (within expected range)
#   3. Observation status (visible, occluded, etc.)

def classify_reference_quality(
    confidence: int,
    bone_length_stable: bool,
    observation_status: str,
) -> str:
    """Classify a joint-frame as high/medium/low/unusable reference quality.

    Args:
        confidence: Kinect SDK confidence level (0-3).
        bone_length_stable: Whether the associated bone length is within
            expected physiological range.
        observation_status: One of 'visible', 'occluded', 'out_of_fov', 'uncertain'.

    Returns:
        One of 'high', 'medium', 'low', 'unusable'.
    """
    if confidence == KinectConfidence.NONE:
        return "unusable"
    if observation_status == "out_of_fov":
        return "unusable"

    if confidence == KinectConfidence.HIGH and bone_length_stable:
        return "high"
    elif confidence >= KinectConfidence.MEDIUM and bone_length_stable:
        return "medium"
    elif confidence >= KinectConfidence.LOW:
        return "low"
    else:
        return "unusable"


def get_invalid_reason(
    confidence: int,
    bone_length_stable: bool,
    observation_status: str,
) -> str:
    """Determine the reason a joint-frame is not reference_valid."""
    if confidence == KinectConfidence.HIGH and bone_length_stable and observation_status == "visible":
        return "none"
    if observation_status == "out_of_fov":
        return "fov_edge"
    if observation_status == "occluded":
        return "occlusion"
    if confidence <= KinectConfidence.NONE:
        return "tracking_failure"
    if confidence <= KinectConfidence.LOW:
        return "low_confidence"
    if not bone_length_stable:
        return "bone_length_anomaly"
    return "none"
