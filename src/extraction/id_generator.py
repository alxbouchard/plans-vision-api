"""Deterministic ID generation for extracted objects.

Per PHASE2_DECISIONS.md:
- Object IDs must be deterministic for the same page content
- Use stable hashing of page_id plus normalized label and geometry buckets
"""

from __future__ import annotations

import hashlib
from uuid import UUID
from typing import Optional, Tuple

from src.models.entities import ObjectType


def normalize_label(label: str) -> str:
    """Normalize a label for stable hashing.

    - Lowercase
    - Strip whitespace
    - Remove special characters
    """
    if not label:
        return ""
    normalized = label.lower().strip()
    # Keep only alphanumeric and spaces
    normalized = "".join(c if c.isalnum() or c.isspace() else "" for c in normalized)
    # Collapse multiple spaces
    normalized = " ".join(normalized.split())
    return normalized


def bucket_coordinate(value: int, bucket_size: int = 50) -> int:
    """Round a coordinate to nearest bucket for stability.

    Small pixel differences shouldn't create different IDs.
    """
    return (value // bucket_size) * bucket_size


def bucket_bbox(bbox: Tuple[int, int, int, int], bucket_size: int = 50) -> Tuple[int, int, int, int]:
    """Bucket all bbox coordinates for stability."""
    return (
        bucket_coordinate(bbox[0], bucket_size),
        bucket_coordinate(bbox[1], bucket_size),
        bucket_coordinate(bbox[2], bucket_size),
        bucket_coordinate(bbox[3], bucket_size),
    )


def generate_object_id(
    page_id: UUID,
    object_type: ObjectType,
    label: str,
    bbox: Tuple[int, int, int, int],
    qualifier: Optional[str] = None,
) -> str:
    """Generate a deterministic ID for an extracted object.

    Args:
        page_id: The page ID where the object was found
        object_type: Type of object (room, door, etc.)
        label: The extracted label/text for the object
        bbox: Bounding box as (x1, y1, x2, y2)
        qualifier: Optional additional qualifier (e.g., room number)

    Returns:
        Deterministic string ID like "room_abc123" or "door_def456"
    """
    # Normalize inputs
    normalized_label = normalize_label(label)
    bucketed_bbox = bucket_bbox(bbox)

    # Build hash input
    hash_parts = [
        str(page_id),
        object_type.value,
        normalized_label,
        str(bucketed_bbox),
    ]
    if qualifier:
        hash_parts.append(qualifier)

    hash_input = "|".join(hash_parts)

    # Generate hash
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    # Use first 8 bytes for compact ID (16 hex chars)
    hash_hex = hash_bytes[:8].hex()

    # Return typed ID
    return f"{object_type.value}_{hash_hex}"


def generate_room_id(
    page_id: UUID,
    label: str,
    bbox: Tuple[int, int, int, int],
    room_number: Optional[str] = None,
) -> str:
    """Generate a deterministic ID for a room."""
    return generate_object_id(
        page_id=page_id,
        object_type=ObjectType.ROOM,
        label=label,
        bbox=bbox,
        qualifier=room_number,
    )


def generate_door_id(
    page_id: UUID,
    label: str,
    bbox: Tuple[int, int, int, int],
    door_number: Optional[str] = None,
) -> str:
    """Generate a deterministic ID for a door."""
    return generate_object_id(
        page_id=page_id,
        object_type=ObjectType.DOOR,
        label=label,
        bbox=bbox,
        qualifier=door_number,
    )
