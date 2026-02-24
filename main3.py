import random
import logging
from htag import Tag, ChromeApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sudoku")

class SudokuLogic:
    @staticmethod
    def is_valid(grid, r, c, n):
        for i in range(9):
            if grid[r][i] == n or grid[i][c] == n:
                return False
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                if grid[i][j] == n:
                    return False
        return True

    @staticmethod
    def solve(grid):
        for r in range(9):
            for c in range(9):
                if grid[r][c] == 0:
                    nums = list(range(1, 10))
                    random.shuffle(nums)
                    for n in nums:
                        if SudokuLogic.is_valid(grid, r, c, n):
                            grid[r][c] = n
                            if SudokuLogic.solve(grid):
                                return True
                            grid[r][c] = 0
                    return False
        return True

    @staticmethod
    def generate(difficulty=40):
        grid = [[0 for _ in range(9)] for _ in range(9)]
        SudokuLogic.solve(grid)
        puzzle = [row[:] for row in grid]
        for _ in range(difficulty):
            r, c = random.randint(0, 8), random.randint(0, 8)
            while puzzle[r][c] == 0:
                r, c = random.randint(0, 8), random.randint(0, 8)
            puzzle[r][c] = 0
        return grid, puzzle

class Sudoku(Tag.App):
    statics = [
        Tag.link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap"),
        Tag.style("""
            :root {
                --bg: #0b0e14;
                --card-bg: rgba(255, 255, 255, 0.03);
                --accent: #00d2ff;
                --accent-glow: rgba(0, 210, 255, 0.3);
                --error: #ff4d4d;
                --text: #e2e8f0;
                --text-muted: #94a3b8;
                --glass-border: rgba(255, 255, 255, 0.1);
            }
            body { 
                font-family: 'Outfit', sans-serif; 
                background: radial-gradient(circle at top right, #1e293b, var(--bg)); 
                color: var(--text); 
                margin: 0; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                min-height: 100vh;
                overflow: hidden;
            }
            .container { 
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                gap: 30px;
                animation: fadeIn 1s ease-out;
            }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
            
            h1 { font-weight: 300; letter-spacing: 4px; text-transform: uppercase; margin: 0; font-size: 2rem; color: var(--accent); text-shadow: 0 0 20px var(--accent-glow); }
            
            .board { 
                display: grid; 
                grid-template-columns: repeat(9, 50px); 
                gap: 1px; 
                background: var(--glass-border); 
                border: 2px solid var(--glass-border); 
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                overflow: hidden;
            }
            .cell { 
                width: 50px; height: 50px; 
                background: var(--card-bg); 
                display: flex; align-items: center; justify-content: center; 
                font-size: 1.2rem; cursor: pointer; user-select: none;
                transition: all 0.2s;
            }
            .cell:hover { background: rgba(255, 255, 255, 0.08); }
            .cell.selected { background: var(--accent-glow); box-shadow: inset 0 0 10px var(--accent); }
            .cell.fixed { font-weight: 600; color: var(--text-muted); cursor: default; }
            .cell.fixed:hover { background: var(--card-bg); }
            .cell.error { color: var(--error); text-shadow: 0 0 5px var(--error); }
            
            /* Subgrid borders */
            .cell:nth-child(3n) { border-right: 2px solid var(--glass-border); }
            .cell:nth-child(9n) { border-right: none; }
            div.board > div:nth-child(n+19):nth-child(-n+27),
            div.board > div:nth-child(n+46):nth-child(-n+54) { border-bottom: 2px solid var(--glass-border); }

            .controls { display: flex; gap: 10px; margin-top: 20px; }
            .btn { 
                background: var(--card-bg); border: 1px solid var(--glass-border); color: var(--text);
                padding: 10px 20px; border-radius: 8px; cursor: pointer; font-family: inherit; font-weight: 600;
                transition: all 0.2s; backdrop-filter: blur(5px);
            }
            .btn:hover { background: rgba(255, 255, 255, 0.1); border-color: var(--accent); color: var(--accent); }
            
            .numpad { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 20px; }
            .num-btn { 
                width: 45px; height: 45px; background: var(--card-bg); border: 1px solid var(--glass-border);
                border-radius: 8px; color: var(--text); cursor: pointer; font-size: 1.1rem;
                transition: all 0.2s;
            }
            .num-btn:hover { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
            
            .status { font-size: 0.9rem; color: var(--text-muted); height: 20px; }
        """)
    ]

    def init(self):
        self.selected = None
        self.new_game()

        container = Tag.div(_class="container")
        self += container
        
        container += Tag.h1("Sudoku Gravity")
        self.status = Tag.div(_class="status")
        container += self.status
        
        self.board_tag = Tag.div(_class="board")
        container += self.board_tag
        
        self.render_board()
        
        numpad = Tag.div(_class="numpad")
        container += numpad
        for i in range(1, 10):
            numpad += Tag.button(str(i), _class="num-btn", _onclick=lambda e, n=i: self.input_num(n))
        numpad += Tag.button("C", _class="num-btn", _onclick=lambda e: self.input_num(0))
        
        controls = Tag.div(_class="controls")
        container += controls
        controls += Tag.button("NEW GAME", _class="btn", _onclick=lambda e: self.new_game_and_render())

    def new_game(self):
        self.solution, self.grid = SudokuLogic.generate(45)
        self.fixed = [[col != 0 for col in row] for row in self.grid]
        self.selected = None

    def new_game_and_render(self):
        self.new_game()
        self.status.clear()
        self.render_board()

    def render_board(self):
        self.board_tag.clear()
        for r in range(9):
            for c in range(9):
                val = self.grid[r][c]
                is_fixed = self.fixed[r][c]
                
                cls = ["cell"]
                if is_fixed: cls.append("fixed")
                if self.selected == (r, c): cls.append("selected")
                
                # Check for errors (if not 0 and doesn't match solution)
                if val != 0 and val != self.solution[r][c]:
                    cls.append("error")
                
                cell = Tag.div(str(val) if val != 0 else "", 
                              _class=" ".join(cls),
                              _onclick=lambda e, r=r, c=c: self.select_cell(r, c))
                self.board_tag += cell

    def select_cell(self, r, c):
        if not self.fixed[r][c]:
            self.selected = (r, c)
            self.render_board()

    def input_num(self, n):
        if self.selected:
            r, c = self.selected
            self.grid[r][c] = n
            self.render_board()
            
            # Check for win
            if all(self.grid[r][c] == self.solution[r][c] for r in range(9) for c in range(9)):
                self.status += "CONGRATULATIONS! GRAVITY DEFIED."
                self.selected = None
                self.render_board()

if __name__ == "__main__":
    ChromeApp(Sudoku, width=600, height=850).run()
