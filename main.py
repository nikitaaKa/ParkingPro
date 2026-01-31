import arcade
import math
import sqlite3
import random
from pyglet.graphics import Batch

# Константы для настройки игры
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
SCREEN_TITLE = "Parking Pro"
TILE_SCALING = 1.0
PLAYER_SCALING = 1.45
CAR_SCALING = 1.0

# Физические константы для управления автомобилем
ACCELERATION_RATE = 0.2  # Ускорение при нажатии клавиш движения
DECELERATION_RATE = 0.15  # Замедление при отпускании клавиш
MAX_SPEED = 3.0  # Максимальная скорость автомобиля
TURN_SPEED = 1  # Скорость поворота
FRICTION = 0.1  # Трение для естественного замедления

# Данные уровней: начальная позиция и границы парковочного места
LEVELS_DATA = [
    {'spawn_pos': (580, 540, 180),
     'parking_borders': (539, 32, 613, 160)
     },
    {'spawn_pos': (576, 576, 225),
     'parking_borders': (347, 32, 421, 160)
     },
    {'spawn_pos': (451, 93, 0),
     'parking_borders': (219, 32, 293, 160)
     },
    {'spawn_pos': (577, 232, 0),
     'parking_borders': (288, 539, 416, 613)
     },
    {'spawn_pos': (192, 540, 180),
     'parking_borders': (283, 32, 357, 160)
     }
]

# Режим отладки (бессмертие и доступ ко всем уровням)
CHEAT_MODE = False


class PlayerCar(arcade.Sprite):
    """Класс игрового автомобиля, наследующий от arcade.Sprite"""
    def __init__(self, filename, scale):
        super().__init__(filename, scale)
        self.speed = 0  # Текущая скорость автомобиля
        self.angle_speed = 0  # Скорость вращения

    def update(self):
        """Обновление позиции и состояния автомобиля каждый кадр"""
        # Движение вперед/назад с учетом угла поворота
        angle_rad = math.radians(self.angle)
        self.center_x += self.speed * math.sin(angle_rad)
        self.center_y += self.speed * math.cos(angle_rad)
        
        # Поворот только при движении (как у реальной машины)
        self.angle += self.angle_speed * self.speed if abs(self.speed) > 0.1 else 0

        # Естественное замедление из-за трения
        if abs(self.speed) > 0:
            if self.speed > 0:
                self.speed -= FRICTION
                if self.speed < 0:
                    self.speed = 0
            else:
                self.speed += FRICTION
                if self.speed > 0:
                    self.speed = 0

        # Ограничение максимальной скорости
        if abs(self.speed) > MAX_SPEED:
            self.speed = MAX_SPEED if self.speed > 0 else -MAX_SPEED


class WinParticles:
    """Система частиц для эффектов"""
    def __init__(self):
        self.particles = []
        self.emitting = False
        
    def emit_confetti(self, x, y, count=50):
        """Создание конфетти при победе"""
        colors = [
            (255, 105, 97),
            (255, 180, 128),
            (248, 243, 141),
            (126, 232, 250),
            (138, 201, 38),
            (199, 146, 234),
        ]
        
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(2, 8)
            size = random.uniform(4, 10)
            lifetime = random.uniform(60, 120)
            
            self.particles.append({
                'x': x,
                'y': y,
                'vx': math.sin(angle) * speed,
                'vy': math.cos(angle) * speed,
                'size': size,
                'color': random.choice(colors),
                'lifetime': lifetime,
                'max_lifetime': lifetime
            })
        
        self.emitting = True
    
    def update(self):
        """Обновление частиц"""
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['vy'] -= 0.1
            particle['lifetime'] -= 1

            particle['size'] *= 0.99

            if particle['lifetime'] <= 0:
                self.particles.remove(particle)

        if len(self.particles) == 0:
            self.emitting = False
    
    def draw(self):
        """Отрисовка частиц"""
        for particle in self.particles:
            alpha = int(255 * (particle['lifetime'] / particle['max_lifetime']))
            color = (*particle['color'][:3], alpha)
            
            arcade.draw_circle_filled(
                particle['x'], particle['y'],
                particle['size'], color
            )


