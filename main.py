import pygame
import time
import math
import neat
import os
import random
from utils import scale_image, blit_rotate_center, blit_text_center
pygame.font.init()

GRASS = scale_image(pygame.image.load("imgs/grass.jpg"), 2.5)
TRACK = scale_image(pygame.image.load("imgs/track.png"), 0.9)

TRACK_BORDER = scale_image(pygame.image.load("imgs/track-border.png"), 0.9)
TRACK_BORDER_MASK = pygame.mask.from_surface(TRACK_BORDER)

FINISH = pygame.image.load("imgs/finish.png")
FINISH_MASK = pygame.mask.from_surface(FINISH)
FINISH_POSITION = (130, 250)

RED_CAR = scale_image(pygame.image.load("imgs/red-car.png"), 0.55)
GREEN_CAR = scale_image(pygame.image.load("imgs/green-car.png"), 0.55)

cars = []
ge = []
nets = []
gates = []
counter = 0
counter_max = 75

WIDTH, HEIGHT = TRACK.get_width(), TRACK.get_height()
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Racing Game!")

MAIN_FONT = pygame.font.SysFont("comicsans", 44)

FPS = 60
PATH = [(175, 119), (110, 70), (56, 133), (70, 481), (318, 731), (404, 680), (418, 521), (507, 475), (600, 551), (613, 715), (736, 713),
        (734, 399), (611, 357), (409, 343), (433, 257), (697, 258), (738, 123), (581, 71), (303, 78), (275, 377), (176, 388), (178, 260)]

class Gate:
    def __init__(self, x, y, width, height, id):
        self.rect = pygame.Rect(x, y, width, height)
        self.x = x
        self.y = y
        self.img = pygame.image.load("imgs/finish.png")
        self.width = width
        self.height = height
        self.id = id

    def check_collision(self, car, x):
        # Create masks for car and gate
        car_mask = pygame.mask.from_surface(car.IMG)
        gate_mask = pygame.mask.from_surface(self.img)

        # Calculate offset between car and gate
        offset = (int(self.x - car.x), int(self.y - car.y))
        offset2 = (int(self.y - car.y), int(self.x - car.x))

        # Check if masks collide
        if car_mask.overlap(gate_mask, offset) or car_mask.overlap(gate_mask, offset2):

            # If car passed through the gate for the first time, increase its fitness
            if self.id not in car.passed_gates:
                car.number_of_gates_passed += 1
                ge[x].fitness += 50*car.number_of_gates_passed
                car.passed_gates.append(self.id)


    def draw(self, win):
        pygame.draw.rect(win, (255, 0, 0), self.rect)

class GameInfo:
    LEVELS = 10

    def __init__(self, level=1):
        self.level = level
        self.started = True
        self.level_start_time = 0

    def next_level(self):
        self.level += 1
        self.started = True

    def reset(self):
        self.level = 1
        self.started = True
        self.level_start_time = 0

    def game_finished(self):
        return self.level > self.LEVELS

    def start_level(self):
        self.started = True
        self.level_start_time = time.time()

    def get_level_time(self):
        if not self.started:
            return 0
        return round(time.time() - self.level_start_time)


