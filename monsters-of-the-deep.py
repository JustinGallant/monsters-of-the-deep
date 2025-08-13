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

# ----------------------------
# Helper math
# ----------------------------
def clamp(v, a, b): return max(a, min(b, v))
def dist(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])

# ----------------------------
# Maze generation (DFS)
# ----------------------------
def generate_maze(w, h):
    # grid: 1 = wall, 0 = floor
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
    # open some extra loops
    for _ in range((w*h)//40):
        x = random.randrange(1,w-1)
        y = random.randrange(1,h-1)
        grid[x][y]=0
    return grid

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
    # backtrack one step from goal
    cur=(gx,gy)
    while came[cur] and came[cur]!=start:
        cur=came[cur]
    return cur

# ----------------------------
# Entities
# ----------------------------
class Bullet:
    def __init__(self,pos,vel,damage=1,life=1.5):
        self.x,self.y = pos
        self.vx,self.vy = vel
        self.damage=damage
        self.life=life
        self.alive=True
    def update(self,dt,world):
        if not self.alive: return
        self.x+=self.vx*dt; self.y+=self.vy*dt
        self.life-=dt
        if self.life<=0: self.alive=False
        # collide walls
        gx,gy=int(self.x//TILE), int(self.y//TILE)
        if world.is_solid(gx,gy): self.alive=False
    def draw(self,surf):
        if self.alive:
            pygame.draw.circle(surf, YELLOW, (int(self.x),int(self.y)), 3)

class Enemy:
    def __init__(self,grid_pos, tier=1):
        self.gx,self.gy = grid_pos
        self.x,self.y = self.gx*TILE+TILE/2, self.gy*TILE+TILE/2
        self.hp = 2 + tier
        self.speed = 1.2 + 0.2*tier
        self.damage = 4 + 2*tier
        self.tier=tier
        self.path_timer=0
        self.next_cell=(self.gx,self.gy)
        self.alive=True
        self.hit_timer=0
    def grid_cell(self): return int(self.x//TILE), int(self.y//TILE)
    def update(self,dt,world):
        if not self.alive: return
        self.hit_timer=max(0, self.hit_timer-dt)
        self.path_timer-=dt
        target = world.base_cell
        if self.path_timer<=0:
            self.next_cell = bfs_next_step(world.grid, self.grid_cell(), target)
            self.path_timer = 0.4
        nx,ny = self.next_cell
        tx,ty = nx*TILE+TILE/2, ny*TILE+TILE/2
        ang = math.atan2(ty-self.y, tx-self.x)
        self.x += math.cos(ang)*self.speed*60*dt
        self.y += math.sin(ang)*self.speed*60*dt
        # clamp in corridors
        if world.is_solid(int(self.x//TILE), int(self.y//TILE)):
            self.x=self.gx*TILE+TILE/2; self.y=self.gy*TILE+TILE/2
        else:
            self.gx,self.gy=int(self.x//TILE), int(self.y//TILE)
        # reached base?
        if (self.gx,self.gy)==world.base_cell:
            world.base_hp = max(0, world.base_hp - self.damage*dt)
    def draw(self,surf):
        c = (200,60,60) if self.hit_timer<=0 else (255,200,200)
        pygame.draw.circle(surf, c, (int(self.x),int(self.y)), 10+self.tier)

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

class Turret:
    def __init__(self,cell):
        self.cell=cell
        self.x,self.y=cell[0]*TILE+TILE/2, cell[1]*TILE+TILE/2
        self.cooldown=0
        self.rate=0.7
        self.range=220
    def update(self,dt,world):
        self.cooldown=max(0,self.cooldown-dt)
        if self.cooldown==0 and world.enemies:
            # target closest
            target=min(world.enemies, key=lambda e: dist((self.x,self.y),(e.x,e.y)))
            if dist((self.x,self.y),(target.x,target.y))<self.range:
                ang=math.atan2(target.y-self.y, target.x-self.x)
                speed=420
                world.bullets.append(Bullet((self.x,self.y),(math.cos(ang)*speed, math.sin(ang)*speed),damage=1))
                self.cooldown=self.rate
    def draw(self,surf):
        pygame.draw.circle(surf, PURPLE,(int(self.x),int(self.y)), 10)
        pygame.draw.circle(surf, WHITE,(int(self.x),int(self.y)), 10,1)

# ----------------------------
# World
# ----------------------------
class World:
    def __init__(self):
        self.grid = generate_maze(GRID_W, GRID_H)
        # carve a central room as base/shop
        self.base_cell=(GRID_W//2, GRID_H//2)
        for x in range(self.base_cell[0]-2, self.base_cell[0]+3):
            for y in range(self.base_cell[1]-2, self.base_cell[1]+3):
                if 0<=x<GRID_W and 0<=y<GRID_H: self.grid[x][y]=0
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
    def say(self,txt,dur=2.0):
        self.message=txt; self.message_timer=dur
    def is_solid(self,gx,gy):
        if 0<=gx<GRID_W and 0<=gy<GRID_H:
            return self.grid[gx][gy]==1
        return True
    def update(self,dt):
        self.message_timer=max(0,self.message_timer-dt)
        self.player.update(dt)
        for e in list(self.enemies):
            e.update(dt,self)
            if e.hp<=0:
                self.enemies.remove(e)
                # drop loot
                if random.random()<0.85:
                    self.pickups.append(Pickup((e.x,e.y),"scrap", amount=1))
                if random.random()<0.18:
                    self.pickups.append(Pickup((e.x,e.y),"core", amount=1))
        for b in list(self.bullets):
            b.update(dt,self)
            # bullet vs enemy
            if b.alive:
                for e in self.enemies:
                    if dist((b.x,b.y),(e.x,e.y))<12+e.tier and e.alive:
                        e.hp-=self.player.attack_damage
                        e.hit_timer=0.1
                        b.alive=False
                        break
            if not b.alive:
                self.bullets.remove(b)
        for p in list(self.pickups):
            p.update(dt,self)
            if dist((self.player.x,self.player.y),(p.x,p.y))<14 and len(self.player.backpack)<self.player.backpack_capacity:
                self.player.backpack.append(p)
                self.pickups.remove(p)
        for t in self.turrets: t.update(dt,self)
        # enemy spawn logic
        self.spawn_timer-=dt
        if self.spawn_timer<=0:
            self.spawn_wave()
            self.spawn_timer = max(2.0, 8 - self.wave*0.5)
        # camera follows player
        self.camera=(int(self.player.x-WIDTH//2), int(self.player.y-HEIGHT//2))
        self.camera=(clamp(self.camera[0],0,GRID_W*TILE-WIDTH), clamp(self.camera[1],0,GRID_H*TILE-HEIGHT))
    def spawn_wave(self):
        count= min(3+self.wave, 18)
        for _ in range(count):
            # pick random edge cell that is floor
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
        # convert pickups in backpack into currencies
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
        elif item=="turret" and p.cores>=3:
            p.cores-=3; self.turrets.append(Turret(self.base_cell)); self.say("Turret installed")
        elif item=="basehp" and p.cores>=2:
            p.cores-=2; self.base_hp=min(200, self.base_hp+30); self.say("Base repaired +30")
        else:
            self.say("Not enough currency")
    def draw(self,screen):
        # world to screen offset
        ox,oy = -self.camera[0], -self.camera[1]
        # draw floor
        screen.fill((10,10,15))
        for x in range(GRID_W):
            for y in range(GRID_H):
                rect=pygame.Rect(x*TILE+ox, y*TILE+oy, TILE, TILE)
                if self.grid[x][y]==1:
                    pygame.draw.rect(screen, GREY, rect)
                else:
                    pygame.draw.rect(screen, (20,20,26), rect,1)
        # base area
        bx,by=self.base_cell[0]*TILE+TILE/2+ox, self.base_cell[1]*TILE+TILE/2+oy
        pygame.draw.circle(screen, (40,60,80), (int(bx),int(by)), self.deposit_radius)
        pygame.draw.circle(screen, (120,140,200), (int(bx),int(by)), self.deposit_radius,2)
        for p in self.pickups: p.draw(screen)
        for t in self.turrets: t.draw(screen)
        for e in self.enemies: e.draw(screen)
        for b in self.bullets: b.draw(screen)
        self.player.draw(screen)
        self.draw_darkness(screen)
        self.draw_ui(screen)
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
        text=f"HP {int(self.player.hp)}/{int(self.player.max_hp)}  Scrap:{self.player.scrap}  Cores:{self.player.cores}  Backpack:{len(self.player.backpack)}/{self.player.backpack_capacity}  Wave:{self.wave-1}  BaseHP:{int(self.base_hp)}"
        screen.blit(font.render(text,True,WHITE),(10,10))
        if self.message_timer>0:
            msgsurf=big.render(self.message,True,YELLOW)
            screen.blit(msgsurf,(WIDTH//2-msgsurf.get_width()//2,10))
        if self.player.in_shop:
            self.draw_shop(screen)
        if self.base_hp<=0:
            over=big.render("BASE DESTROYED! Press R to restart.",True,RED)
            screen.blit(over,(WIDTH//2-over.get_width()//2, HEIGHT//2-20))
    def draw_shop(self,screen):
        font=pygame.font.SysFont("consolas",18)
        panel=pygame.Surface((380,260))
        panel.fill((16,22,30))
        pygame.draw.rect(panel,(80,120,160),panel.get_rect(),2)
        lines=[
            "SHOP (on base) — [Esc] to close",
            "1) +8% Speed ............ 5 scrap",
            "2) +0.5 Damage .......... 7 scrap",
            "3) +10 HP ............... 6 scrap",
            "4) +3 Backpack Capacity . 8 scrap",
            "5) Install Turret ....... 3 cores",
            "6) Repair Base +30 ...... 2 cores",
            "",
            "Press [1-6] to buy."
        ]
        for i,l in enumerate(lines):
            panel.blit(font.render(l,True,WHITE),(12,12+i*24))
        screen.blit(panel,(WIDTH-400, HEIGHT-280))

    # --- NEW: pause menu with clickable buttons ---
    def draw_pause_menu(self,screen):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        title_font = pygame.font.SysFont("consolas", 36, bold=True)
        title = title_font.render("PAUSED", True, (255, 255, 255))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 160))

        # buttons
        labels = ["Resume", "Main Menu", "Restart", "Quit"]
        btn_w, btn_h = 320, 56
        spacing = 72
        start_y = HEIGHT//2 - 60
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
    def update(self,dt):
        keys=pygame.key.get_pressed()
        mx,my = pygame.mouse.get_pos()
        dx=(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=(keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        length=math.hypot(dx,dy) or 1.0
        vx,vy = dx/length*self.speed*120*dt, dy/length*self.speed*120*dt
        self.move(vx,vy)
        self.shoot_cooldown=max(0,self.shoot_cooldown-dt)
        if pygame.mouse.get_pressed()[0] and self.shoot_cooldown==0 and self.world.base_hp>0 and not self.in_shop:
            px,py=self.x,self.y
            wx = mx + self.world.camera[0]
            wy = my + self.world.camera[1]
            ang=math.atan2(wy-py, wx-px)
            speed=520
            self.world.bullets.append(Bullet((px,py),(math.cos(ang)*speed, math.sin(ang)*speed),damage=self.attack_damage))
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
    panel = pygame.Surface((680, 320))
    panel.fill((16,22,30))
    pygame.draw.rect(panel, (80,120,160), panel.get_rect(), 2)
    font=pygame.font.SysFont("consolas",20)
    lines = [
        "WASD or Arrow Keys to move",
        "Mouse to aim and Left Click to shoot",
        "[E] deposit on base, [B] shop on base",
        "[1-6] buy in shop, [R] restart",
        "[Esc] or [P] pause",
        "",
        "Protect the base in the center. Collect scrap and cores.",
        "Spend scrap/cores in the shop to upgrade and survive waves."
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
        "[1-6] buy in shop, [R] restart, [Esc] close shop",
    ]
    helpsurf=pygame.Surface((420,80))
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
                    if ev.key in (pygame.K_p, pygame.K_ESCAPE):
                        if world.player.in_shop:
                            world.player.in_shop = False
                        else:
                            paused = not paused
                            game_state = "paused" if paused else "playing"
                    elif not paused:
                        if ev.key == pygame.K_r:
                            world = World()
                        elif ev.key == pygame.K_e:
                            world.deposit()
                        elif ev.key == pygame.K_b:
                            world.open_shop()
                        elif world.player.in_shop and ev.key in (
                            pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6
                        ):
                            idx = {
                                pygame.K_1:"speed", pygame.K_2:"damage", pygame.K_3:"hp",
                                pygame.K_4:"capacity", pygame.K_5:"turret", pygame.K_6:"basehp"
                            }[ev.key]
                            world.buy(idx)

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

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx,my = ev.pos
                if game_state == "menu":
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
                elif game_state == "help":
                    back_rect = draw_help(screen)
                    if back_rect.collidepoint(mx,my):
                        game_state = "menu"
                elif game_state == "paused" and world:
                    # NEW: clickable pause menu
                    buttons = world.draw_pause_menu(screen)
                    for label, rect in buttons:
                        if rect.collidepoint(mx,my):
                            if label == "Resume":
                                paused = False
                                game_state = "playing"
                            elif label == "Main Menu":
                                game_state = "menu"
                                paused = False
                                world = None
                            elif label == "Restart":
                                world = World()
                                paused = False
                                game_state = "playing"
                            elif label == "Quit":
                                running = False
                            break

        # Update
        if game_state == "playing" and (not paused) and world and (not world.player.in_shop) and world.base_hp > 0:
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
