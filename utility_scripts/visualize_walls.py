import cv2
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

# Load the minimap image
original_image = cv2.imread("images/SRminimap4x.png")
mask = cv2.imread("images/SRminimap4x.png", cv2.IMREAD_GRAYSCALE)

# Detect walls (black areas)
_, mask1 = cv2.threshold(mask, 30, 255, cv2.THRESH_BINARY_INV)
_, mask2 = cv2.threshold(mask, 60, 255, cv2.THRESH_BINARY_INV)
wall_mask = cv2.bitwise_or(mask1, mask2)

# Find contours
contours, _ = cv2.findContours(wall_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Create polygons
polygons = []
for cnt in contours:
    coords = [(pt[0][0], pt[0][1]) for pt in cnt]
    if len(coords) >= 3:
        poly = Polygon(coords).buffer(0)
        poly = poly.buffer(.5)
        if poly.is_valid and not poly.is_empty:
            polygons.append(poly)

walls = unary_union(polygons)

# Draw walls on a copy of the original image using OpenCV
visualization = original_image.copy()

# Draw walls as overlays
if walls.geom_type == "Polygon":
    polygons_to_draw = [walls]
elif walls.geom_type == "MultiPolygon":
    polygons_to_draw = list(walls.geoms)
else:
    polygons_to_draw = []

for poly in polygons_to_draw:
    coords = np.array(list(poly.exterior.coords), dtype=np.int32)
    # Draw filled polygon with semi-transparent red (using blending)
    overlay = visualization.copy()
    cv2.fillPoly(overlay, [coords], (0, 0, 255))  # Red in BGR
    cv2.addWeighted(overlay, 0.3, visualization, 0.7, 0, visualization)
    # Draw outline
    cv2.polylines(visualization, [coords], True, (0, 0, 255), 2)

# Save the visualization
cv2.imwrite("wall_overlay_visualization.png", visualization)
print("✓ Wall overlay visualization saved as 'wall_overlay_visualization.png'")
print(f"✓ Detected {len(polygons_to_draw)} wall regions")
print(f"✓ Image size: {visualization.shape}")

# Also display using OpenCV
cv2.imshow("Wall Overlay", visualization)
print("✓ Displaying visualization (press any key to close)...")
cv2.waitKey(0)
cv2.destroyAllWindows()