class AbstractCar:
    def __init__(self, max_vel, rotation_vel, START):
        self.img = self.IMG
        self.max_vel = max_vel
        self.vel = 0
        self.rotation_vel = rotation_vel
        self.angle = 0
        self.width = 20
        self.height = 10
        self.number_of_gates_passed = 0
        self.passed_gates = []
        self.x, self.y = START
        self.acceleration = 0.1

    def rotate(self, left=False, right=False):
        if left:
            self.angle += self.rotation_vel
        elif right:
            self.angle -= self.rotation_vel

    def draw(self, win):
        blit_rotate_center(win, self.img, (self.x, self.y), self.angle)

    def move_forward(self):
        self.vel = min(self.vel + self.acceleration, self.max_vel)
        self.move()

    def move_backward(self):
        self.vel = max(self.vel - self.acceleration, -self.max_vel/2)
        self.move()

    def move(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.vel
        horizontal = math.sin(radians) * self.vel

        self.y -= vertical
        self.x -= horizontal

    def collide(self, mask, x=0, y=0):
        car_mask = pygame.mask.from_surface(self.img)
        offset = (int(self.x - x), int(self.y - y))
        poi = mask.overlap(car_mask, offset)
        return poi

    def reset(self):
        self.x, self.y = self.START_POS
        self.angle = 0
        self.vel = 0

    def distance_to_wall(self, mask, max_distance=20, angles=[0]):
        """
        Returns a list of distances to the nearest wall in front of the car for each angle in `angles`.
        If there is no wall within `max_distance`, it returns `max_distance`.
        """
        distances = []
        for angle in angles:
            radians = math.radians(self.angle + angle)
            x, y = self.x, self.y
            for distance in range(1, max_distance):
                vertical = math.sin(radians) * distance
                horizontal = math.cos(radians) * distance
                y -= vertical
                x += horizontal
                if not 0 < y < mask.get_size()[1] or not 0 < x < mask.get_size()[0]:
                    distances.append(max_distance)
                    break
                poi = mask.get_at((int(x), int(y)))
                if poi == 1:
                    distances.append(distance)
                    break
                elif distance == max_distance - 1:
                    distances.append(max_distance)
        return distances


class PlayerCar(AbstractCar):
    IMG = RED_CAR
    #180,200
    #720,130
    #720, 430
    #400,600

    def reduce_speed(self):
        self.vel = max(self.vel - self.acceleration / 2, 0)
        self.move()

    def bounce(self):
        self.vel = -self.vel*0.5
        self.move()


class ComputerCar(AbstractCar):
    IMG = GREEN_CAR
    #START_POS = (150, 200)

    def __init__(self, max_vel, rotation_vel, path=[]):
        super().__init__(max_vel, rotation_vel)
        self.path = path
        self.current_point = 0
        self.vel = max_vel

    def draw_points(self, win):
        for point in self.path:
            pygame.draw.circle(win, (255, 0, 0), point, 5)

    def draw(self, win):
        super().draw(win)
        # self.draw_points(win)

    def calculate_angle(self):
        target_x, target_y = self.path[self.current_point]
        x_diff = target_x - self.x
        y_diff = target_y - self.y

        if y_diff == 0:
            desired_radian_angle = math.pi / 2
        else:
            desired_radian_angle = math.atan(x_diff / y_diff)

        if target_y > self.y:
            desired_radian_angle += math.pi

        difference_in_angle = self.angle - math.degrees(desired_radian_angle)
        if difference_in_angle >= 180:
            difference_in_angle -= 360

        if difference_in_angle > 0:
            self.angle -= min(self.rotation_vel, abs(difference_in_angle))
        else:
            self.angle += min(self.rotation_vel, abs(difference_in_angle))

    def update_path_point(self):
        target = self.path[self.current_point]
        rect = pygame.Rect(
            self.x, self.y, self.img.get_width(), self.img.get_height())
        if rect.collidepoint(*target):
            self.current_point += 1

    def move(self):
        if self.current_point >= len(self.path):
            return

        self.calculate_angle()
        self.update_path_point()
        super().move()

    def next_level(self, level):
        self.reset()
        self.vel = self.max_vel + (level - 1) * 0.2
        self.current_point = 0


def draw(win, images,gates,cars, player_car, game_info):
    for img, pos in images:
        win.blit(img, pos)

    level_text = MAIN_FONT.render(
        f"Level {game_info.level}", 1, (255, 255, 255))
    win.blit(level_text, (10, HEIGHT - level_text.get_height() - 70))

    time_text = MAIN_FONT.render(
        f"Time: {game_info.get_level_time()}s", 1, (255, 255, 255))
    win.blit(time_text, (10, HEIGHT - time_text.get_height() - 40))

    vel_text = MAIN_FONT.render(
        f"Vel: {round(player_car.vel, 1)}px/s", 1, (255, 255, 255))
    win.blit(vel_text, (10, HEIGHT - vel_text.get_height() - 10))

    for car in cars:
        car.draw(win)
    player_car.draw(win)
    for gate in gates:
        gate.draw(win)
    #computer_car.draw(win)
    pygame.display.update()


def move_player(player_car):
    keys = pygame.key.get_pressed()
    moved = False

    if keys[pygame.K_a]:
        player_car.rotate(left=True)
    if keys[pygame.K_d]:
        player_car.rotate(right=True)
    if keys[pygame.K_w]:
        moved = True
        player_car.move_forward()
    if keys[pygame.K_s]:
        moved = True
        player_car.move_backward()

    if not moved:
        player_car.reduce_speed()


def handle_collision(cars, player_car, game_info, time_survived):
    if player_car.collide(TRACK_BORDER_MASK) != None:
        player_car.bounce()
    for x, car in enumerate(cars):
        if car.collide(TRACK_BORDER_MASK) != None:
            car.bounce()
            ge[x].fitness -= 1000/time_survived
            cars.pop(x)
            ge.pop(x)
            nets.pop(x)

    #computer_finish_poi_collide = computer_car.collide(
     #   FINISH_MASK, *FINISH_POSITION)
    #if computer_finish_poi_collide != None:
     #   blit_text_center(WIN, MAIN_FONT, "You lost!")
      #  pygame.display.update()
       # pygame.time.wait(5000)
        #game_info.reset()
        #player_car.reset()
        #computer_car.reset()

    player_finish_poi_collide = player_car.collide(
        FINISH_MASK, *FINISH_POSITION)
    if player_finish_poi_collide != None:
        if player_finish_poi_collide[1] == 0:
            player_car.bounce()
        else:
            game_info.next_level()
            player_car.reset()
           # computer_car.next_level(game_info.level)

def main(genomes, config):
    global counter
    global counter_max
    time_survived = 0
    if counter_max < 400:
        counter_max += 10
    counter = counter_max
    run = True
    clock = pygame.time.Clock()
    images = [(GRASS, (0, 0)), (TRACK, (0, 0)),
              (FINISH, FINISH_POSITION), (TRACK_BORDER, (0, 0))]
    dist = random.choice([(180,200),(720,100),(720,460), (400, 650)])
    #dist = (400,310)
    player_car = PlayerCar(6, 4, START = dist)

    #computer_car = ComputerCar(2, 4,random.choice([(180,200),(720,130),(720,430), (400, 600)]), PATH)
    game_info = GameInfo()

    for _, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        cars.append(PlayerCar(max_vel= 2, rotation_vel=8, START=  dist))
        g.fitness = 0
        ge.append(g)
    while run:
        clock.tick(FPS)
        counter -= 1
        time_survived += 1
        if len(cars) == 0:
            run = False
            break
        draw(WIN, images, gates, cars, player_car, game_info)
        while not game_info.started:
            #blit_text_center(
             #   WIN, MAIN_FONT, f"Press any key to start level {game_info.level}!")
            pygame.display.update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    break

                #if event.type == pygame.KEYDOWN:
                game_info.start_level()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break
        #print(player_car.distance_to_wall(TRACK_BORDER_MASK, angles=[0, 45, 90, 135, 180]))
        for x, car in enumerate(cars):
            car.move()
            if len(car.passed_gates) != 0:
                cur = max(car.passed_gates)
                if cur == 39:
                    cur = 1
                for gate in gates[cur:cur+1]:
                    gate.check_collision(car, x)
            else:
                for gate in gates:
                    gate.check_collision(car, x)
                #print(max(car.passed_gates))
            #if time_survived < 5000:
                #for gate in gates[0:15]:
                   # gate.check_collision(car, x)
            #else:


            distances = car.distance_to_wall(TRACK_BORDER_MASK, angles=[30, 60, 90, 120, 150])
            #print(distances)
            distances.append(car.vel)
            distances.append(car.rotation_vel)
            output = nets[x].activate(distances)

            #if car.vel > 1.5:
                #ge[x].fitness += car.vel**2/4
            distance_traveled = 0
            if time_survived % 30 == 0:
                distance_traveled += distance_traveled
                ge[x].fitness += 25*car.vel

            if output[0] > 0.05:
                car.move_forward()
                #ge[x].fitness += 1

            if output[1] > 0.5:
                car.rotate(left=False, right=True)

            if output[2] > 0.5:
                car.rotate(left=True, right=False)

            #if output[2] > 0.5:
             #   car.move_backward()
              #  ge[x].fitness -= 0.5

            if counter <= 0:
                ge.pop(x)
                cars.pop(x)
                nets.pop(x)

        move_player(player_car)
        #computer_car.move()

        handle_collision(cars, player_car, game_info, time_survived)

        if game_info.game_finished():
            blit_text_center(WIN, MAIN_FONT, "You won the game!")
            pygame.time.wait(50)
            game_info.reset()
            player_car.reset()
           # computer_car.reset()

def run(config_path):
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction, neat.DefaultSpeciesSet, neat.DefaultStagnation, config_path)

    p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)
    winner = p.run(main)

