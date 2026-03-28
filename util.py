
import math


def check_collision(rect, rect_list):
    for other_rect in rect_list:
        if rect.colliderect(other_rect):
            return True
    return False

def get_collision(rect, rect_list):
    for other_rect in rect_list:
        if rect.colliderect(other_rect):
            return other_rect
    return None


def point_in_polygon(px, py, polygon):
    """Ray-casting algorithm to check if a point is inside a polygon.
    polygon is a list of (x, y) tuples."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Return the shortest distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

