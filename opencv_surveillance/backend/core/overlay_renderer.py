# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Overlay Renderer Module
Handles rendering of timestamp and custom text overlays on video frames
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Tuple


# Color mappings (BGR format for OpenCV)
OVERLAY_COLORS = {
    'white': (255, 255, 255),
    'yellow': (0, 255, 255),
    'cyan': (255, 255, 0),
    'green': (0, 255, 0),
    'red': (0, 0, 255),
    'black': (0, 0, 0),
}


def get_text_size(text: str, font_scale: int, thickness: int = 2) -> Tuple[int, int]:
    """
    Get the size of text for positioning

    Args:
        text: Text to measure
        font_scale: Font scale (1-3)
        thickness: Font thickness

    Returns:
        Tuple of (width, height)
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )
    return text_width, text_height + baseline


def calculate_position(
    frame_shape: Tuple[int, int],
    text_size: Tuple[int, int],
    position: str,
    padding: int = 10
) -> Tuple[int, int]:
    """
    Calculate text position based on frame size and desired position

    Args:
        frame_shape: (height, width) of the frame
        text_size: (width, height) of the text
        position: Position string (top-left, top-right, bottom-left, bottom-right, center-top, center-bottom)
        padding: Padding from edges in pixels

    Returns:
        Tuple of (x, y) coordinates for text bottom-left corner
    """
    frame_height, frame_width = frame_shape[:2]
    text_width, text_height = text_size

    # Calculate base positions
    positions = {
        'top-left': (padding, padding + text_height),
        'top-right': (frame_width - text_width - padding, padding + text_height),
        'bottom-left': (padding, frame_height - padding),
        'bottom-right': (frame_width - text_width - padding, frame_height - padding),
        'center-top': ((frame_width - text_width) // 2, padding + text_height),
        'center-bottom': ((frame_width - text_width) // 2, frame_height - padding),
    }

    return positions.get(position, positions['top-left'])


def draw_text_with_background(
    frame: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: int,
    color: Tuple[int, int, int],
    thickness: int = 2,
    background_color: Tuple[int, int, int] = (0, 0, 0),
    background_alpha: float = 0.6
) -> np.ndarray:
    """
    Draw text with a semi-transparent background for better readability

    Args:
        frame: Input frame (will be modified)
        text: Text to draw
        position: (x, y) coordinates for text bottom-left corner
        font_scale: Font scale (1-3)
        color: Text color (BGR)
        thickness: Font thickness
        background_color: Background color (BGR)
        background_alpha: Background transparency (0-1)

    Returns:
        Modified frame
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    x, y = position

    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )

    # Calculate background rectangle coordinates
    padding = 5
    rect_x1 = x - padding
    rect_y1 = y - text_height - padding
    rect_x2 = x + text_width + padding
    rect_y2 = y + baseline + padding

    # Create overlay for semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), background_color, -1)

    # Blend overlay with original frame
    cv2.addWeighted(overlay, background_alpha, frame, 1 - background_alpha, 0, frame)

    # Draw text on top
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)

    return frame


def render_overlay(
    frame: np.ndarray,
    overlay_enabled: bool = True,
    timestamp_enabled: bool = True,
    custom_text: Optional[str] = None,
    position: str = 'top-left',
    font_size: int = 1,
    font_color: str = 'white'
) -> np.ndarray:
    """
    Render timestamp and/or custom text overlay on a frame

    Args:
        frame: Input video frame
        overlay_enabled: Master enable/disable for all overlays
        timestamp_enabled: Enable timestamp display
        custom_text: Custom text message (optional)
        position: Position for overlay (top-left, top-right, bottom-left, bottom-right, center-top, center-bottom)
        font_size: Font scale (1-3)
        font_color: Color name (white, yellow, cyan, green, red)

    Returns:
        Frame with overlay applied
    """
    if not overlay_enabled:
        return frame

    # Skip if neither timestamp nor custom text is enabled
    if not timestamp_enabled and not custom_text:
        return frame

    # Get color from mapping
    color = OVERLAY_COLORS.get(font_color, OVERLAY_COLORS['white'])

    # Font settings
    font_scale = font_size * 0.7  # Scale down for better readability
    thickness = max(1, font_size)

    # Build overlay text lines
    lines = []

    if timestamp_enabled:
        # Format: "2025-01-31 14:30:45"
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(timestamp_str)

    if custom_text:
        lines.append(custom_text)

    # Calculate positions for each line
    frame_shape = frame.shape
    line_spacing = 10

    for i, line in enumerate(lines):
        # Get text size for this line
        text_size = get_text_size(line, font_scale, thickness)

        # Calculate position based on desired placement
        base_x, base_y = calculate_position(frame_shape, text_size, position)

        # Adjust y position for multiple lines
        if position.startswith('bottom'):
            # Stack upwards from bottom
            y_offset = -(i * (text_size[1] + line_spacing))
        else:
            # Stack downwards from top
            y_offset = i * (text_size[1] + line_spacing)

        text_position = (base_x, base_y + y_offset)

        # Draw text with background
        draw_text_with_background(
            frame,
            line,
            text_position,
            font_scale,
            color,
            thickness,
            background_color=(0, 0, 0),
            background_alpha=0.6
        )

    return frame
