from app.services.knowledge import RetrievalService

if __name__ == "__main__":
    stats = RetrievalService().refresh()
    print(stats)