class MenuView(arcade.View):
    """Класс главного меню игры"""
    def __init__(self):
        super().__init__()
        self.buttons = []  # Список кнопок уровней
        self.unlocked_levels = 0  # Количество доступных уровней
        self.menu_music = None  # Фоновая музыка меню
        self.music_player = None  # Объект воспроизведения музыки
        self.con = sqlite3.connect("levels.db")
        self.cur = self.con.cursor()

    def setup(self, unlocked_levels=1):
        """Инициализация меню с указанием количества открытых уровней"""
        arcade.set_background_color((26, 20, 35))
        self.unlocked_levels = unlocked_levels

        self.cur.execute("CREATE TABLE IF NOT EXISTS levels (LevelsOpened INT);")
        if len(self.cur.execute("SELECT * FROM levels").fetchall()) < 1:
            self.cur.execute("INSERT INTO levels (LevelsOpened) VALUES (1)")
        elif self.unlocked_levels == 1:
            self.unlocked_levels = self.cur.execute("SELECT LevelsOpened FROM levels").fetchone()[0]
        self.con.commit()
        if CHEAT_MODE:
            self.unlocked_levels = 5  # В режиме читов открываем все уровни
        
        # Создание кнопок для каждого уровня
        self.buttons = []
        for i in range(1, 6):
            button = arcade.SpriteSolidColor(80, 80, color=(183, 93, 105))
            button.center_x = SCREEN_WIDTH // 6 * i
            button.center_y = SCREEN_HEIGHT // 2
            button.level = i  # Номер уровня на кнопке
            button.enabled = i <= self.unlocked_levels  # Доступность уровня
            button.color = (183, 93, 105) if button.enabled else (119, 76, 96)
            self.buttons.append(button)
        
        # Создание batch для эффективного отображения текста
        self.batch = Batch()
        
        # Заголовок игры
        self.header = arcade.Text('Parking Pro',
                             SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 1.3,
                             (234, 205, 194),
                             60,
                             align='center',
                             anchor_x='center',
                             anchor_y='center',
                             bold=True,
                             font_name='Comic Sans MS',
                             batch=self.batch)
        
        # Подзаголовок
        self.additional_text = arcade.Text('Выберите уровень',
                             SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 1.5,
                             (219, 174, 180),
                             24,
                             align='center',
                             anchor_x='center',
                             anchor_y='center',
                             font_name='Comic Sans MS',
                             batch=self.batch)
        
        # Номера на кнопках
        self.numbers = []
        for btn in self.buttons:
            text = arcade.Text(str(btn.level),
                               btn.center_x,
                               btn.center_y,
                               (234, 205, 194),
                               20,
                               align='center',
                               anchor_x='center',
                               anchor_y='center',
                               font_name='Comic Sans MS',
                               batch=self.batch)
            self.numbers.append(text)
        
        # Изображение машины в меню
        self.menu_car = arcade.load_texture('assets/images/menu_car.png')
        
        # Загрузка и воспроизведение музыки меню
        if not self.menu_music:
            self.menu_music = arcade.Sound('assets/sounds/menu_music.mp3', streaming=True)
        self.music_player = self.menu_music.play(loop=True, volume=0.3)

    def on_draw(self):
        """Отрисовка всех элементов меню"""
        self.clear()
        # Отрисовка кнопок
        for btn in self.buttons:
            arcade.draw_sprite(btn)
            self.batch.draw()
        # Отрисовка машины
        arcade.draw_texture_rect(self.menu_car,
                                 arcade.rect.XYWH(SCREEN_WIDTH // 2,
                                                  SCREEN_HEIGHT // 4,
                                                  360, 360))

    def on_mouse_press(self, x, y, button, modifiers):
        """Обработка кликов мыши по кнопкам уровней"""
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        for btn in self.buttons:
            # Проверка попадания клика в границы кнопки
            if btn.left < x < btn.right and btn.bottom < y < btn.top:
                if btn.enabled:
                    # Запуск выбранного уровня
                    game_view = GameView()
                    game_view.setup(btn.level, self.unlocked_levels)
                    self.window.show_view(game_view)

    def on_hide_view(self):
        """Остановка музыки и выход из базы данных при скрытии меню"""
        self.con.close()
        if self.music_player:
            self.menu_music.stop(self.music_player)


