from project1.client import Client

if __name__ == '__main__':
    with Client(student_id=592) as client:
        client.start()
