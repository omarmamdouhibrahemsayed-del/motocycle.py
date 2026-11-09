
import math
import random
import sys
import pygame

pygame.init()
pygame.display.set_caption("Desert Rider")
WIDTH, HEIGHT = 1100, 650
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("arial", 22, bold=True)
SMALL = pygame.font.SysFont("arial", 16, bold=True)
BIG = pygame.font.SysFont("arial", 56, bold=True)

SKY = (112, 196, 235)
SAND = (224, 178, 104)
DARK = (34, 38, 47)
WHITE = (248, 248, 240)
ORANGE = (246, 112, 35)
CYAN = (45, 210, 205)


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_text(surface, text, font, color, pos, center=False):
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(image, rect)


class Bike:
    """Player bike: a small rigid body represented by a center, angle and wheels."""

    STYLES = [
        {"name": "STANDARD ORANGE", "frame": ORANGE, "trim": (255, 225, 180),
         "rider": (40, 42, 48), "wheel": (25, 27, 31)},
        {"name": "NINJA SHADOW", "frame": (48, 52, 67), "trim": CYAN,
         "rider": (20, 23, 33), "wheel": (10, 12, 18)},
    ]

    def __init__(self, x, y, style=0):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = 0.0, 0.0
        self.angle = 0.0
        self.angular_velocity = 0.0
        self.style = style
        self.wheel_radius = 15
        self.crashed = False
        self.grounded = False
        self.flip_rotation = 0.0

    def wheel_positions(self):
        # Local wheel positions along the bike frame, rotated into world space.
        c, s = math.cos(self.angle), math.sin(self.angle)
        points = []
        for lx in (-31, 31):
            points.append((self.x + lx * c, self.y + lx * s + 8))
        return points

    def jump(self):
        """Jump only when the bike is touching the ground."""
        if self.grounded and not self.crashed:
            self.vy = -520
            self.grounded = False
            return True
        return False

    def update(self, dt, keys, level):
        if self.crashed:
            return

        accelerating = keys[pygame.K_UP] or keys[pygame.K_w]
        braking = keys[pygame.K_DOWN] or keys[pygame.K_s]
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if accelerating:
            self.vx += 520 * dt
        if braking:
            self.vx -= 650 * dt
        self.vx = clamp(self.vx, -180, 560)

        # Air control. On the ground, the suspension/terrain keeps the bike stable.
        self.grounded = False
        if not level.is_near_ground(self.x, self.y + 22):
            if left:
                self.angular_velocity -= 4.0 * dt
            if right:
                self.angular_velocity += 4.0 * dt
        else:
            self.angular_velocity *= 0.82

        self.angular_velocity = clamp(self.angular_velocity, -4.5, 4.5)
        self.angle += self.angular_velocity
        self.angle = (self.angle + math.pi) % (2 * math.pi) - math.pi

        self.vy += 1050 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        # Apply simple terrain collision to both wheels.
        for wx, wy in self.wheel_positions():
            ground = level.ground_height(wx)
            if wy + self.wheel_radius > ground and self.vy >= 0:
                self.y -= (wy + self.wheel_radius - ground) * 0.55
                self.vy = min(self.vy, 0)
                self.grounded = True
                # Align gradually with the ground; avoid snapping during jumps.
                slope = level.ground_slope(self.x)
                target_angle = math.atan(slope)
                self.angle += (target_angle - self.angle) * min(1, 8 * dt)
                self.angular_velocity *= 0.55

        # Fall protection.
        if self.y > HEIGHT + 500:
            self.crashed = True

    def draw(self, surface, camera_x):
        style = self.STYLES[self.style]
        x, y = self.x - camera_x, self.y
        c, s = math.cos(self.angle), math.sin(self.angle)

        def point(lx, ly):
            return (int(x + lx * c - ly * s), int(y + lx * s + ly * c))

        rear, front = point(-31, 8), point(31, 8)
        # Wheels
        for wx, wy in (rear, front):
            pygame.draw.circle(surface, style["wheel"], (wx, wy), 16)
            pygame.draw.circle(surface, (175, 180, 180), (wx, wy), 10, 3)
            pygame.draw.circle(surface, WHITE, (wx, wy), 3)
        # Frame, fork, seat and engine
        pygame.draw.line(surface, style["frame"], rear, point(-5, -9), 7)
        pygame.draw.line(surface, style["frame"], point(-5, -9), front, 7)
        pygame.draw.line(surface, style["trim"], point(-5, -9), point(13, -14), 4)
        pygame.draw.line(surface, style["frame"], point(13, -14), front, 5)
        pygame.draw.line(surface, style["trim"], point(-20, -14), point(-2, -14), 5)
        pygame.draw.circle(surface, (65, 70, 78), point(0, 0), 8)
        # Rider body and helmet
        pygame.draw.line(surface, style["rider"], point(-3, -12), point(5, -31), 9)
        pygame.draw.line(surface, style["rider"], point(5, -28), point(20, -17), 7)
        pygame.draw.circle(surface, style["trim"], point(7, -39), 9)
        pygame.draw.line(surface, style["rider"], point(-2, -12), point(-17, -1), 6)


