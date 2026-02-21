"""
PIL-based image annotation with bounding boxes, labels, and legends.

GCP Document AI provides normalized vertices (0.0-1.0).
Conversion: pixel = normalized_vertex * image_dimension
"""

from typing import Dict, List, Any, Tuple
from PIL import Image, ImageDraw, ImageFont


class SimpleDocumentAnnotator:
    """Creates image-based annotations with overlaid bounding boxes."""

    def __init__(self):
        self.element_styles = {
            "text": {"color": "#007ACC", "width": 2},
            "tables": {"color": "#00B04F", "width": 3},
            "paragraphs": {"color": "#9932CC", "width": 2},
            "form_fields": {"color": "#FF8C00", "width": 2},
            "entities": {"color": "#DC143C", "width": 2},
            "checkboxes": {"color": "#8A2BE2", "width": 2},
        }

    def annotate_image(
        self,
        image: Image.Image,
        bounding_boxes: Dict[str, List[Dict]],
        page_idx: int,
        show_labels: bool = True,
    ) -> Image.Image:
        """
        Create annotated image with bounding boxes drawn directly on it.

        For GCP, vertices are normalized (0-1), so we multiply by image dimensions.
        No separate scale_x/scale_y needed — the vertices already encode position.

        Args:
            image: PIL Image to annotate
            bounding_boxes: Dict of bounding box data by element type
            page_idx: Current page index (0-based)
            show_labels: Whether to show text labels

        Returns:
            Annotated PIL Image copy
        """
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)

        font, small_font = self._load_fonts()

        page_boxes = self._filter_boxes_for_page(bounding_boxes, page_idx)

        # Draw order: background elements first, details last
        draw_order = [
            "paragraphs", "tables", "form_fields", "entities", "checkboxes", "text",
        ]

        for box_type in draw_order:
            boxes = page_boxes.get(box_type, [])
            if not boxes:
                continue
            style = self.element_styles.get(box_type, {"color": "#FF0000", "width": 2})
            for box in boxes:
                self._draw_single_box(
                    draw, box, box_type, style,
                    image.width, image.height,
                    font, small_font, show_labels,
                )

        return annotated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_fonts():
        """Load fonts with graceful fallback."""
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 14)
            small_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 12)
        except OSError:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            except OSError:
                font = ImageFont.load_default()
                small_font = font
        return font, small_font

    @staticmethod
    def _filter_boxes_for_page(
        bounding_boxes: Dict[str, List], page_idx: int
    ) -> Dict[str, List]:
        """Filter bounding boxes for a specific page."""
        return {
            box_type: [b for b in boxes if b.get("page", 0) == page_idx]
            for box_type, boxes in bounding_boxes.items()
        }

    def _draw_single_box(
        self,
        draw: ImageDraw.Draw,
        box: Dict,
        box_type: str,
        style: Dict,
        img_width: int,
        img_height: int,
        font,
        small_font,
        show_labels: bool,
    ):
        """Draw a single bounding box using normalized vertices."""
        vertices = box.get("vertices", [])
        if len(vertices) < 3:
            return

        # Convert normalized vertices to pixel coordinates
        points = []
        for v in vertices:
            x = max(0, min(int(v["x"] * img_width), img_width))
            y = max(0, min(int(v["y"] * img_height), img_height))
            points.append((x, y))

        color = style["color"]
        width = style["width"]

        # Semi-transparent fill for larger regions
        if box_type in ("tables", "entities"):
            rgb = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
            fill_color = rgb + (30,)
            draw.polygon(points, fill=fill_color, outline=color, width=width)
        else:
            draw.polygon(points, outline=color, width=width)

        if show_labels and points:
            self._add_label(draw, box, box_type, points[0], color, small_font)

    @staticmethod
    def _add_label(draw, box, box_type, position, color, font):
        """Add a text label above the bounding box."""
        x, y = position

        if box_type == "text":
            content = box.get("content", "").strip()
            label = (content[:27] + "...") if len(content) > 30 else content
        elif box_type == "tables":
            details = box.get("details", {})
            label = f"Table {details.get('rowCount', 0)}x{details.get('columnCount', 0)}"
        elif box_type == "paragraphs":
            label = "Paragraph"
        elif box_type == "form_fields":
            details = box.get("details", {})
            role = details.get("role", "").title()
            label = f"KV {role}" if role else "Form Field"
        elif box_type == "entities":
            details = box.get("details", {})
            label = details.get("entityType", "Entity")
        elif box_type == "checkboxes":
            details = box.get("details", {})
            state = details.get("state", "unknown")
            label = f"CB: {state}"
        else:
            label = box_type.title()

        if not label:
            return

        label_y = max(0, y - 20)

        bbox = draw.textbbox((x, label_y), label, font=font)
        pad = 2
        bg_rect = [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad]
        draw.rectangle(bg_rect, fill="white", outline=color, width=1)
        draw.text((x, label_y), label, fill=color, font=font)

        confidence = box.get("confidence", 1.0)
        if confidence < 1.0:
            conf_text = f"{confidence:.0%}"
            draw.text((x, label_y + 15), conf_text, fill=color, font=font)

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------

    def create_legend_html(self) -> str:
        """Create HTML legend showing annotation types and colors."""
        type_names = {
            "text": "Text Lines",
            "tables": "Tables",
            "paragraphs": "Paragraphs",
            "form_fields": "Form Fields (KVPs)",
            "entities": "Entities",
            "checkboxes": "Checkboxes",
        }

        items = []
        for box_type, style in self.element_styles.items():
            name = type_names.get(box_type, box_type)
            items.append(f"""
                <div style="display: flex; align-items: center; margin-bottom: 6px;">
                    <div style="width: 24px; height: 14px; background-color: {style['color']};
                                margin-right: 10px; border: 1px solid #ccc; border-radius: 2px; opacity: 0.7;"></div>
                    <span style="font-size: 14px; color: #333;">{name}</span>
                </div>
            """)

        return f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6; margin: 10px 0;">
            <div style="font-weight: bold; margin-bottom: 10px; color: #495057; font-size: 15px;">
                Document Annotations
            </div>
            {''.join(items)}
            <div style="font-size: 12px; color: #6c757d; margin-top: 10px; font-style: italic;">
                Bounding boxes show detected document elements with labels
            </div>
        </div>
        """
