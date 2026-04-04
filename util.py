
import math
import heapq
import hashlib
import json
import os
from collections import deque


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


class PathGrid:
    """Pre-computed walkability grid with A* pathfinding for navigating around walls."""

    def __init__(self, world_w, world_h, wall_polygons, wall_bounds, pathing_radius, cell_size=100):
        self.cell_size = cell_size
        self.cols = world_w // cell_size + 1
        self.rows = world_h // cell_size + 1
        self.walkable = self._load_or_build(world_w, world_h, wall_polygons, wall_bounds, pathing_radius)

    def _grid_hash(self, world_w, world_h, wall_polygons, pathing_radius):
        """Compute a hash of the inputs that affect the grid."""
        h = hashlib.md5()
        h.update(f"{world_w},{world_h},{self.cell_size},{pathing_radius}".encode())
        for poly in wall_polygons:
            for x, y in poly:
                h.update(f"{x:.2f},{y:.2f}".encode())
        return h.hexdigest()

    def _load_or_build(self, world_w, world_h, wall_polygons, wall_bounds, pathing_radius):
        """Load cached grid from disk or build and cache it."""
        cache_file = "pathgrid_cache.json"
        grid_hash = self._grid_hash(world_w, world_h, wall_polygons, pathing_radius)

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                if data.get("hash") == grid_hash:
                    return data["grid"]
            except (json.JSONDecodeError, KeyError):
                pass

        grid = self._compute_walkability(wall_polygons, wall_bounds, pathing_radius)
        try:
            with open(cache_file, "w") as f:
                json.dump({"hash": grid_hash, "grid": grid}, f)
        except OSError:
            pass
        return grid

    def _compute_walkability(self, wall_polygons, wall_bounds, radius):
        """Build a 2D grid. True = walkable, False = blocked by a wall.
        Iterates walls first, then only the cells near each wall."""
        grid = [[True] * self.cols for _ in range(self.rows)]
        cs = self.cell_size
        half = cs // 2
        margin = radius + half  # cells whose center could be within radius of the wall bbox

        for i, polygon in enumerate(wall_polygons):
            if wall_bounds and i < len(wall_bounds) and wall_bounds[i]:
                mn_x, mx_x, mn_y, mx_y = wall_bounds[i]
            else:
                xs = [p[0] for p in polygon]
                ys = [p[1] for p in polygon]
                mn_x, mx_x, mn_y, mx_y = min(xs), max(xs), min(ys), max(ys)

            c_min = max(0, int((mn_x - margin) / cs))
            c_max = min(self.cols - 1, int((mx_x + margin) / cs))
            r_min = max(0, int((mn_y - margin) / cs))
            r_max = min(self.rows - 1, int((mx_y + margin) / cs))

            # Pre-extract edges for this polygon
            n = len(polygon)
            edges = []
            for j in range(n):
                x1, y1 = polygon[j]
                x2, y2 = polygon[(j + 1) % n]
                edges.append((x1, y1, x2, y2))

            for r in range(r_min, r_max + 1):
                cy = r * cs + half
                for c in range(c_min, c_max + 1):
                    if not grid[r][c]:
                        continue  # Already blocked
                    cx = c * cs + half
                    if point_in_polygon(cx, cy, polygon):
                        grid[r][c] = False
                        continue
                    for x1, y1, x2, y2 in edges:
                        if point_to_segment_distance(cx, cy, x1, y1, x2, y2) < radius:
                            grid[r][c] = False
                            break
        return grid

    def _nearest_walkable(self, c, r):
        """BFS to find the nearest walkable cell."""
        if 0 <= r < self.rows and 0 <= c < self.cols and self.walkable[r][c]:
            return c, r
        queue = deque([(c, r)])
        visited = {(c, r)}
        while queue:
            cc, cr = queue.popleft()
            if 0 <= cr < self.rows and 0 <= cc < self.cols and self.walkable[cr][cc]:
                return cc, cr
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nc, nr = cc + dc, cr + dr
                if 0 <= nc < self.cols and 0 <= nr < self.rows and (nc, nr) not in visited:
                    visited.add((nc, nr))
                    queue.append((nc, nr))
        return c, r

    def snap_to_walkable(self, world_x, world_y):
        """If (world_x, world_y) is inside a wall, return the nearest walkable world position.
        Otherwise return the original position unchanged."""
        cs = self.cell_size
        c = max(0, min(int(world_x / cs), self.cols - 1))
        r = max(0, min(int(world_y / cs), self.rows - 1))
        if self.walkable[r][c]:
            return world_x, world_y
        nc, nr = self._nearest_walkable(c, r)
        return nc * cs + cs // 2, nr * cs + cs // 2

    def find_path(self, start_x, start_y, goal_x, goal_y):
        """A* from world (start_x, start_y) to (goal_x, goal_y).

        Returns a list of (x, y) world-coordinate waypoints leading to the goal.
        Always includes the exact goal position as the final waypoint.
        """
        cs = self.cell_size
        sc = max(0, min(int(start_x / cs), self.cols - 1))
        sr = max(0, min(int(start_y / cs), self.rows - 1))
        gc = max(0, min(int(goal_x / cs), self.cols - 1))
        gr = max(0, min(int(goal_y / cs), self.rows - 1))

        if not self.walkable[sr][sc]:
            sc, sr = self._nearest_walkable(sc, sr)
        if not self.walkable[gr][gc]:
            gc, gr = self._nearest_walkable(gc, gr)

        if sc == gc and sr == gr:
            return [(goal_x, goal_y)]

        SQRT2 = 1.4142135
        NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                     (0, 1), (1, -1), (1, 0), (1, 1)]

        open_set = [(0.0, sc, sr)]
        came_from = {}
        g_score = {(sc, sr): 0.0}
        closed = set()

        while open_set:
            _, cx, cy = heapq.heappop(open_set)

            if cx == gc and cy == gr:
                # Reconstruct path
                path = []
                node = (gc, gr)
                while node in came_from:
                    c, r = node
                    path.append((c * cs + cs // 2, r * cs + cs // 2))
                    node = came_from[node]
                path.reverse()
                path.append((goal_x, goal_y))
                return self._smooth_path(path)

            if (cx, cy) in closed:
                continue
            closed.add((cx, cy))

            for dc, dr in NEIGHBORS:
                nc, nr = cx + dc, cy + dr
                if not (0 <= nc < self.cols and 0 <= nr < self.rows):
                    continue
                if not self.walkable[nr][nc]:
                    continue
                if (nc, nr) in closed:
                    continue
                # Prevent corner-cutting through diagonal walls
                if dc != 0 and dr != 0:
                    if not self.walkable[cy][cx + dc] or not self.walkable[cy + dr][cx]:
                        continue
                cost = SQRT2 if (dc != 0 and dr != 0) else 1.0
                ng = g_score[(cx, cy)] + cost
                if ng < g_score.get((nc, nr), float('inf')):
                    g_score[(nc, nr)] = ng
                    dx_h = abs(nc - gc)
                    dy_h = abs(nr - gr)
                    h = max(dx_h, dy_h) + (SQRT2 - 1) * min(dx_h, dy_h)
                    heapq.heappush(open_set, (ng + h, nc, nr))
                    came_from[(nc, nr)] = (cx, cy)

        # No path found — fall back to straight line
        return [(goal_x, goal_y)]

    def _smooth_path(self, path):
        """Remove unnecessary intermediate waypoints via line-of-sight checks."""
        if len(path) <= 2:
            return path
        smoothed = [path[0]]
        i = 0
        while i < len(path) - 1:
            farthest = i + 1
            for j in range(i + 2, len(path)):
                if self._line_walkable(path[i], path[j]):
                    farthest = j
            smoothed.append(path[farthest])
            i = farthest
        return smoothed

    def _line_walkable(self, p1, p2):
        """Check if the straight line between two points passes only through walkable cells."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.sqrt(dx * dx + dy * dy)
        steps = max(int(dist / (self.cell_size * 0.5)), 1)
        cs = self.cell_size
        for i in range(steps + 1):
            t = i / steps
            x = p1[0] + dx * t
            y = p1[1] + dy * t
            c = max(0, min(int(x / cs), self.cols - 1))
            r = max(0, min(int(y / cs), self.rows - 1))
            if not self.walkable[r][c]:
                return False
        return True