class Obstacle:
    def __init__(self, kind, x, y, width=42, height=42, phase=0):
        self.kind, self.x, self.y = kind, x, y
        self.width, self.height = width, height
        self.phase = phase
        self.rotation = 0.0
        self.exploded = False
        self.explosion_time = 0.0

    def update(self, dt, elapsed):
        self.rotation += dt * 7
        if self.kind == "saw":
            self.y = self.base_y + math.sin(elapsed * 2.2 + self.phase) * 45
        if self.exploded:
            self.explosion_time += dt

    def collides(self, bike):
        if self.kind == "saw":
            ox, oy = self.x, self.y
            return math.hypot(bike.x - ox, bike.y - oy) < 31
        if self.kind == "spikes":
            rect = pygame.Rect(self.x - self.width / 2, self.y - self.height,
                               self.width, self.height)
            return rect.collidepoint(int(bike.x), int(bike.y + 8))
        if self.kind == "tnt" and not self.exploded:
            rect = pygame.Rect(self.x - self.width / 2, self.y - self.height,
                               self.width, self.height)
            return rect.colliderect(pygame.Rect(bike.x - 22, bike.y - 25, 44, 45))
        return False

    def draw(self, surface, camera_x):
        x = int(self.x - camera_x)
        y = int(self.y)
        if x < -100 or x > WIDTH + 100:
            return
        if self.kind == "saw":
            pygame.draw.circle(surface, (65, 68, 72), (x, y), 24)
            for i in range(12):
                a = self.rotation + i * math.tau / 12
                p1 = (x + math.cos(a) * 17, y + math.sin(a) * 17)
                p2 = (x + math.cos(a) * 31, y + math.sin(a) * 31)
                pygame.draw.line(surface, (210, 215, 220), p1, p2, 5)
            pygame.draw.circle(surface, (190, 195, 200), (x, y), 8)
        elif self.kind == "spikes":
            for i in range(4):
                px = x - self.width // 2 + i * 12
                pygame.draw.polygon(surface, (65, 66, 68),
                                    [(px, y), (px + 6, y - self.height), (px + 12, y)])
        elif self.kind == "tnt":
            if self.exploded:
                radius = int(18 + self.explosion_time * 130)
                if self.explosion_time < 0.38:
                    pygame.draw.circle(surface, (255, 180, 45), (x, y - 18), radius, 5)
                    pygame.draw.circle(surface, (255, 75, 25), (x, y - 18), max(4, radius // 2))
            else:
                rect = pygame.Rect(x - 21, y - 40, 42, 40)
                pygame.draw.rect(surface, (190, 48, 32), rect, border_radius=5)
                pygame.draw.rect(surface, (245, 210, 150), rect, 3, border_radius=5)
                draw_text(surface, "TNT", SMALL, WHITE, (x, y - 20), True)


class Level:
    """World geometry and level objects."""

    LENGTH = 5200

    def __init__(self):
        self.obstacles = []
        self.checkpoints = [900, 2350, 3850]
        self.finish_x = 4950
        self._build()

    def _build(self):
        specs = [
            ("spikes", 620), ("saw", 1120), ("tnt", 1510),
            ("spikes", 1830), ("saw", 2150), ("tnt", 2780),
            ("spikes", 3100), ("saw", 3440), ("tnt", 4140),
            ("spikes", 4510)
        ]
        for i, (kind, x) in enumerate(specs):
            y = self.ground_height(x)
            obj = Obstacle(kind, x, y, phase=i * 1.7)
            if kind == "saw":
                obj.base_y = y - 65
            self.obstacles.append(obj)

    def ground_height(self, x):
        # Smooth rolling terrain plus a few ramps and a shallow loop-shaped hill.
        return 520 + 32 * math.sin(x / 210) + 18 * math.sin(x / 73)

    def ground_slope(self, x):
        eps = 3
        return (self.ground_height(x + eps) - self.ground_height(x - eps)) / (2 * eps)

    def is_near_ground(self, x, y):
        return y > self.ground_height(x) - 55

    def update(self, dt, elapsed):
        for obj in self.obstacles:
            obj.update(dt, elapsed)

    def draw(self, surface, camera_x, elapsed):
        # Distant dunes
        surface.fill(SKY)
        for layer, color, amp, offset in [
            (0, (238, 205, 145), 45, 0.18),
            (1, (220, 177, 112), 62, 0.32),
        ]:
            points = []
            for sx in range(-40, WIDTH + 60, 20):
                wx = sx + camera_x * offset
                sy = 330 + layer * 55 + math.sin(wx / 180) * amp
                points.append((sx, sy))
            points += [(WIDTH + 60, HEIGHT), (-40, HEIGHT)]
            pygame.draw.polygon(surface, color, points)

        # Clouds drift relative to the camera.
        for i in range(7):
            cx = int((i * 230 - camera_x * 0.12 + elapsed * 13) % (WIDTH + 260) - 100)
            cy = 75 + (i % 3) * 48
            pygame.draw.circle(surface, WHITE, (cx, cy), 19)
            pygame.draw.circle(surface, WHITE, (cx + 22, cy - 7), 24)
            pygame.draw.circle(surface, WHITE, (cx + 47, cy), 18)

        # Palm trees
        for wx in range(-200, self.LENGTH + 300, 520):
            sx = int(wx - camera_x * 0.55)
            if -100 < sx < WIDTH + 100:
                base_y = 455 + math.sin(wx / 170) * 12
                pygame.draw.line(surface, (119, 79, 43), (sx, base_y),
                                 (sx - 12, base_y - 95), 9)
                for j in range(5):
                    a = -2.7 + j * 0.7
                    end = (sx - 12 + math.cos(a) * 52,
                           base_y - 95 + math.sin(a) * 28)
                    pygame.draw.line(surface, (40, 125, 70),
                                     (sx - 12, base_y - 95), end, 8)

        # Ground strip and surface
        pts = []
        for sx in range(-30, WIDTH + 50, 12):
            wx = sx + camera_x
            pts.append((sx, int(self.ground_height(wx))))
        pts += [(WIDTH + 50, HEIGHT), (-30, HEIGHT)]
        pygame.draw.polygon(surface, SAND, pts)
        for sx in range(-30, WIDTH + 50, 28):
            wx = sx + camera_x
            gy = int(self.ground_height(wx))
            pygame.draw.line(surface, (160, 116, 67), (sx, gy + 12), (sx + 9, gy + 18), 2)

        # Ramps
        for wx in (1280, 2500, 3650):
            sx = int(wx - camera_x)
            if -200 < sx < WIDTH + 200:
                gy = int(self.ground_height(wx))
                pygame.draw.polygon(surface, (130, 88, 48),
                                    [(sx - 75, gy), (sx + 35, gy - 105), (sx + 65, gy)])
                pygame.draw.line(surface, (255, 220, 150),
                                 (sx - 75, gy), (sx + 35, gy - 105), 5)

        for cp in self.checkpoints:
            sx = int(cp - camera_x)
            if -30 < sx < WIDTH + 30:
                gy = int(self.ground_height(cp))
                pygame.draw.line(surface, (75, 70, 60), (sx, gy), (sx, gy - 95), 5)
                pygame.draw.polygon(surface, (55, 190, 105),
                                    [(sx, gy - 95), (sx + 42, gy - 82), (sx, gy - 68)])

        fx = int(self.finish_x - camera_x)
        if -60 < fx < WIDTH + 60:
            gy = int(self.ground_height(self.finish_x))
            pygame.draw.line(surface, DARK, (fx, gy), (fx, gy - 130), 7)
            pygame.draw.rect(surface, WHITE, (fx, gy - 130, 70, 42))
            for yy in range(2):
                for xx in range(4):
                    if (xx + yy) % 2 == 0:
                        pygame.draw.rect(surface, DARK, (fx + xx * 17, gy - 130 + yy * 21, 17, 21))

        for obj in self.obstacles:
            obj.draw(surface, camera_x)


class Game:
    def __init__(self):
        self.state = "menu"
        self.selected_style = 0
        self.reset()

    def reset(self):
        self.level = Level()
        self.bike = Bike(110, 440, self.selected_style)
        self.camera_x = 0.0
        self.start_ticks = pygame.time.get_ticks()
        self.elapsed = 0.0
        self.deaths = 0
        self.checkpoint_x = 110
        self.finished_time = None
        self.particles = []

    def crash(self):
        if self.bike.crashed or self.state != "playing":
            return
        self.bike.crashed = True
        self.deaths += 1
        # Small burst of debris particles.
        for _ in range(22):
            self.particles.append([self.bike.x, self.bike.y,
                                   random.uniform(-180, 180), random.uniform(-260, 40), 0.7])

    def respawn(self):
        self.bike = Bike(self.checkpoint_x, self.level.ground_height(self.checkpoint_x) - 45,
                         self.selected_style)
        self.camera_x = max(0, self.checkpoint_x - 250)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        if self.state == "playing":
            self.elapsed = (pygame.time.get_ticks() - self.start_ticks) / 1000
            self.level.update(dt, self.elapsed)
            if not self.bike.crashed:
                self.bike.update(dt, keys, self.level)

                # Checkpoint activation
                for cp in self.level.checkpoints:
                    if self.bike.x >= cp and cp > self.checkpoint_x:
                        self.checkpoint_x = cp

                # Hazards
                for obj in self.level.obstacles:
                    if obj.collides(self.bike):
                        if obj.kind == "tnt":
                            obj.exploded = True
                            obj.explosion_time = 0
                        self.crash()
                        break

                # A bad landing angle crashes the rider.
                if self.bike.grounded and abs(self.bike.angle) > 1.22:
                    self.crash()

                if self.bike.x >= self.level.finish_x:
                    self.state = "finished"
                    self.finished_time = self.elapsed

            self.camera_x += (self.bike.x - 300 - self.camera_x) * min(1, dt * 5)
            self.camera_x = clamp(self.camera_x, 0, self.level.LENGTH - WIDTH + 100)

        for p in self.particles[:]:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 450 * dt
            p[4] -= dt
            if p[4] <= 0:
                self.particles.remove(p)

    def stars(self, time_taken):
        if time_taken < 42:
            return 3
        if time_taken < 65:
            return 2
        return 1

    def draw_hud(self):
        pygame.draw.rect(SCREEN, (25, 35, 45), (16, 14, 310, 88), border_radius=12)
        draw_text(SCREEN, f"TIME  {self.elapsed:05.1f}s", FONT, WHITE, (31, 23))
        draw_text(SCREEN, f"DEATHS  {self.deaths}", FONT, WHITE, (31, 55))
        progress = clamp(self.bike.x / self.level.finish_x, 0, 1)
        pygame.draw.rect(SCREEN, (80, 90, 95), (365, 25, 370, 13), border_radius=6)
        pygame.draw.rect(SCREEN, (70, 220, 135), (365, 25, int(370 * progress), 13), border_radius=6)
        draw_text(SCREEN, "FINISH", SMALL, WHITE, (745, 20))

    def draw(self):
        self.level.draw(SCREEN, self.camera_x, self.elapsed)
        self.bike.draw(SCREEN, self.camera_x)
        for p in self.particles:
            px, py = int(p[0] - self.camera_x), int(p[1])
            pygame.draw.circle(SCREEN, (255, 190, 70), (px, py), 4)
        if self.state == "playing":
            self.draw_hud()

        if self.state == "menu":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((12, 22, 35, 145))
            SCREEN.blit(overlay, (0, 0))
            draw_text(SCREEN, "DESERT RIDER", BIG, WHITE, (WIDTH // 2, 155), True)
            draw_text(SCREEN, "A PHYSICS MOTORCYCLE PLATFORMER", FONT, (255, 220, 160),
                      (WIDTH // 2, 210), True)
            draw_text(SCREEN, "SELECT YOUR BIKE", FONT, WHITE, (WIDTH // 2, 300), True)
            for i, style in enumerate(Bike.STYLES):
                color = style["frame"]
                rect = pygame.Rect(WIDTH // 2 - 230 + i * 250, 340, 210, 72)
                pygame.draw.rect(SCREEN, color if i == self.selected_style else (70, 75, 85),
                                 rect, border_radius=12)
                draw_text(SCREEN, f"{i + 1}. {style['name']}", SMALL, WHITE, rect.center, True)
            draw_text(SCREEN, "ENTER: START     1 / 2: CHOOSE BIKE", FONT, WHITE,
                      (WIDTH // 2, 470), True)
            draw_text(SCREEN, "W/UP accelerate   S/DOWN brake   A/D flip   SPACE jump",
                      SMALL, WHITE, (WIDTH // 2, 515), True)

        elif self.bike.crashed and self.state == "playing":
            pygame.draw.rect(SCREEN, (25, 25, 30), (300, 245, 500, 135), border_radius=16)
            draw_text(SCREEN, "CRASHED!", BIG, (255, 105, 75), (550, 285), True)
            draw_text(SCREEN, "Press SPACE to respawn at your checkpoint",
                      SMALL, WHITE, (550, 340), True)

        elif self.state == "finished":
            pygame.draw.rect(SCREEN, (25, 35, 45), (300, 190, 500, 260), border_radius=18)
            stars = self.stars(self.finished_time)
            draw_text(SCREEN, "LEVEL COMPLETE!", BIG, WHITE, (550, 245), True)
            draw_text(SCREEN, "★ " * stars + "☆ " * (3 - stars), BIG,
                      (255, 210, 55), (550, 315), True)
            draw_text(SCREEN, f"TIME: {self.finished_time:.2f}s     DEATHS: {self.deaths}",
                      FONT, WHITE, (550, 365), True)
            draw_text(SCREEN, "SPACE: PLAY AGAIN     ESC: MENU", SMALL, WHITE,
                      (550, 410), True)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.state == "menu":
                if event.key == pygame.K_1:
                    self.selected_style = 0
                elif event.key == pygame.K_2:
                    self.selected_style = 1
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.reset()
                    self.bike.style = self.selected_style
                    self.state = "playing"
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif self.state == "finished" and event.key == pygame.K_SPACE:
                self.reset()
                self.state = "playing"
            elif self.state == "playing" and event.key == pygame.K_SPACE:
                if self.bike.crashed:
                    self.respawn()
                else:
                    self.bike.jump()


def main():
    game = Game()
    running = True
    while running:
        dt = min(CLOCK.tick(60) / 1000.0, 0.033)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_event(event)

        game.update(dt)
        game.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