if __name__ == "__main__":
    gates.append(Gate(x=140, y=190, width=100, height=20, id = 1))
    gates.append(Gate(x=120, y=20, width=20, height=100, id = 2))
    gates.append(Gate(x=20, y=100, width=100, height=20, id = 3))
    gates.append(Gate(x=20, y=200, width=100, height=20, id=4))
    gates.append(Gate(x=20, y=300, width=100, height=20, id=5))
    gates.append(Gate(x=20, y=400, width=100, height=20, id=6))
    gates.append(Gate(x=80, y=530, width=100, height=20, id=7))
    gates.append(Gate(x=130, y=600, width=100, height=20, id=8))
    gates.append(Gate(x=210, y=670, width=100, height=20, id=9))
    gates.append(Gate(x=350, y=680, width=20, height=100, id=10))
    gates.append(Gate(x=350, y=690, width=100, height=20, id=11))
    gates.append(Gate(x=350, y=600, width=100, height=20, id=12))
    gates.append(Gate(x=390, y=500, width=100, height=20, id=13))
    gates.append(Gate(x=500, y=440, width=20, height=100, id=14))
    gates.append(Gate(x=520, y=500, width=100, height=20, id=15))
    gates.append(Gate(x=550, y=600, width=100, height=20, id=16))
    gates.append(Gate(x=650, y=670, width=20, height=100, id=17))
    gates.append(Gate(x=680, y=670, width=100, height=20, id=18))
    gates.append(Gate(x=680, y=570, width=100, height=20, id=19))
    gates.append(Gate(x=680, y=470, width=100, height=20, id=20))
    gates.append(Gate(x=680, y=370, width=100, height=20, id=21))
    gates.append(Gate(x=680, y=330, width=20, height=100, id=22))
    gates.append(Gate(x=580, y=330, width=20, height=100, id=23))
    gates.append(Gate(x=480, y=330, width=20, height=100, id=24))
    gates.append(Gate(x=360, y=300, width=100, height=20, id=25))
    gates.append(Gate(x=480, y=210, width=20, height=100, id=26))
    gates.append(Gate(x=580, y=210, width=20, height=100, id=27))
    gates.append(Gate(x=680, y=210, width=20, height=100, id=28))
    gates.append(Gate(x=680, y=210, width=100, height=20, id=29))
    gates.append(Gate(x=680, y=110, width=100, height=20, id=30))
    gates.append(Gate(x=680, y=20, width=20, height=100, id=31))
    gates.append(Gate(x=580, y=20, width=20, height=100, id=32))
    gates.append(Gate(x=480, y=20, width=20, height=100, id=33))
    gates.append(Gate(x=380, y=20, width=20, height=100, id=34))
    gates.append(Gate(x=230, y=120, width=100, height=20, id=35))
    gates.append(Gate(x=230, y=220, width=100, height=20, id=36))
    gates.append(Gate(x=230, y=320, width=100, height=20, id=37))
    gates.append(Gate(x=230, y=350, width=20, height=100, id=38))
    gates.append(Gate(x=100, y=320, width=100, height=20, id=39))


    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config")
    run(config_path)


pygame.quit()