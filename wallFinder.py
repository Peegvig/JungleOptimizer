import cv2
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.geometry import Point
import json
#MAPSIZE = 14800 #how many units tall/wide SR is, not sure

# Load your wall mask (black = wall, white = floor)
mask = cv2.imread("images/SRminimap4x.png", cv2.IMREAD_GRAYSCALE)

# Only very dark pixels = walls
_, mask1 = cv2.threshold(mask, 30, 255, cv2.THRESH_BINARY_INV)
_, mask2 = cv2.threshold(mask, 60, 255, cv2.THRESH_BINARY_INV)
wall_mask = cv2.bitwise_or(mask1, mask2)


# Find contours with OpenCV
contours, _ = cv2.findContours(wall_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

polygons = []
for cnt in contours:
    coords = [(pt[0][0], pt[0][1]) for pt in cnt]
    if len(coords) >= 3:
        poly = Polygon(coords).buffer(0)  # clean invalid polygons
        poly = poly.buffer(.5) 
        if poly.is_valid and not poly.is_empty:
            polygons.append(poly)

walls = unary_union(polygons)

#scale_x = MAPSIZE / wall_mask.shape[1]
#scale_y = MAPSIZE / wall_mask.shape[0]

# def scale_polygon(polygon):
#     return Polygon([(x*scale_x, y*scale_y) for x, y in polygon.exterior.coords])

# if walls.geom_type == "Polygon":
#     walls = scale_polygon(walls)
# elif walls.geom_type == "MultiPolygon":
#     walls = MultiPolygon([scale_polygon(p) for p in walls.geoms])



def export_walls_json(walls, filename="walls.json"):
    data = []
    if walls.geom_type == "Polygon":
        data.append(list(walls.exterior.coords))
    elif walls.geom_type == "MultiPolygon":
        for poly in walls.geoms:
            data.append(list(poly.exterior.coords))
    with open(filename, "w") as f:
        json.dump(data, f)

export_walls_json(walls)
print("Walls exported to walls.json")
