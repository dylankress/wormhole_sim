class SimClock:
    def __init__(self):
        self.tick = 0

    def advance(self):
        self.tick += 1

    def current(self):
        return self.tick