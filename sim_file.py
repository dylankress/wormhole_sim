class SimFile:
    def __init__(self, file_name: str, file_size: int, owner):
        self.file_name = file_name
        self.file_size = file_size
        self.owner = owner

    def __repr__(self):
        return f"<File Name={self.file_name}, size={self.file_size}MB, owner={self.owner.id}>"