class GameView(arcade.View):
    """Класс игрового экрана (уровня)"""
    def __init__(self):
        super().__init__()
        self.level = 0  # Текущий уровень
        self.unlocked_levels = 0  # Количество открытых уровней
        self.player_sprite = None  # Спрайт игрока
        self.collision = None  # Список спрайтов для коллизий
        self.background = None  # Фоновые спрайты
        self.decor = None  # Декоративные элементы
        self.cars = None  # Машины-препятствия
        self.parking_borders = ()  # Границы парковочного места
        self.physics_engine = None  # Движок физики для коллизий
        self.level_completed = False  # Флаг завершения уровня
        self.level_failed = False  # Флаг проигрыша
        self.music = None  # Игровая музыка
        self.music_player = None  # Объект воспроизведения музыки
        self.moving_forward = False  # Флаг движения вперед
        self.moving_backward = False  # Флаг движения назад
        self.particle_system = None  # Система частиц
        self.con = sqlite3.connect("levels.db")
        self.cur = self.con.cursor()
        
    def setup(self, level, unlocked_levels):
        """Инициализация уровня с указанным номером"""
        self.level = level
        self.unlocked_levels = unlocked_levels
        self.level_completed = False
        self.level_failed = False
        self.moving_forward = False
        self.moving_backward = False

        # Загрузка тайловой карты уровня
        tilemap = arcade.load_tilemap(f'assets/levels/level{self.level}.tmx', TILE_SCALING)

        # Расчет размеров карты и смещения для центрирования
        self.map_width = tilemap.width * tilemap.tile_width
        self.map_height = tilemap.height * tilemap.tile_height
        self.offset_x = (SCREEN_WIDTH - self.map_width) // 2
        self.offset_y = (SCREEN_HEIGHT - self.map_height) // 2

        # Загрузка слоев тайловой карты
        self.collision = tilemap.sprite_lists['collision']
        self.background = tilemap.sprite_lists['background']
        self.decor = tilemap.sprite_lists['decor']
        self.cars = tilemap.sprite_lists['cars']

        # Корректировка позиций спрайтов с учетом смещения
        for spr in self.collision:
            spr.center_x += self.offset_x
            spr.center_y += self.offset_y

        for spr in self.background:
            spr.center_x += self.offset_x
            spr.center_y += self.offset_y

        for spr in self.decor:
            spr.center_x += self.offset_x
            spr.center_y += self.offset_y

        for spr in self.cars:
            spr.center_x += self.offset_x
            spr.center_y += self.offset_y

        # Загрузка и воспроизведение игровой музыки
        if not self.music:
            self.music = arcade.Sound('assets/sounds/music.mp3', streaming=True)
        self.music_player = self.music.play(loop=True, volume=0.3)

        # Установка начальной позиции игрока
        x, y, angle = LEVELS_DATA[self.level-1]['spawn_pos']
        self.parking_borders = LEVELS_DATA[self.level-1]['parking_borders']
        self.player_sprite = PlayerCar('assets/images/car.png', PLAYER_SCALING)
        self.player_sprite.center_x = x
        self.player_sprite.center_y = y
        self.player_sprite.angle = angle
        self.player_sprite.center_x += self.offset_x
        self.player_sprite.center_y += self.offset_y

        # Создание интерфейса уровня
        self.batch = Batch()
        self.level_text = arcade.Text(f'Level {self.level}',
                                      10,
                                      SCREEN_HEIGHT - 10,
                                      (234, 205, 194),
                                      18,
                                      align='left',
                                      anchor_x='left',
                                      anchor_y='top',
                                      font_name='Comic Sans MS',
                                      batch=self.batch)
        
        # Создание текста обучения для первого уровня
        if self.level == 1:
            offsets = [(-2, 0), (2, 0), (0, -2), (0, 2)]
            self.offseted_texts = []
            # Создание обводки текста через смещенные копии
            for dx, dy in offsets:
                text = arcade.Text('УПРАВЛЕНИЕ:\nWASD и стрелки',
                122 + self.offset_x + dx,
                SCREEN_HEIGHT - (26 + self.offset_y) + dy,
                (0, 0, 0),
                24,
                align='left',
                anchor_x='left',
                anchor_y='top',
                font_name='Comic Sans MS',
                multiline=True,
                width=1111111111,
                batch=self.batch)
                self.offseted_texts.append(text)
            # Основной текст обучения
            self.tutorial_text = arcade.Text('УПРАВЛЕНИЕ:\nWASD и стрелки',
                                      122 + self.offset_x,
                                      SCREEN_HEIGHT - (26 + self.offset_y),
                                      (234, 205, 194),
                                      24,
                                      align='left',
                                      anchor_x='left',
                                      anchor_y='top',
                                      font_name='Comic Sans MS',
                                      multiline=True,
                                      width=1111111111,
                                      batch=self.batch)

        # Создание физического движка для обработки коллизий
        self.physics_engine = arcade.PhysicsEngineSimple(player_sprite=self.player_sprite,
                                                         walls=self.collision)
        
        self.particle_system = WinParticles()

    def on_draw(self):
        """Отрисовка всех элементов уровня"""
        self.clear()
        # Отрисовка слоев в правильном порядке
        self.background.draw()
        self.decor.draw()
        arcade.draw_sprite(self.player_sprite)
        self.cars.draw()
        self.batch.draw()
        # Отрисовка UI поверх игры
        if self.level_failed:
            self._draw_game_over_ui()
        elif self.level_completed:
            self._draw_level_complete_ui()
        if self.particle_system:
            self.particle_system.draw()

    def _draw_level_complete_ui(self):
        """Отрисовка экрана победы"""
        # Полупрозрачное затемнение
        arcade.draw_rect_filled(
            arcade.rect.XYWH(SCREEN_WIDTH // 2, 
            SCREEN_HEIGHT // 2,
            SCREEN_WIDTH, 
            SCREEN_HEIGHT),
            (0, 0, 0, 200)
        )

        # Текст победы
        if self.level == 5:
            text = "Вы прошли все уровни!"
            text_color = arcade.color.GOLD
        else:
            text = "Уровень пройден!"
            text_color = arcade.color.GREEN

        arcade.draw_text(
            text,
            SCREEN_WIDTH // 2,
            SCREEN_HEIGHT // 2 + 80,
            text_color,
            font_size=40,
            anchor_x="center",
            anchor_y="center",
            bold=True
        )

        # Создание кнопок в зависимости от номера уровня
        button_width = 220
        button_height = 60
        button_y = SCREEN_HEIGHT // 2 - 20
        
        if self.level == 5:
            # Для последнего уровня только кнопки "Заново" и "В меню"
            self.restart_button = (SCREEN_WIDTH // 2, button_y, button_width, button_height)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(self.restart_button[0], self.restart_button[1],
                self.restart_button[2], self.restart_button[3]),
                arcade.color.BLUE
            )
            arcade.draw_text(
                "Заново",
                self.restart_button[0], self.restart_button[1],
                arcade.color.WHITE,
                font_size=26,
                anchor_x="center",
                anchor_y="center"
            )

            self.menu_button = (SCREEN_WIDTH // 2, button_y - 90, button_width, button_height)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(self.menu_button[0], self.menu_button[1],
                self.menu_button[2], self.menu_button[3]),
                arcade.color.GRAY
            )
            arcade.draw_text(
                "В главное меню",
                self.menu_button[0], self.menu_button[1],
                arcade.color.WHITE,
                font_size=26,
                anchor_x="center",
                anchor_y="center"
            )
            
        else:
            # Для обычных уровней кнопки "Заново", "Дальше" и "В меню"
            self.restart_button = (SCREEN_WIDTH // 2 - 130, button_y, button_width, button_height)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(self.restart_button[0], self.restart_button[1],
                self.restart_button[2], self.restart_button[3]),
                arcade.color.BLUE
            )
            arcade.draw_text(
                "Заново",
                self.restart_button[0], self.restart_button[1],
                arcade.color.WHITE,
                font_size=26,
                anchor_x="center",
                anchor_y="center"
            )

            self.next_button = (SCREEN_WIDTH // 2 + 130, button_y, button_width, button_height)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(self.next_button[0], self.next_button[1],
                self.next_button[2], self.next_button[3]),
                arcade.color.GREEN
            )
            arcade.draw_text(
                "Дальше",
                self.next_button[0], self.next_button[1],
                arcade.color.WHITE,
                font_size=26,
                anchor_x="center",
                anchor_y="center"
            )

            self.menu_button = (SCREEN_WIDTH // 2, button_y - 90, button_width, button_height)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(self.menu_button[0], self.menu_button[1],
                self.menu_button[2], self.menu_button[3]),
                arcade.color.GRAY
            )
            arcade.draw_text(
                "В главное меню",
                self.menu_button[0], self.menu_button[1],
                arcade.color.WHITE,
                font_size=26,
                anchor_x="center",
                anchor_y="center"
            )

    def _draw_game_over_ui(self):
        """Отрисовка экрана проигрыша"""
        # Полупрозрачное затемнение
        arcade.draw_rect_filled(
            arcade.rect.XYWH(SCREEN_WIDTH // 2, 
            SCREEN_HEIGHT // 2,
            SCREEN_WIDTH, 
            SCREEN_HEIGHT),
            (0, 0, 0, 200)
        )

        # Текст проигрыша
        arcade.draw_text(
            "Вы проиграли, попробуйте снова",
            SCREEN_WIDTH // 2,
            SCREEN_HEIGHT // 2 + 80,
            arcade.color.RED,
            font_size=40,
            anchor_x="center",
            anchor_y="center",
            bold=True
        )

        # Кнопки "Заново" и "В меню"
        button_width = 220
        button_height = 60
        button_y = SCREEN_HEIGHT // 2 - 20

        self.restart_button = (SCREEN_WIDTH // 2 - 130, button_y, button_width, button_height)
        arcade.draw_rect_filled(
            arcade.rect.XYWH(self.restart_button[0], self.restart_button[1],
            self.restart_button[2], self.restart_button[3]),
            arcade.color.BLUE
        )
        arcade.draw_text(
            "Заново",
            self.restart_button[0], self.restart_button[1],
            arcade.color.WHITE,
            font_size=26,
            anchor_x="center",
            anchor_y="center"
        )

        self.menu_button = (SCREEN_WIDTH // 2 + 130, button_y, button_width, button_height)
        arcade.draw_rect_filled(
            arcade.rect.XYWH(self.menu_button[0], self.menu_button[1],
            self.menu_button[2], self.menu_button[3]),
            arcade.color.GRAY
        )
        arcade.draw_text(
            "В главное меню",
            self.menu_button[0], self.menu_button[1],
            arcade.color.WHITE,
            font_size=26,
            anchor_x="center",
            anchor_y="center"
        )

    def on_mouse_press(self, x, y, button, modifiers):
        """Обработка кликов мыши по кнопкам UI"""
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        
        # Обработка кликов на экране победы
        if self.level_completed:
            if hasattr(self, 'restart_button'):
                rx, ry, rw, rh = self.restart_button
                if (rx - rw/2 <= x <= rx + rw/2 and 
                    ry - rh/2 <= y <= ry + rh/2):
                    self._restart_level()
                    return
            
            if self.level < 5 and hasattr(self, 'next_button'):
                nx, ny, nw, nh = self.next_button
                if (nx - nw/2 <= x <= nx + nw/2 and 
                    ny - nh/2 <= y <= ny + nh/2):
                    self._next_level()
                    return
            
            if hasattr(self, 'menu_button'):
                mx, my, mw, mh = self.menu_button
                if (mx - mw/2 <= x <= mx + mw/2 and 
                    my - mh/2 <= y <= my + mh/2):
                    self._go_to_menu()
                    return
        
        # Обработка кликов на экране проигрыша
        elif self.level_failed:
            if hasattr(self, 'restart_button'):
                rx, ry, rw, rh = self.restart_button
                if (rx - rw/2 <= x <= rx + rw/2 and 
                    ry - rh/2 <= y <= ry + rh/2):
                    self._restart_level()
                    return
            
            if hasattr(self, 'menu_button'):
                mx, my, mw, mh = self.menu_button
                if (mx - mw/2 <= x <= mx + mw/2 and 
                    my - mh/2 <= y <= my + mh/2):
                    self._go_to_menu()
                    return

    def _restart_level(self):
        """Перезапуск текущего уровня"""
        self.setup(self.level, self.unlocked_levels)

    def _next_level(self):
        """Переход к следующему уровню"""
        next_level = self.level + 1 if self.level != 5 else 5
        next_unlocked_levels = max(self.unlocked_levels, next_level)
        game_view = GameView()
        game_view.setup(next_level, next_unlocked_levels)
        self.window.show_view(game_view)

    def _go_to_menu(self):
        """Возврат в главное меню"""
        if self.level_completed:
            # При возврате из победы обновляем количество открытых уровней
            next_level = self.level + 1 if self.level != 5 else 5
            next_unlocked_levels = max(self.unlocked_levels, next_level)
            self.cur.execute(f"UPDATE levels SET LevelsOpened = {next_unlocked_levels}")
            self.con.commit()
            menu_view = MenuView()
            menu_view.setup(next_unlocked_levels)
            self.window.show_view(menu_view)
        else:
            # При возврате из проигрыша сохраняем текущий прогресс
            menu_view = MenuView()
            menu_view.setup(self.unlocked_levels)
            self.window.show_view(menu_view)

    def on_update(self, delta_time):
        """Обновление игровой логики каждый кадр"""
        if not self.level_completed and not self.level_failed:
            # Обновление состояния автомобиля
            self.player_sprite.update()
            
            # Ограничение движения в пределах карты
            if self.player_sprite.right > 640 + self.offset_x:
                self.player_sprite.right = 640 + self.offset_x
            if self.player_sprite.left < self.offset_x:
                self.player_sprite.left = self.offset_x
            if self.player_sprite.bottom < self.offset_y:
                self.player_sprite.bottom = self.offset_y
            if self.player_sprite.top > 640 + self.offset_y:
                self.player_sprite.top = 640 + self.offset_y
            
            # Обновление физического движка
            self.physics_engine.update()
            
            # Проверка столкновений с другими машинами
            colliding_with_cars = arcade.check_for_collision_with_list(self.player_sprite, self.cars)
            if len(colliding_with_cars) > 0:
                if not CHEAT_MODE:
                    self.level_failed = True
                    if self.music_player:
                        self.music.stop(self.music_player)
                    # Проигрываем звук проигрыша
                    gameover_sound = arcade.Sound('assets/sounds/gameover.mp3')
                    gameover_sound.play(volume=0.5)
                else:
                    print('player died')

            # Проверка успешной парковки (нахождение в границах парковочного места)
            if (self.player_sprite.left > self.parking_borders[0] + self.offset_x
                and self.player_sprite.bottom > self.parking_borders[1] + self.offset_y
                and self.player_sprite.right < self.parking_borders[2] + self.offset_x
                and self.player_sprite.top < self.parking_borders[3] + self.offset_y):
                self.level_completed = True
                if self.music_player:
                    self.music.stop(self.music_player)
                self.particle_system.emit_confetti(
                    self.player_sprite.center_x,
                    self.player_sprite.center_y,
                    count=100 if self.level == 5 else 50
                )
                # Проигрываем звук победы
                win_sound = arcade.Sound('assets/sounds/win.mp3')
                win_sound.play(volume=0.5)

            # Применение ускорения при удержании клавиш движения
            if self.moving_forward:
                self.player_sprite.speed += ACCELERATION_RATE
            elif self.moving_backward:
                self.player_sprite.speed -= ACCELERATION_RATE

        if self.particle_system:
            self.particle_system.update()

    def on_key_press(self, key, modifiers):
        """Обработка нажатий клавиш управления"""
        if not self.level_completed and not self.level_failed:
            if key == arcade.key.W or key == arcade.key.UP:
                self.moving_forward = True
            elif key == arcade.key.S or key == arcade.key.DOWN:
                self.moving_backward = True
            elif key == arcade.key.A or key == arcade.key.LEFT:
                self.player_sprite.angle_speed = -TURN_SPEED
            elif key == arcade.key.D or key == arcade.key.RIGHT:
                self.player_sprite.angle_speed = TURN_SPEED

    def on_key_release(self, key, modifiers):
        """Обработка отпускания клавиш управления"""
        if not self.level_completed and not self.level_failed:
            if key == arcade.key.W or key == arcade.key.UP:
                self.moving_forward = False
            elif key == arcade.key.S or key == arcade.key.DOWN:
                self.moving_backward = False
            if key == arcade.key.A or key == arcade.key.D or key == arcade.key.LEFT or key == arcade.key.RIGHT:
                self.player_sprite.angle_speed = 0

    def on_hide_view(self):
        """Остановка музыки при скрытии игрового экрана"""
        if self.music_player:
            self.music.stop(self.music_player)


def main():
    """Основная функция инициализации игры"""
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    menu_view = MenuView()
    menu_view.setup()
    window.show_view(menu_view)
    arcade.run()


if __name__ == "__main__":
    main()
