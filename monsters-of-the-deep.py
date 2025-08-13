import pygame, random, math, time
from collections import deque

# ----------------------------
# Config
# ----------------------------
WIDTH, HEIGHT = 1024, 640
TILE = 32
GRID_W, GRID_H = WIDTH // TILE, HEIGHT // TILE

FPS = 60

# Colors
WHITE=(255,255,255); BLACK=(0,0,0); GREY=(60,60,60)
GREEN=(80,210,120); RED=(220,70,70); YELLOW=(240,210,90); BLUE=(80,160,240); PURPLE=(170,90,210)
ORANGE=(240,140,60); CYAN=(120,210,230)

# ----------------------------
# Helper math
# ----------------------------
def clamp(v, a, b): return max(a, min(b, v))
def dist(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])

# ----------------------------
# Maze generation (DFS)
# ----------------------------
def generate_maze(w, h):
    grid = [[1 for _ in range(h)] for _ in range(w)]
    start = (1,1)
    stack=[start]
    grid[start[0]][start[1]] = 0
    dirs=[(2,0),(-2,0),(0,2),(0,-2)]
    while stack:
        cx,cy = stack[-1]
        random.shuffle(dirs)
        carved=False
        for dx,dy in dirs:
            nx,ny = cx+dx, cy+dy
            if 1<=nx<w-1 and 1<=ny<h-1 and grid[nx][ny]==1:
                grid[nx-dx//2][ny-dy//2]=0
                grid[nx][ny]=0
                stack.append((nx,ny))
                carved=True
                break
        if not carved:
            stack.pop()
    for _ in range((w*h)//40):
        x = random.randrange(1,w-1)
        y = random.randrange(1,h-1)
        grid[x][y]=0
    return grid

# ----------------------------
# Connectivity fixes (guarantee all open tiles reachable from base)
# ----------------------------
def flood_reachable(grid, start):
    """Return a set of open (0) cells reachable from start via 4-neighbors."""
    w, h = len(grid), len(grid[0])
    q = deque([start])
    seen = set([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == 0 and (nx,ny) not in seen:
                seen.add((nx,ny)); q.append((nx,ny))
    return seen

def component_from(grid, seed, banned):
    """Return one open component (set) grown from seed, avoiding 'banned' cells."""
    w, h = len(grid), len(grid[0])
    q = deque([seed])
    comp = set([seed])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and grid[nx][ny] == 0 and (nx,ny) not in comp and (nx,ny) not in banned:
                comp.add((nx,ny)); q.append((nx,ny))
    return comp

def connect_component_with_wall_knock(grid, comp, main):
    """
    Try to connect 'comp' to 'main' by converting a single separating wall to floor.
    Returns True if successful.
    """
    w, h = len(grid), len(grid[0])
    for (x, y) in comp:
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            wx, wy = x+dx, y+dy
            ox, oy = x+2*dx, y+2*dy
            if 0 <= wx < w and 0 <= wy < h and grid[wx][wy] == 1:
                if 0 <= ox < w and 0 <= oy < h and grid[ox][oy] == 0 and (ox,oy) in main:
                    grid[wx][wy] = 0
                    return True
    return False

def carve_corridor(grid, a, b):
    """Carve a thin Manhattan corridor from a to b (inclusive)."""
    ax, ay = a; bx, by = b
    x, y = ax, ay
    while x != bx:
        x += 1 if bx > x else -1
        grid[x][y] = 0
    while y != by:
        y += 1 if by > y else -1
        grid[x][y] = 0

def ensure_full_connectivity(grid, start):
    """
    Ensure all open cells (0) are reachable from 'start'.
    Mutates 'grid' to connect stray open components back to the main region.
    """
    w, h = len(grid), len(grid[0])
    main = flood_reachable(grid, start)
    all_open = {(x,y) for x in range(w) for y in range(h) if grid[x][y] == 0}
    remaining = list(all_open - main)

    while remaining:
        comp = component_from(grid, remaining[0], banned=main)
        if connect_component_with_wall_knock(grid, comp, main):
            main = flood_reachable(grid, start)
        else:
            # carve corridor to nearest main tile
            best_pair = None
            best_d = 10**9
            for cx, cy in comp:
                for mx, my in main:
                    d = abs(cx - mx) + abs(cy - my)
                    if d < best_d:
                        best_d = d
                        best_pair = ((cx,cy), (mx,my))
            if best_pair:
                carve_corridor(grid, best_pair[0], best_pair[1])
                main = flood_reachable(grid, start)

        all_open = {(x,y) for x in range(w) for y in range(h) if grid[x][y] == 0}
        remaining = list(all_open - main)

# ----------------------------
# Pathfinding on grid (BFS for next step)
# ----------------------------
def bfs_next_step(grid, start, goal):
    w,h=len(grid),len(grid[0])
    sx,sy=start; gx,gy=goal
    if (sx,sy)==(gx,gy): return (sx,sy)
    q=deque([(sx,sy)])
    came={ (sx,sy): None }
    neigh=[(1,0),(-1,0),(0,1),(0,-1)]
    while q:
        x,y=q.popleft()
        if (x,y)==(gx,gy): break
        for dx,dy in neigh:
            nx,ny=x+dx,y+dy
            if 0<=nx<w and 0<=ny<h and grid[nx][ny]==0 and (nx,ny) not in came:
                came[(nx,ny)]=(x,y)
                q.append((nx,ny))
    if (gx,gy) not in came:
        return start
    cur=(gx,gy)
    while came[cur] and came[cur]!=start:
        cur=came[cur]
    return cur

# ----------------------------
# Entities
# ----------------------------
class Bullet:
    def __init__(self,pos,vel,damage=1,life=1.5, dot_dps=0, dot_dur=0, slow_factor=1.0, slow_dur=0, color=YELLOW):
        self.x,self.y = pos
        self.vx,self.vy = vel
        self.damage=damage
        self.life=life
        self.alive=True
        self.dot_dps = dot_dps
        self.dot_dur = dot_dur
        self.slow_factor = slow_factor
        self.slow_dur = slow_dur
        self.color = color
        # For wall-mounted turrets: let bullets clear the wall tile before colliding
        self.dist_traveled = 0.0
        self.grace_dist = 12  # pixels before wall collision check

    def update(self,dt,world):
        if not self.alive: return
        dx = self.vx*dt; dy = self.vy*dt
        self.x += dx; self.y += dy
        self.dist_traveled += math.hypot(dx, dy)

        self.life -= dt
        if self.life <= 0:
            self.alive = False

        if self.alive and self.dist_traveled > self.grace_dist:
            gx,gy=int(self.x//TILE), int(self.y//TILE)
            if world.is_solid(gx,gy):
                self.alive=False

    def draw(self,surf):
        if self.alive:
            pygame.draw.circle(surf, self.color, (int(self.x),int(self.y)), 3)

class Enemy:
    def __init__(self,grid_pos, tier=1):
        self.gx,self.gy = grid_pos
        self.x,self.y = self.gx*TILE+TILE/2, self.gy*TILE+TILE/2
        self.base_speed = 1.2 + 0.2*tier
        self.hp = 2 + tier
        self.max_hp = self.hp  # track max HP for HP bar
        self.damage = 4 + 2*tier
        self.tier=tier
        self.path_timer=0
        self.next_cell=(self.gx,self.gy)
        self.alive=True
        self.hit_timer=0
        # Status effects
        self.dots=[]   # list of dicts: {"dps":.., "t":..}
        self.slows=[]  # list of dicts: {"factor":.., "t":..}
    def grid_cell(self): return int(self.x//TILE), int(self.y//TILE)

    def apply_dot(self, dps, duration):
        if dps<=0 or duration<=0: return
        self.dots.append({"dps":dps, "t":duration})

    def apply_slow(self, factor, duration):
        if duration<=0 or factor>=1.0: return
        self.slows.append({"factor":max(0.1, factor), "t":duration})

    def _tick_status(self, dt):
        # DoT
        total_dps=0.0
        for s in self.dots:
            total_dps+=s["dps"]
            s["t"]-=dt
        self.dots=[s for s in self.dots if s["t"]>0]
        if total_dps>0:
            self.hp -= total_dps*dt
            self.hit_timer=0.05
        # Slow
        for s in self.slows:
            s["t"]-=dt
        self.slows=[s for s in self.slows if s["t"]>0]

    def current_speed(self):
        slow_factor = 1.0
        if self.slows:
            slow_factor = min(s["factor"] for s in self.slows)
        return self.base_speed * slow_factor

    def update(self,dt,world):
        if not self.alive: return
        self._tick_status(dt)
        self.hit_timer=max(0, self.hit_timer-dt)
        self.path_timer-=dt
        target = world.base_cell
        if self.path_timer<=0:
            self.next_cell = bfs_next_step(world.grid, self.grid_cell(), target)
            self.path_timer = 0.4
        nx,ny = self.next_cell
        tx,ty = nx*TILE+TILE/2, ny*TILE+TILE/2
        ang = math.atan2(ty-self.y, tx-self.x)
        self.x += math.cos(ang)*self.current_speed()*60*dt
        self.y += math.sin(ang)*self.current_speed()*60*dt
        if world.is_solid(int(self.x//TILE), int(self.y//TILE)):
            self.x=self.gx*TILE+TILE/2; self.y=self.gy*TILE+TILE/2
        else:
            self.gx,self.gy=int(self.x//TILE), int(self.y//TILE)
        if (self.gx,self.gy)==world.base_cell:
            world.base_hp = max(0, world.base_hp - self.damage*dt)
    def draw(self,surf):
        c = (200,60,60) if self.hit_timer<=0 else (255,200,200)
        pygame.draw.circle(surf, c, (int(self.x),int(self.y)), 10+self.tier)
        if self.slows:
            pygame.draw.circle(surf, CYAN, (int(self.x),int(self.y)), 12+self.tier,1)

        # --- HP bar (show when damaged or recently hit) ---
        if self.hp < self.max_hp or self.hit_timer > 0:
            px, py = int(self.x), int(self.y)
            w = 26 + self.tier*3   # slight size bump with tier
            h = 4
            ratio = max(0.0, min(1.0, self.hp / self.max_hp))
            x = px - w//2
            y = py - (14 + self.tier*2)

            # border/background
            pygame.draw.rect(surf, (30,30,30), pygame.Rect(x-1, y-1, w+2, h+2))
            pygame.draw.rect(surf, (90,20,20),  pygame.Rect(x, y, w, h))
            if ratio > 0:
                pygame.draw.rect(surf, (80,210,120), pygame.Rect(x, y, int(w*ratio), h))

class Pickup:
    def __init__(self,pos,kind="scrap",amount=1):
        self.x,self.y=pos
        self.kind=kind
        self.amount=amount
        self.alive=True
        self.pulse=0
    def update(self,dt,_):
        self.pulse=(self.pulse+dt)%1.0
    def draw(self,surf):
        r=6+int(2*math.sin(self.pulse*math.tau))
        color = BLUE if self.kind=="core" else GREEN
        pygame.draw.circle(surf, color, (int(self.x),int(self.y)), r)
        pygame.draw.circle(surf, WHITE, (int(self.x),int(self.y)), r,1)

# ----------------------------
# Turrets
# ----------------------------
TURRET_KINDS = {
    "basic": {
        "color": PURPLE, "rate": 0.7, "range": 220, "proj_speed": 420,
        "damage": 1.0, "dot_dps": 0.0, "dot_dur": 0.0, "slow_factor": 1.0, "slow_dur": 0.0, "bullet_color": YELLOW
    },
    "flame": {
        "color": ORANGE, "rate": 0.45, "range": 180, "proj_speed": 360,
        "damage": 0.5, "dot_dps": 2.0, "dot_dur": 1.3, "slow_factor": 1.0, "slow_dur": 0.0, "bullet_color": ORANGE
    },
    "ice": {
        "color": CYAN, "rate": 0.9, "range": 240, "proj_speed": 400,
        "damage": 0.6, "dot_dps": 0.0, "dot_dur": 0.0, "slow_factor": 0.55, "slow_dur": 1.6, "bullet_color": CYAN
    }
}

MAX_UPGRADE = 5  # per stat

class Turret:
    def __init__(self,cell,turret_type="basic"):
        self.cell=cell
        self.x,self.y=cell[0]*TILE+TILE/2, cell[1]*TILE+TILE/2
        self.type = turret_type if turret_type in TURRET_KINDS else "basic"
        self.cooldown=0
        self.upgrades = {"dmg":0, "rng":0, "rate":0}  # per-turret levels

    # ----- Upgrade economics -----
    def upgrade_level(self, kind): return self.upgrades.get(kind,0)
    def can_upgrade(self, kind): return self.upgrade_level(kind) < MAX_UPGRADE
    def upgrade_cost(self, kind):
        lvl = self.upgrade_level(kind)
        base = {"dmg":6, "rng":5, "rate":7}[kind]
        step = {"dmg":2, "rng":2, "rate":3}[kind]
        return base + step*lvl

    def apply_upgrade(self, kind):
        if self.can_upgrade(kind):
            self.upgrades[kind] += 1

    # ----- Stats w/ upgrade scaling -----
    def base_cfg(self):
        return TURRET_KINDS[self.type]

    def stats(self):
        cfg = self.base_cfg()
        ld = self.upgrade_level("dmg")
        lr = self.upgrade_level("rng")
        lf = self.upgrade_level("rate")

        damage = cfg["damage"] * (1 + 0.25*ld)
        dot_dps = cfg["dot_dps"] * (1 + 0.25*ld)
        dot_dur = cfg["dot_dur"] * (1 + 0.20*ld) if cfg["dot_dur"]>0 else 0.0
        # For ICE: extend slow duration with dmg upgrades (more control)
        slow_factor = cfg["slow_factor"]
        slow_dur = cfg["slow_dur"] * (1 + 0.20*ld) if cfg["slow_dur"]>0 else 0.0

        rng = int(cfg["range"] * (1 + 0.15*lr))
        proj_speed = cfg["proj_speed"] * (1 + 0.05*lr)

        rate = cfg["rate"] * (0.88 ** lf)  # lower cooldown per level

        return {
            "damage": damage, "dot_dps": dot_dps, "dot_dur": dot_dur,
            "slow_factor": slow_factor, "slow_dur": slow_dur,
            "range": rng, "proj_speed": proj_speed, "rate": rate,
            "color": cfg["color"], "bullet_color": cfg["bullet_color"]
        }

    def update(self,dt,world):
        self.cooldown=max(0,self.cooldown-dt)
        if not world.enemies:
            return
        st = self.stats()
        # target closest within upgraded range
        target=min(world.enemies, key=lambda e: dist((self.x,self.y),(e.x,e.y)))
        if dist((self.x,self.y),(target.x,target.y))<st["range"]:
            if self.cooldown==0:
                ang=math.atan2(target.y-self.y, target.x-self.x)
                vx,vy = math.cos(ang)*st["proj_speed"], math.sin(ang)*st["proj_speed"]
                world.bullets.append(
                    Bullet(
                        (self.x,self.y),(vx,vy),
                        damage=st["damage"], life=1.5,
                        dot_dps=st["dot_dps"], dot_dur=st["dot_dur"],
                        slow_factor=st["slow_factor"], slow_dur=st["slow_dur"],
                        color=st["bullet_color"]
                    )
                )
                self.cooldown=st["rate"]

    def draw(self,surf):
        st = self.stats()
        pygame.draw.circle(surf, st["color"],(int(self.x),int(self.y)), 10)
        pygame.draw.circle(surf, WHITE,(int(self.x),int(self.y)), 10,1)
        # small pips to show upgrade levels (dmg/rng/rate)
        px,py=int(self.x),int(self.y)
        for i,kind in enumerate(("dmg","rng","rate")):
            lvl = self.upgrade_level(kind)
            if lvl>0:
                pygame.draw.rect(surf, WHITE, pygame.Rect(px-12+i*8, py+12, 6, 4))
                if lvl>1:
                    pygame.draw.rect(surf, WHITE, pygame.Rect(px-12+i*8, py+17, 6, 4))

# ----------------------------
# World
# ----------------------------
class World:
    def __init__(self):
        self.grid = generate_maze(GRID_W, GRID_H)
        self.base_cell=(GRID_W//2, GRID_H//2)
        for x in range(self.base_cell[0]-2, self.base_cell[0]+3):
            for y in range(self.base_cell[1]-2, self.base_cell[1]+3):
                if 0<=x<GRID_W and 0<=y<GRID_H: self.grid[x][y]=0

        # Ensure everything is reachable from the base
        ensure_full_connectivity(self.grid, self.base_cell)

        self.player = Player(self, (self.base_cell[0]*TILE+TILE/2, self.base_cell[1]*TILE+TILE/2))
        self.enemies=[]
        self.pickups=[]
        self.bullets=[]
        self.turrets=[]
        self.spawn_timer=3
        self.wave=1
        self.base_hp=100.0
        self.camera=(0,0)
        self.deposit_radius=48
        self.message=""
        self.message_timer=0
        # Upgrade UI state
        self.upgrade_target = None

    def say(self,txt,dur=2.0):
        self.message=txt; self.message_timer=dur

    def is_solid(self,gx,gy):
        if 0<=gx<GRID_W and 0<=gy<GRID_H:
            return self.grid[gx][gy]==1
        return True

    def can_place_turret(self, cell):
        gx,gy = cell
        if not (0<=gx<GRID_W and 0<=gy<GRID_H):
            return False
        # Place on WALLS (must be solid)
        if self.grid[gx][gy] == 0:
            return False
        for t in self.turrets:
            if t.cell == cell:
                return False
        return True

    # ---- Upgrades helpers ----
    def nearest_turret_to_world(self, wx, wy, radius=28):
        if not self.turrets: return None
        best=None; bestd=1e9
        for t in self.turrets:
            d=dist((t.x,t.y),(wx,wy))
            if d<radius and d<bestd:
                best=t; bestd=d
        return best

    def upgrade_buy(self, kind):
        t = self.upgrade_target
        if not t: return
        if not t.can_upgrade(kind):
            self.say("Already at max level")
            return
        cost = t.upgrade_cost(kind)
        if self.player.scrap < cost:
            self.say(f"Need {cost} scrap")
            return
        self.player.scrap -= cost
        t.apply_upgrade(kind)
        self.say(f"Upgraded {kind.upper()} to L{t.upgrade_level(kind)}")

    def update(self,dt):
        self.message_timer=max(0,self.message_timer-dt)
        self.player.update(dt)

        for e in list(self.enemies):
            e.update(dt,self)
            if e.hp<=0:
                self.enemies.remove(e)
                if random.random()<0.85:
                    self.pickups.append(Pickup((e.x,e.y),"scrap", amount=1))
                if random.random()<0.18:
                    self.pickups.append(Pickup((e.x,e.y),"core", amount=1))
        for b in list(self.bullets):
            b.update(dt,self)
            if b.alive:
                for e in self.enemies:
                    if dist((b.x,b.y),(e.x,e.y))<12+e.tier and e.alive:
                        e.hp -= b.damage
                        if b.dot_dps>0: e.apply_dot(b.dot_dps, b.dot_dur)
                        if b.slow_factor<1.0: e.apply_slow(b.slow_factor, b.slow_dur)
                        e.hit_timer=0.1
                        b.alive=False
                        break
            if not b.alive:
                self.bullets.remove(b)
        for p in list(self.pickups):
            p.update(dt,self)
            if dist((self.player.x,self.player.y),(p.x,p.y))<14 and self.player.backpack_space():
                self.player.backpack.append(p)
                self.pickups.remove(p)
        for t in self.turrets: t.update(dt,self)

        self.spawn_timer-=dt
        if self.spawn_timer<=0:
            self.spawn_wave()
            self.spawn_timer = max(2.0, 8 - self.wave*0.5)

        self.camera=(int(self.player.x-WIDTH//2), int(self.player.y-HEIGHT//2))
        self.camera=(clamp(self.camera[0],0,GRID_W*TILE-WIDTH), clamp(self.camera[1],0,GRID_H*TILE-HEIGHT))

    def spawn_wave(self):
        count= min(3+self.wave, 18)
        for _ in range(count):
            for _tries in range(100):
                x = random.choice([1, GRID_W-2])
                y = random.randrange(1,GRID_H-1)
                if random.random()<0.5:
                    x = random.randrange(1,GRID_W-1)
                    y = random.choice([1, GRID_H-2])
                if self.grid[x][y]==0:
                    self.enemies.append(Enemy((x,y), tier=1 + self.wave//4))
                    break
        self.wave += 1
        self.say(f"Wave {self.wave-1}!")

    def deposit(self):
        if dist((self.player.x,self.player.y),(self.base_cell[0]*TILE+TILE/2, self.base_cell[1]*TILE+TILE/2))<self.deposit_radius:
            scrap= sum(1 for p in self.player.backpack if p.kind=="scrap")
            cores= sum(1 for p in self.player.backpack if p.kind=="core")
            self.player.backpack.clear()
            self.player.scrap += scrap
            self.player.cores += cores
            if scrap or cores:
                self.say(f"Deposited: {scrap} scrap, {cores} cores")
            else:
                self.say("Backpack is empty")
        else:
            self.say("Stand on the base to deposit")

    def open_shop(self):
        if dist((self.player.x,self.player.y),(self.base_cell[0]*TILE+TILE/2, self.base_cell[1]*TILE+TILE/2))<self.deposit_radius:
            self.player.in_shop=True
        else:
            self.say("You must be on the base to shop")

    def buy(self, item):
        p=self.player
        if item=="speed" and p.scrap>=5:
            p.scrap-=5; p.speed*=1.08; self.say("Speed +8%")
        elif item=="damage" and p.scrap>=7:
            p.scrap-=7; p.attack_damage+=0.5; self.say("Damage +0.5")
        elif item=="hp" and p.scrap>=6:
            p.scrap-=6; p.max_hp+=10; p.hp=p.max_hp; self.say("HP +10")
        elif item=="capacity" and p.scrap>=8:
            p.scrap-=8; p.backpack_capacity+=3; self.say("Backpack +3")
        elif item=="turret_basic" and p.cores>=3:
            p.cores-=3; p.add_turret_kit("basic"); self.say("Basic turret kit acquired")
        elif item=="turret_flame" and p.cores>=4:
            p.cores-=4; p.add_turret_kit("flame"); self.say("Flame turret kit acquired")
        elif item=="turret_ice" and p.cores>=4:
            p.cores-=4; p.add_turret_kit("ice"); self.say("Ice turret kit acquired")
        elif item=="basehp" and p.cores>=2:
            p.cores-=2; self.base_hp=min(200, self.base_hp+30); self.say("Base repaired +30")
        else:
            self.say("Not enough currency")

    def draw(self,screen):
        ox,oy = -self.camera[0], -self.camera[1]
        screen.fill((10,10,15))
        for x in range(GRID_W):
            for y in range(GRID_H):
                rect=pygame.Rect(x*TILE+ox, y*TILE+oy, TILE, TILE)
                if self.grid[x][y]==1:
                    pygame.draw.rect(screen, GREY, rect)
                else:
                    pygame.draw.rect(screen, (20,20,26), rect,1)
        bx,by=self.base_cell[0]*TILE+TILE/2+ox, self.base_cell[1]*TILE+TILE/2+oy
        pygame.draw.circle(screen, (40,60,80), (int(bx),int(by)), self.deposit_radius)
        pygame.draw.circle(screen, (120,140,200), (int(bx),int(by)), self.deposit_radius,2)

        for p in self.pickups: p.draw(screen)
        for t in self.turrets:
            t.draw(screen)
            # If it's the selected upgrade target, show its (upgraded) range
            if t is self.upgrade_target:
                rng = t.stats()["range"]
                pygame.draw.circle(screen, (220,220,240), (int(t.x- self.camera[0]), int(t.y- self.camera[1])), rng, 1)
        for e in self.enemies: e.draw(screen)
        for b in self.bullets: b.draw(screen)
        self.player.draw(screen)

        if self.upgrade_target:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            screen.blit(overlay, (0, 0))

        self.draw_turret_preview(screen)
        self.draw_darkness(screen)
        self.draw_ui(screen)

    def draw_turret_preview(self, screen):
        if not self.player.placing_turret: return
        mx, my = pygame.mouse.get_pos()
        wx = mx + self.camera[0]
        wy = my + self.camera[1]
        gx, gy = int(wx//TILE), int(wy//TILE)
        cx, cy = gx*TILE + TILE//2 - self.camera[0], gy*TILE + TILE//2 - self.camera[1]
        valid = self.can_place_turret((gx,gy))
        ttype = self.player.placing_type or "basic"
        col = TURRET_KINDS[ttype]["color"]
        if not valid:
            col = (max(0,col[0]-80), max(0,col[1]-80), max(0,col[2]-80))
        pygame.draw.circle(screen, col, (int(cx),int(cy)), 12, 2)
        pygame.draw.circle(screen, WHITE, (int(cx),int(cy)), 12, 1)
        # range ring (base stats preview)
        rng = TURRET_KINDS[ttype]["range"]
        pygame.draw.circle(screen, (200,200,220), (int(cx),int(cy)), rng, 1)

    def draw_darkness(self,screen):
        dark = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA)
        px,py = int(self.player.x-self.camera[0]), int(self.player.y-self.camera[1])
        radius = 130 + int(20*self.player.flashlight_level)
        for r,alpha in [(radius,180),(radius//2,90)]:
            pygame.draw.circle(dark,(0,0,0,alpha),(px,py),r)
        pygame.draw.circle(dark,(0,0,0,0),(px,py), int(radius*0.6))
        screen.blit(dark,(0,0), special_flags=pygame.BLEND_RGBA_SUB)

    def draw_ui(self,screen):
        font=pygame.font.SysFont("consolas",18)
        big=pygame.font.SysFont("consolas",24, bold=True)
        kits = self.player.turret_kits
        kits_text = f"B:{kits.get('basic',0)} F:{kits.get('flame',0)} I:{kits.get('ice',0)}"
        text=f"HP {int(self.player.hp)}/{int(self.player.max_hp)}  Scrap:{self.player.scrap}  Cores:{self.player.cores}  Kits[{kits_text}]  Backpack:{len(self.player.backpack)}/{self.player.backpack_capacity}  Wave:{self.wave-1}  BaseHP:{int(self.base_hp)}"
        screen.blit(font.render(text,True,WHITE),(10,10))
        if self.message_timer>0:
            msgsurf=big.render(self.message,True,YELLOW)
            screen.blit(msgsurf,(WIDTH//2-msgsurf.get_width()//2,10))
        if self.player.in_shop:
            self.draw_shop(screen)
        if self.base_hp<=0:
            over=big.render("BASE DESTROYED! Press R to restart.",True,RED)
            screen.blit(over,(WIDTH//2-over.get_width()//2, HEIGHT//2-20))
        if self.player.placing_turret:
            tip = font.render(
                f"Placing [{self.player.placing_type}] on WALLS: Left-click place • Right-click/Esc cancel • [Tab] cycle",
                True, (220,220,240)
            )
            screen.blit(tip, (WIDTH//2 - tip.get_width()//2, HEIGHT-30))
        if self.upgrade_target:
            self.draw_upgrade_panel(screen)

    def draw_shop(self,screen):
        font=pygame.font.SysFont("consolas",18)
        panel=pygame.Surface((420,320))
        panel.fill((16,22,30))
        pygame.draw.rect(panel,(80,120,160),panel.get_rect(),2)
        lines=[
            "SHOP (on base) — [Esc] to close",
            "1) +8% Speed ............ 5 scrap",
            "2) +0.5 Damage .......... 7 scrap",
            "3) +10 HP ............... 6 scrap",
            "4) +3 Backpack Capacity . 8 scrap",
            "5) Basic Turret ......... 3 cores",
            "6) Repair Base +30 ...... 2 cores",
            "7) Flame Turret (DoT) ... 4 cores",
            "8) Ice Turret (Slow) .... 4 cores",
            "",
            "Press [1-8] to buy."
        ]
        for i,l in enumerate(lines):
            panel.blit(font.render(l,True,WHITE),(12,12+i*24))
        screen.blit(panel,(WIDTH-440, HEIGHT-340))

    def draw_upgrade_panel(self, screen):
        t = self.upgrade_target
        if not t: return
        font=pygame.font.SysFont("consolas",18)
        small=pygame.font.SysFont("consolas",16)
        panel=pygame.Surface((420,210))
        panel.fill((18,20,28))
        pygame.draw.rect(panel,(140,180,240),panel.get_rect(),2)
        title = f"UPGRADE TURRET [{t.type.upper()}] — scrap:{self.player.scrap}"
        panel.blit(font.render(title, True, WHITE),(12,10))

        # Levels & costs
        def line(lbl, key, y):
            lvl = t.upgrade_level(key)
            cost = t.upgrade_cost(key)
            maxed = lvl >= MAX_UPGRADE
            text = f"{lbl}  Lvl {lvl}/{MAX_UPGRADE}  —  Cost: {cost} scrap"
            col = (200,200,200) if not maxed else (160,160,160)
            panel.blit(font.render(text, True, col),(24,y))
            if maxed:
                panel.blit(small.render("MAXED", True, (240,210,90)), (panel.get_width()-90, y))

        line("1) +Damage (boosts DoT/slow duration on special)", "dmg", 52)
        line("2) +Range", "rng", 84)
        line("3) +Fire Rate (lower cooldown)", "rate", 116)
        panel.blit(small.render("Press [1-3] to buy • [Esc] to close • Stand close to a turret & press U to open", True, (200,210,230)), (12, 160))
        screen.blit(panel,(20, HEIGHT-240))

    def draw_pause_menu(self,screen):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        title_font = pygame.font.SysFont("consolas", 36, bold=True)
        title = title_font.render("PAUSED", True, (255, 255, 255))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 200))
        labels = ["Resume", "Restart", "Main Menu", "Quit"]
        btn_w, btn_h = 320, 56
        spacing = 72
        start_y = HEIGHT//2 - 80
        mx,my = pygame.mouse.get_pos()
        rects = []
        for i, label in enumerate(labels):
            rect = pygame.Rect(WIDTH//2 - btn_w//2, start_y + i*spacing, btn_w, btn_h)
            hovered = rect.collidepoint(mx,my)
            draw_button(screen, rect, label, hovered)
            rects.append((label, rect))
        hint = pygame.font.SysFont("consolas", 16).render("Press P/Esc to resume", True, (200,210,230))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, start_y + len(labels)*spacing + 10))
        return rects

class Player:
    def __init__(self, world, pos):
        self.world=world
        self.x,self.y=pos
        self.speed=2.1
        self.max_hp=100; self.hp=self.max_hp
        self.attack_damage=1.0
        self.backpack=[]; self.backpack_capacity=5
        self.scrap=0; self.cores=0
        self.in_shop=False
        self.shoot_cooldown=0
        self.flashlight_level=1
        # turret kits & placement
        self.turret_kits = {"basic":0, "flame":0, "ice":0}
        self.placing_turret = False
        self.placing_type = None

    def backpack_space(self):
        return len(self.backpack) < self.backpack_capacity
    def add_turret_kit(self, ttype):
        if ttype not in self.turret_kits: self.turret_kits[ttype]=0
        self.turret_kits[ttype]+=1
        # enter placement for that type immediately
        self.placing_turret = True
        self.placing_type = ttype
    def cycle_turret_type(self):
        types = [t for t,c in self.turret_kits.items() if c>0]
        if not types: return
        if self.placing_type not in types:
            self.placing_type = types[0]; return
        idx = types.index(self.placing_type)
        self.placing_type = types[(idx+1)%len(types)]

    def update(self,dt):
        keys=pygame.key.get_pressed()
        mx,my = pygame.mouse.get_pos()
        dx=(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=(keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        length=math.hypot(dx,dy) or 1.0
        vx,vy = dx/length*self.speed*120*dt, dy/length*self.speed*120*dt
        self.move(vx,vy)
        self.shoot_cooldown=max(0,self.shoot_cooldown-dt)
        if pygame.mouse.get_pressed()[0] and self.shoot_cooldown==0 and self.world.base_hp>0 and not self.in_shop and not self.placing_turret and not self.world.upgrade_target:
            px,py=self.x,self.y
            wx = mx + self.world.camera[0]
            wy = my + self.world.camera[1]
            ang=math.atan2(wy-py, wx-px)
            speed=520
            self.world.bullets.append(
                Bullet((px,py),(math.cos(ang)*speed, math.sin(ang)*speed),damage=self.attack_damage, color=YELLOW)
            )
            self.shoot_cooldown=0.2
        for e in list(self.world.enemies):
            if dist((self.x,self.y),(e.x,e.y))<14+e.tier:
                self.hp-=12*dt
                if self.hp<=0: self.respawn()
        self.x=clamp(self.x, 0, GRID_W*TILE-1); self.y=clamp(self.y, 0, GRID_H*TILE-1)

    def move(self,vx,vy):
        nx=self.x+vx; ny=self.y+vy
        if not self.world.is_solid(int(nx//TILE), int(self.y//TILE)):
            self.x=nx
        if not self.world.is_solid(int(self.x//TILE), int(ny//TILE)):
            self.y=ny

    def draw(self,screen):
        px,py=int(self.x-self.world.camera[0]), int(self.y-self.world.camera[1])
        pygame.draw.circle(screen, (200,200,220), (px,py), 10)
        for i,p in enumerate(self.backpack[:8]):
            color = BLUE if p.kind=="core" else GREEN
            pygame.draw.circle(screen, color, (px-14+i*6, py-18), 3)

    def respawn(self):
        self.x,self.y = self.world.base_cell[0]*TILE+TILE/2, self.world.base_cell[1]*TILE+TILE/2
        self.hp=self.max_hp
        lost=int(len(self.backpack)*0.7)
        self.backpack=self.backpack[lost:]
        self.world.say("You were knocked out! Dropped some loot.", 2.5)

# ----------------------------
# Menu helpers
# ----------------------------
def draw_button(surface, rect, text, hovered=False):
    pygame.draw.rect(surface, (20,28,36), rect)
    pygame.draw.rect(surface, (80,120,160) if hovered else (60,90,120), rect, 2)
    font = pygame.font.SysFont("consolas", 26, bold=True)
    label = font.render(text, True, WHITE)
    surface.blit(label, (rect.centerx - label.get_width()//2, rect.centery - label.get_height()//2))

def draw_title(surface, title, subtitle=None):
    surface.fill((10,10,15))
    big = pygame.font.SysFont("consolas", 40, bold=True)
    sub = pygame.font.SysFont("consolas", 20)
    t = big.render(title, True, (200,220,255))
    surface.blit(t, (WIDTH//2 - t.get_width()//2, 120))
    if subtitle:
        s = sub.render(subtitle, True, (180, 190, 210))
        surface.blit(s, (WIDTH//2 - s.get_width()//2, 170))

def draw_main_menu(surface, items, hovered_index):
    draw_title(surface, "MONSTERS OF THE DEEP", "tiny roguelite prototype")
    start_y = 240
    spacing = 72
    btn_w, btn_h = 360, 56
    mx,my = pygame.mouse.get_pos()
    rects=[]
    for i, label in enumerate(items):
        rect = pygame.Rect(WIDTH//2 - btn_w//2, start_y + i*spacing, btn_w, btn_h)
        rects.append(rect)
        hovered = rect.collidepoint(mx,my) or (hovered_index == i)
        draw_button(surface, rect, label, hovered)
    tiny = pygame.font.SysFont("consolas", 16)
    hint = tiny.render("W/S or ↑/↓ to navigate • Enter/Space to select • Mouse supported", True, (160,170,190))
    surface.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT-60))
    return rects

def draw_help(surface):
    draw_title(surface, "HOW TO PLAY")
    panel = pygame.Surface((680, 392))
    panel.fill((16,22,30))
    pygame.draw.rect(panel, (80,120,160), panel.get_rect(), 2)
    font=pygame.font.SysFont("consolas",20)
    lines = [
        "WASD or Arrow Keys to move",
        "Mouse to aim and Left Click to shoot",
        "[E] deposit on base, [B] shop on base",
        "[1-8] buy in shop, [R] restart",
        "[Esc] or [P] pause",
        "T to enter turret placement (Tab to cycle type)",
        "U near a turret: open upgrade panel (1-3 to buy)",
        "",
        "Protect the base in the center. Collect scrap and cores.",
        "Spend scrap/cores in the shop; upgrade turrets with scrap."
    ]
    for i,l in enumerate(lines):
        panel.blit(font.render(l, True, WHITE), (16, 16 + i*32))
    surface.blit(panel, (WIDTH//2 - panel.get_width()//2, 230))
    rect = pygame.Rect(WIDTH//2 - 140, HEIGHT - 100, 280, 52)
    mx,my = pygame.mouse.get_pos()
    draw_button(surface, rect, "Back", rect.collidepoint(mx,my))
    return rect

# ----------------------------
# Game loop
# ----------------------------
def main():
    pygame.init()
    screen=pygame.display.set_mode((WIDTH,HEIGHT))
    pygame.display.set_caption("Monsters of the Deep — roguelite prototype")
    clock=pygame.time.Clock()

    game_state = "menu"  # "menu", "help", "playing", "paused"
    selected_index = 0
    menu_items = ["Start Game", "How to Play", "Quit"]
    world=None
    paused=False

    font=pygame.font.SysFont("consolas",18)
    help_lines=[
        "WASD to move, Mouse to aim/shoot",
        "[E] deposit on base, [B] shop on base",
        "[1-8] buy in shop, [R] restart, [Esc] close shop",
        "T place turret kit (Tab cycle) • U to upgrade turret"
    ]
    helpsurf=pygame.Surface((620,120))
    helpsurf.fill((16,22,30))
    pygame.draw.rect(helpsurf,(80,120,160),helpsurf.get_rect(),2)
    for i,l in enumerate(help_lines):
        helpsurf.blit(font.render(l,True,WHITE),(10,8+i*22))
    help_timer=5.0

    running=True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if game_state == "menu":
                    if ev.key in (pygame.K_DOWN, pygame.K_s):
                        selected_index = (selected_index + 1) % len(menu_items)
                    elif ev.key in (pygame.K_UP, pygame.K_w):
                        selected_index = (selected_index - 1) % len(menu_items)
                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        choice = menu_items[selected_index]
                        if choice == "Start Game":
                            world = World()
                            game_state = "playing"
                            paused = False
                            help_timer = 5.0
                        elif choice == "How to Play":
                            game_state = "help"
                        elif choice == "Quit":
                            running = False
                    elif ev.key in (pygame.K_ESCAPE,):
                        running = False

                elif game_state == "help":
                    if ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                        game_state = "menu"

                elif game_state == "playing":
                    # Esc / P: close shop or upgrade, or cancel placement, or pause
                    if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                        if world.player.in_shop:
                            world.player.in_shop = False
                        elif world.upgrade_target:
                            world.upgrade_target = None
                            world.say("Closed upgrade panel")
                        elif ev.key == pygame.K_ESCAPE and world.player.placing_turret:
                            world.player.placing_turret = False
                            world.say("Turret placement cancelled")
                        else:
                            paused = not paused
                            game_state = "paused" if paused else "playing"

                    elif not paused:
                        if ev.key == pygame.K_r:
                            world = World()

                        elif ev.key == pygame.K_c:
                            # Cheat Key
                            world.player.scrap+=15
                            world.player.cores+=10
                            for k in world.player.turret_kits:
                                world.player.turret_kits[k]+=2

                        elif ev.key == pygame.K_b:
                            # Toggle shop when on the base
                            if world.player.in_shop:
                                world.player.in_shop = False
                            else:
                                world.open_shop()

                        elif ev.key == pygame.K_e:
                            world.deposit()

                        elif ev.key == pygame.K_t:
                            avail = [t for t,c in world.player.turret_kits.items() if c>0]
                            if avail:
                                world.player.placing_turret = True
                                if world.player.placing_type not in avail:
                                    world.player.placing_type = avail[0]
                                world.say("Turret placement mode")
                            else:
                                world.say("No turret kits")

                        elif ev.key == pygame.K_TAB and world.player.placing_turret:
                            world.player.cycle_turret_type()

                        elif ev.key == pygame.K_u and (not world.player.in_shop):
                            # open upgrade panel for turret under cursor if close enough
                            mx,my = pygame.mouse.get_pos()
                            wx = mx + world.camera[0]
                            wy = my + world.camera[1]
                            t = world.nearest_turret_to_world(wx, wy, radius=24)
                            if t and dist((world.player.x,world.player.y),(t.x,t.y))<=80:
                                world.upgrade_target = t
                                world.say("Upgrade: 1)Damage  2)Range  3)Rate  • Esc to close")
                            elif t:
                                world.say("Move closer to the turret to upgrade")
                            else:
                                world.say("No turret under cursor")

                        # Shop buying (when shop open)
                        elif world.player.in_shop and ev.key in (
                            pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                            pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8
                        ):
                            idx = {
                                pygame.K_1:"speed", pygame.K_2:"damage", pygame.K_3:"hp",
                                pygame.K_4:"capacity", pygame.K_5:"turret_basic", pygame.K_6:"basehp",
                                pygame.K_7:"turret_flame", pygame.K_8:"turret_ice"
                            }[ev.key]
                            world.buy(idx)

                        # Upgrade purchases (when upgrade panel open)
                        elif world.upgrade_target and ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                            kmap = {pygame.K_1:"dmg", pygame.K_2:"rng", pygame.K_3:"rate"}
                            world.upgrade_buy(kmap[ev.key])

                elif game_state == "paused":
                    if ev.key in (pygame.K_p, pygame.K_ESCAPE):
                        paused = False
                        game_state = "playing"
                    elif ev.key == pygame.K_r:
                        world = World()
                        paused = False
                        game_state = "playing"
                    elif ev.key == pygame.K_q:
                        running = False

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                if game_state == "menu" and ev.button==1:
                    rects = draw_main_menu(screen, menu_items, selected_index)
                    for i, r in enumerate(rects):
                        if r.collidepoint(mx,my):
                            selected_index = i
                            choice = menu_items[i]
                            if choice == "Start Game":
                                world = World()
                                game_state = "playing"
                                paused = False
                                help_timer = 5.0
                            elif choice == "How to Play":
                                game_state = "help"
                            elif choice == "Quit":
                                running = False
                            break
                elif game_state == "help" and ev.button==1:
                    back_rect = draw_help(screen)
                    if back_rect.collidepoint(mx,my):
                        game_state = "menu"
                elif game_state == "paused" and world and ev.button==1:
                    buttons = world.draw_pause_menu(screen)
                    for label, rect in buttons:
                        if rect.collidepoint(mx,my):
                            if label == "Resume":
                                paused = False; game_state = "playing"
                            elif label == "Restart":
                                world = World(); paused = False; game_state = "playing"
                            elif label == "Main Menu":
                                game_state = "menu"; paused = False; world = None
                            elif label == "Quit":
                                running = False
                            break
                elif game_state == "playing" and world:
                    # turret placement clicks
                    if world.player.placing_turret:
                        if ev.button == 1:  # left click: attempt place
                            wx = mx + world.camera[0]
                            wy = my + world.camera[1]
                            gx, gy = int(wx//TILE), int(wy//TILE)
                            if world.can_place_turret((gx,gy)) and world.player.placing_type:
                                world.turrets.append(Turret((gx,gy), world.player.placing_type))
                                ttype = world.player.placing_type
                                world.player.turret_kits[ttype] -= 1
                                if world.player.turret_kits[ttype] <= 0:
                                    avail = [t for t,c in world.player.turret_kits.items() if c>0]
                                    if avail:
                                        world.player.placing_type = avail[0]
                                    else:
                                        world.player.placing_turret = False
                                world.say(f"{ttype.capitalize()} turret placed")
                            else:
                                world.say("Can't place there")
                        elif ev.button == 3:  # right click: cancel placement
                            world.player.placing_turret = False
                            world.say("Turret placement cancelled")
                    # click outside to close upgrade panel
                    elif world.upgrade_target and ev.button==1:
                        # close if you click far from the panel and not on target turret
                        wx = mx + world.camera[0]; wy = my + world.camera[1]
                        if dist((wx,wy),(world.upgrade_target.x, world.upgrade_target.y))>80:
                            world.upgrade_target=None

        # Update
        if (
            game_state == "playing"
            and (not paused)
            and world
            and (not world.player.in_shop)
            and world.base_hp > 0
            and (world.upgrade_target is None)  # <-- pause game logic during upgrade menu
        ):
            world.update(dt)

        # Draw
        if game_state in ("menu", "help"):
            if game_state == "menu":
                rects = draw_main_menu(screen, menu_items, -1)
                if 0 <= selected_index < len(rects):
                    pygame.draw.rect(screen, (240,210,90), rects[selected_index], 3)
            else:
                draw_help(screen)
        else:
            if world:
                world.draw(screen)
            if paused and world:
                world.draw_pause_menu(screen)
            if help_timer > 0 and world and game_state == "playing":
                help_timer -= dt
                screen.blit(helpsurf, (10, HEIGHT - helpsurf.get_height() - 10))

        pygame.display.flip()

    pygame.quit()

if __name__=="__main__":
    main()
