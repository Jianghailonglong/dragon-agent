"""游戏逻辑 - 状态管理、计分、UI"""

import json
import os
import pygame
from settings import (
    WINDOW_WIDTH, WINDOW_HEIGHT, CELL_SIZE,
    GRID_WIDTH, GRID_HEIGHT,
    BLACK, WHITE, GRAY, DARK_GRAY, GREEN, RED, GOLD, BLUE, SCORE_BG,
    INITIAL_SPEED, MIN_SPEED, SPEED_INCREMENT,
    STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER,
    HIGHSCORE_FILE, UP, DOWN, LEFT, RIGHT
)
from snake import Snake
from food import Food


class Game:
    def __init__(self):
        """初始化游戏"""
        pygame.init()
        pygame.display.set_caption("贪吃蛇 🐍")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        # 尝试加载中文字体
        chinese_fonts = ["SimHei", "Microsoft YaHei", "FangSong", "KaiTi", "Arial"]
        font_name = None
        available_fonts = pygame.font.get_fonts()
        for f in chinese_fonts:
            if f.lower().replace(" ", "") in available_fonts:
                font_name = f
                break
        if font_name is None:
            font_name = "arial"

        self.font_large = pygame.font.SysFont(font_name, 48, bold=True)
        self.font_medium = pygame.font.SysFont(font_name, 28)
        self.font_small = pygame.font.SysFont(font_name, 20)

        self.snake = Snake()
        self.food = Food()
        self.state = STATE_MENU
        self.score = 0
        self.highscore = self.load_highscore()
        self.speed = INITIAL_SPEED
        self.move_timer = 0
        self.running = True

        # 首次生成食物
        self.food.spawn(self.snake.body)

    def load_highscore(self):
        """加载最高分"""
        try:
            if os.path.exists(HIGHSCORE_FILE):
                with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("highscore", 0)
        except Exception:
            pass
        return 0

    def save_highscore(self):
        """保存最高分"""
        try:
            with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
                json.dump({"highscore": self.highscore}, f, ensure_ascii=False)
        except Exception:
            pass

    def handle_events(self):
        """处理输入事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                if self.state == STATE_MENU:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.start_game()

                elif self.state == STATE_PLAYING:
                    # 方向控制
                    if event.key == pygame.K_UP or event.key == pygame.K_w:
                        self.snake.set_direction(UP)
                    elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                        self.snake.set_direction(DOWN)
                    elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                        self.snake.set_direction(LEFT)
                    elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                        self.snake.set_direction(RIGHT)
                    # 暂停
                    elif event.key == pygame.K_SPACE:
                        self.state = STATE_PAUSED

                elif self.state == STATE_PAUSED:
                    if event.key == pygame.K_SPACE:
                        self.state = STATE_PLAYING

                elif self.state == STATE_GAMEOVER:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.start_game()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = STATE_MENU

    def start_game(self):
        """开始新游戏"""
        self.snake.reset()
        self.food.spawn(self.snake.body)
        self.score = 0
        self.speed = INITIAL_SPEED
        self.move_timer = 0
        self.state = STATE_PLAYING

    def update(self, dt):
        """更新游戏状态"""
        if self.state != STATE_PLAYING:
            return

        self.move_timer += dt
        if self.move_timer >= self.speed:
            self.move_timer = 0

            # 移动蛇
            if not self.snake.move():
                self.game_over()
                return

            # 检查是否吃到食物
            if self.snake.get_head() == self.food.position:
                self.snake.grow()
                self.score += self.food.get_score()
                self.food.spawn(self.snake.body)
                # 加速
                self.speed = max(MIN_SPEED, self.speed - SPEED_INCREMENT)

    def game_over(self):
        """游戏结束"""
        self.state = STATE_GAMEOVER
        if self.score > self.highscore:
            self.highscore = self.score
            self.save_highscore()

    def draw(self):
        """绘制所有内容"""
        self.screen.fill(BLACK)

        if self.state == STATE_MENU:
            self.draw_menu()
        elif self.state in (STATE_PLAYING, STATE_PAUSED):
            self.draw_game()
            self.draw_score_bar()
            if self.state == STATE_PAUSED:
                self.draw_pause_overlay()
        elif self.state == STATE_GAMEOVER:
            self.draw_game()
            self.draw_score_bar()
            self.draw_gameover_overlay()

        pygame.display.flip()

    def draw_menu(self):
        """绘制主菜单"""
        # 标题
        title = self.font_large.render("贪吃蛇", True, GREEN)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3))
        self.screen.blit(title, title_rect)

        # 蛇的图案装饰
        snake_icon = self.font_large.render("🐍", True, WHITE)
        icon_rect = snake_icon.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3 - 60))
        self.screen.blit(snake_icon, icon_rect)

        # 开始提示
        start_text = self.font_medium.render("按 空格键 或 回车 开始游戏", True, WHITE)
        start_rect = start_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(start_text, start_rect)

        # 操作说明
        instructions = [
            "方向键 / WASD  控制方向",
            "空格键  暂停游戏",
            "ESC  返回菜单"
        ]
        for i, text in enumerate(instructions):
            inst = self.font_small.render(text, True, GRAY)
            inst_rect = inst.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60 + i * 30))
            self.screen.blit(inst, inst_rect)

        # 最高分
        if self.highscore > 0:
            hs_text = self.font_small.render(f"最高分: {self.highscore}", True, GOLD)
            hs_rect = hs_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 60))
            self.screen.blit(hs_text, hs_rect)

    def draw_game(self):
        """绘制游戏画面"""
        # 绘制网格背景
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + 60, CELL_SIZE, CELL_SIZE)
                color = DARK_GRAY if (x + y) % 2 == 0 else GRAY
                pygame.draw.rect(self.screen, color, rect)

        # 绘制食物和蛇
        self.food.draw(self.screen)
        self.snake.draw(self.screen)

        # 绘制边框
        game_rect = pygame.Rect(0, 60, GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE)
        pygame.draw.rect(self.screen, WHITE, game_rect, 2)

    def draw_score_bar(self):
        """绘制分数栏"""
        bar_rect = pygame.Rect(0, 0, WINDOW_WIDTH, 58)
        pygame.draw.rect(self.screen, SCORE_BG, bar_rect)
        pygame.draw.line(self.screen, WHITE, (0, 58), (WINDOW_WIDTH, 58), 2)

        # 当前分数
        score_text = self.font_medium.render(f"分数: {self.score}", True, WHITE)
        self.screen.blit(score_text, (20, 14))

        # 最高分
        hs_text = self.font_medium.render(f"最高: {self.highscore}", True, GOLD)
        hs_rect = hs_text.get_rect(right=WINDOW_WIDTH - 20, top=14)
        self.screen.blit(hs_text, hs_rect)

    def draw_pause_overlay(self):
        """绘制暂停覆盖层"""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        pause_text = self.font_large.render("暂停", True, WHITE)
        pause_rect = pause_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20))
        self.screen.blit(pause_text, pause_rect)

        hint = self.font_medium.render("按空格键继续", True, GRAY)
        hint_rect = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 40))
        self.screen.blit(hint, hint_rect)

    def draw_gameover_overlay(self):
        """绘制游戏结束覆盖层"""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # 游戏结束文字
        go_text = self.font_large.render("游戏结束", True, RED)
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 60))
        self.screen.blit(go_text, go_rect)

        # 最终分数
        final = self.font_medium.render(f"最终得分: {self.score}", True, WHITE)
        final_rect = final.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(final, final_rect)

        # 新纪录提示
        if self.score >= self.highscore and self.score > 0:
            new_record = self.font_medium.render("🎉 新纪录！", True, GOLD)
            nr_rect = new_record.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 40))
            self.screen.blit(new_record, nr_rect)

        # 重新开始提示
        restart = self.font_small.render("按 空格键 重新开始 | ESC 返回菜单", True, GRAY)
        restart_rect = restart.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 90))
        self.screen.blit(restart, restart_rect)

    def run(self):
        """游戏主循环"""
        while self.running:
            dt = self.clock.tick(60)  # 毫秒
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
