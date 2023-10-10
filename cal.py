import socket
import threading
import time
import json
import re
from datetime import datetime
from queue import Queue
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QIcon
from cal_ui import Ui_MainWindow

UDP_IP = '127.0.0.1'
UDP_PORT = 12345
TIMEOUT  = 3    #connection
OP_TIMEOUT = 5  #operation
Max_CPU = 5 + 1

class MyWindow(QMainWindow, Ui_MainWindow):
    updateWaitingListSignal = pyqtSignal(str,str)
    def __init__(self):
        super().__init__()
        self.setupUi(self)  #initalize the ui from cal_ui.py
        
        self.connection_timer = QTimer(self)    #create a timer to check connection status
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(100)
        
        self.connection_timer = QTimer(self)    #create a timer to check timeout
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(50)
        
        self.send_requestQueue = Queue() #a queue for sending request to the server
        self.server_connected = False   #initalize a flag to track whether the server is connected
        self.last_ping_time = 0 #initalize a timestamp to track to last received "ping" msg
        
        #Define instance attributes for user inputs
        self.num1 = ""
        self.num2 = ""
        self.operation = ""
        
        self.ID = 0     #Define ID number to identify each operation
        self.request_time = 0   #Request timestamp
        self.Waitlist_check = []    #create a list to store ID in waiting list
        
        #Thread for socket operation
        self.socket_thread = threading.Thread(target=self.start_socket_thread)
        self.socket_thread.daemon = True
        self.socket_thread.start()
        
        #Thread to handle request concurrently
        self.request_thread = threading.Thread(target=self.handle_request)
        self.request_thread.daemon = True
        self.request_thread.start()
        
        #Connect click event to handle
        self.calculate_button.clicked.connect(self.calculate_button_clicked)
        self.clear_button.clicked.connect(lambda: self.History_tableWidget.setRowCount(0))
        self.updateWaitingListSignal.connect(self.update_waiting_list)
        
    def start_socket_thread(self):
        try:
            client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            client_socket.bind(('0.0.0.0', UDP_PORT))   #Bind th client socket to listen for response
            while(1):
                data, adr = client_socket.recvfrom(1024)
                if data == b'Ping':
                    self.server_connected = True
                    self.last_ping_time = time.time()
                else:
                    self.handle_response(data)
                    self.server_connected = True
                    self.last_ping_time = time.time()
        except socket.error as e:
            print(e)
            pass
        
    def handle_response(self, data):
        response_dict =json.loads(data.decode())
        ID_receive = response_dict["ID"]
        status = response_dict["status"]
        
        #Iterate through the IDs in waitlist check
        for ID in self.Waitlist_check:
            if ID == ID_receive:
                if status == "Busy":
                    row_position = self.Waitlist_check.index(ID)
                    self.WaitList_tableWidget.setItem(row_position, 1, QTableWidgetItem("Busy"))
                    print("Busy")
                else:
                    operation, request_time = self.remove_waiting_list(ID, "Done")
                    self.update_history_table(data, operation, request_time)
                    self.change_status()
            else:
                self.change_status()
    def change_status(self):
        for row in range(self.WaitList_tableWidget.rowCount()):
            if row < 3:
                status = self.WaitList_tableWidget.item(row,1)
                status = status.text()
                if status == "Busy":
                    self.WaitList_tableWidget.setItem(row, 1, QTableWidgetItem("Peding"))
                    op = self.WaitList_tableWidget.item(row,0)
                    full_op = op.text()
                    res = re.split(r'(\D)', full_op)
                    num1 = res[0]
                    my_operation = res[1]
                    num2 = res[2]
                    request_time = datetime.now().strftime("%H:%M:%S.%f")[:-4]
                    ID = self.Waitlist_check[row]
                    self.WaitList_tableWidget.setItem(row, 2, QTableWidgetItem(request_time))
                    json_payload = self.format_json(num1, num2, my_operation, ID, request_time)
                    self.updateWaitingListSignal.emit("Resend", json_payload)
                    
    def handle_request(self):
        while (1):
            if not self.send_requestQueue.empty():
                json_payload = self.send_requestQueue.get()
                self.send_request(json_payload)
            else:
                time.sleep(0.1)
        
    def check_connection(self):
        if time.time() - self.last_ping_time > TIMEOUT:
            self.server_connected = False
        if self.server_connected:
            self.ConnectionStatus_label.setText("Connected!!")
            self.ConnectionStatus_label.setStyleSheet("color: green;")
        else: 
            self.ConnectionStatus_label.setText("Disconnected!!")
            self.ConnectionStatus_label.setStyleSheet("color: red;")  

    def calculate_button_clicked(self):
        self.get_user_inputs()
        status = "Pending..."
        id_number = self.ID
        
        self.request_time = datetime.now().strftime("%H:%M:%S.%f")[:-4]
        json_payload = self.format_json(self.num1, self.num2, self.operation, self.ID, self.request_time)
        self.ID +=1
        self.updateWaitingListSignal.emit("Pending", json_payload)
    
    def create_request(self, json_payload):
            if self.server_connected:
                self.send_requestQueue.put(json_payload)
            else:
                # Handle the button click when disconnected
                print("Button clicked while disconnected")

    def check_timeouts(self):
        # Iterate through the waiting list and check for timeouts
        for row in range(self.WaitList_tableWidget.rowCount()):
            item = self.WaitList_tableWidget.item(row, 2)  # Get the timestamp item
            status = self.WaitList_tableWidget.item(row, 1)
            if status is not None:
                status = status.text()
                if status == "Pending":
                    timestamp_str = item.text()
                    timestamp_time = datetime.strptime(timestamp_str, '%H:%M:%S.%f').time()
                    ID = self.Waitlist_check[row]
                    # Get the current date and time
                    current_datetime = datetime.now()
                    current_time = current_datetime.time()
                    try:
                        elapsed_time = (datetime.combine(current_datetime.date(), current_time)
                                        - datetime.combine(current_datetime.date(), timestamp_time)).total_seconds()
                    except Exception as e:
                        print(e)
                    # print(elapsed_time)
                    if elapsed_time >= OP_TIMEOUT:
                        # Operation has timed out
                        operation, request_time = self.remove_waiting_list(ID, "Done")
                        timedOut_response = {
                            "timestamp": "-",  # You can set this to an appropriate timestamp
                            "result": "",
                            "status": "Timed out",
                            "ID": row
                        }
                        timedOut_response_payload = json.dumps(timedOut_response)
                        # Update the history table with the timed out status
                        self.update_history_table(timedOut_response_payload, operation, request_time)

    def disconnect_state(self):
        # Iterate through the IDs in Waitlist_check
        for ID in self.Waitlist_check:
            # Remove the corresponding row from the waitlist and get the request time
            operation, request_time = self.remove_waiting_list(ID, "Done")
            # Create a dummy response payload for disconnected status
            fail_time = datetime.now().strftime('%H:%M:%S.%f')[:-4]
            failed_response = {
                "timestamp": fail_time,  # You can set this to an appropriate timestamp
                "result": "",
                "status": "Failed",
                "ID": ID
            }
            failed_response_payload = json.dumps(failed_response)
            # Update the history table with the disconnected status
            self.update_history_table(failed_response_payload, operation, request_time)

    def get_user_inputs(self):
        # Get user inputs
        self.num1 = self.Opr1_lineEdit.text()
        self.num2 = self.Opr2_lineEdit.text()
        self.operation = self.Operation_comboBox.currentText()

    def update_waiting_list(self, status, json_payload):
        # Extract operation and ID_number from json_payload
        payload_data = json.loads(json_payload)
        num1 = payload_data["data"][0]
        num2 = payload_data["data"][1]
        operation = payload_data["data"][2]
        ID_number = payload_data["ID"]
        request_time = payload_data["timestamp"]
        if status == "Resend":
            row_position =  self.Waitlist_check.index(ID_number)
            self.WaitList_tableWidget.setItem(row_position, 1, QTableWidgetItem("Pending"))
            self.WaitList_tableWidget.setItem(row_position, 2, QTableWidgetItem(request_time))
            self.create_request(json_payload)
            QApplication.processEvents()
        else:
            # Add the ID to the Waitlist_check array
            self.Waitlist_check.append(ID_number)
            # Add the extracted information to the waiting list
            row_position = self.WaitList_tableWidget.rowCount()
            self.WaitList_tableWidget.insertRow(row_position)
            self.WaitList_tableWidget.setItem(row_position, 0, QTableWidgetItem(num1 + operation + num2))
            if len(self.Waitlist_check) < Max_CPU:
                self.WaitList_tableWidget.setItem(row_position, 1, QTableWidgetItem("Pending"))
                self.WaitList_tableWidget.setItem(row_position, 2, QTableWidgetItem(request_time))
                QApplication.processEvents()
                self.create_request(json_payload)
            else:
                status_item = QTableWidgetItem("Busy")
                self.WaitList_tableWidget.setItem(row_position, 1, status_item)
                self.WaitList_tableWidget.setItem(row_position, 2, QTableWidgetItem(request_time))
                status_item.setForeground(QColor("red"))
                QApplication.processEvents()
        

    def remove_waiting_list(self, ID, status):
        # Find the position of the ID in the Waitlist_check array
        row_position = self.Waitlist_check.index(ID)
        # Get the value in the third column of the removed row
        rq_time = self.WaitList_tableWidget.item(row_position, 2)
        rqtime_value = rq_time.text() if rq_time else None
        op = self.WaitList_tableWidget.item(row_position, 0)
        operation_value = op.text() if op else None
        # Remove the corresponding row from the waitlist
        self.WaitList_tableWidget.removeRow(row_position)
        # Remove the ID from the Waitlist_check array
        self.Waitlist_check.pop(row_position)
        # Return the value from the removed row
        return operation_value, rqtime_value


    def update_history_table(self, response_payload, operation, request_time):
        try:
            data = json.loads(response_payload)
            response_time = data["timestamp"]
            result = data["result"]
            status = data["status"]
            if result == "Invalid Input":
                result = ""
                status = "Invalid!"
            # Update the "History" table immediately
            row_position = self.History_tableWidget.rowCount()
            self.History_tableWidget.insertRow(row_position)
            self.History_tableWidget.setItem(row_position, 0, QTableWidgetItem(request_time))
            self.History_tableWidget.setItem(row_position, 1, QTableWidgetItem(response_time))
            self.History_tableWidget.setItem(row_position, 2, QTableWidgetItem(operation))
            status_item = QTableWidgetItem(status)
            if status == "Done":
                status_item.setForeground(QColor("green"))
            else:
                status_item.setForeground(QColor("red"))
            self.History_tableWidget.setItem(row_position, 3, status_item)
            self.History_tableWidget.setItem(row_position, 4, QTableWidgetItem(str(result)))
        except (ValueError, KeyError):
            # Handle JSON parsing errors or missing keys
            pass

    def format_json(self, num1, num2, operation, ID_number, request_time):
        # Create a JSON payload
        payload = {"timestamp": request_time, "ID": ID_number, "data": []}
        data_payload = payload["data"]
        data_payload.append(num1)
        data_payload.append(num2)
        data_payload.append(operation)
        json_payload = json.dumps(payload)
        return json_payload

    def send_request(self, json_payload):
        # Define the server's IP address and port
        server_ip = '127.0.0.1'
        server_port = 54321
        try:
            # Create a UDP socket
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Send the JSON payload to the server
            client_socket.sendto(json_payload.encode(), (server_ip, server_port))
            print("[DEBUG] send payload {}".format(json_payload))
            client_socket.close()
        except Exception as e:
            # Handle any exceptions that may occur during the send process
            print("Error sending request to server:", str(e))

if __name__ == "__main__":
    app = QApplication([])
    icon = QIcon('hic.jpg')
    # Set the application icon
    app.setWindowIcon(icon)
    window = MyWindow()
    window.show()
    app.exec()
