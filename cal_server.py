import socket
import json
import threading
import time
import random
from datetime import datetime
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication  # Import QApplication

app = QApplication([])  # Create a QApplication instance

UDP_IP = '127.0.0.1'  # Server IP address (change to your desired IP)
UDP_PORT = 12345  # Server port (change to your desired port)
MAX_CONCURRENT_OPERATIONS = 3

class PingThread(QThread):
    def run(self):
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            send_socket.sendto(b'Ping', (UDP_IP, UDP_PORT))
            time.sleep(1)
            
class Worker(QObject):
    update_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.connected = True  # Initially, assume the server is connected
        self.concurrent_operations = 0

    def perform_calculation(self, num1, num2, operation):
        try:
            num1 = float(num1)
            num2 = float(num2)
            if operation == "+":
                result = num1 + num2
                delay = random.randint(2, 6)
                time.sleep(delay)
            elif operation == "-":
                result = num1 - num2
                delay = random.randint(2, 6)
                time.sleep(delay)
            elif operation == "*":
                result = num1 * num2
                delay = random.randint(3, 7)
                time.sleep(delay)
            elif operation == "/":
                if num2 == 0:
                    return "Invalid Input"
                result = num1 / num2
                delay = random.randint(3, 7)
                time.sleep(delay)
            else:
                return "Invalid Input"
            return result
        except ValueError:
            return "Invalid Input"

    def handle_client_request(self, data):
        try:
            payload = json.loads(data.decode())
            num1 = payload["data"][0]
            num2 = payload["data"][1]
            operation = payload["data"][2]
            ID = payload["ID"]
            # Check if the server is busy
            if self.concurrent_operations >= MAX_CONCURRENT_OPERATIONS:
                response = {
                "timestamp": "",
                "result": "",
                "status": "Busy",
                "ID": ID
                }
            else:
                # Increment the concurrent operations counter
                self.concurrent_operations += 1
                # Perform the calculation
                result = self.perform_calculation(num1, num2, operation)
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-4]
                response = {
                "timestamp": current_time,
                "result": result,
                "status": "Done",
                "ID": ID
                }
                # Decrement the concurrent operations counter
                self.concurrent_operations -= 1
            self.update_signal.emit(response)
        except Exception as e:
            print(f"Error processing client request: {str(e)}")


class Server(QThread):
    def __init__(self):
        super().__init__()
        self.worker = Worker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker.update_signal.connect(self.handle_update_signal)
        self.worker_thread.start()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((UDP_IP, 54321))

    def run(self):
        while True:
            try:
                data, client_address = self.server_socket.recvfrom(1024)
                threading.Thread(target=self.worker.handle_client_request, args=(data,)).start()
            except ConnectionResetError:
                print(f"Connection was forcibly closed by the remote host.")
                pass

    def handle_update_signal(self, response):
        print(response)
        self.server_socket.sendto(json.dumps(response).encode(), (UDP_IP, UDP_PORT))

if __name__ == '__main__':
    print("UDP Calculator Server is running...")
    server = Server()
    ping = PingThread()
    ping.start()
    server.start()
    app.exec_()