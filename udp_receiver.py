import socket
from threading import Thread
from shared_data import TelemetryData
import logging

class UDPReceiver:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 50050))
        self.sock.settimeout(0.1)
        self.running = False
        self.thread = None
        
    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                # 打印接收数据，检查是否正确接收udp数据
                # print(data) 
                TelemetryData.update(data.decode())
                # 打印TelemetryData._data,里面是把接收数据规整成键值对的字典文件
                # print(TelemetryData._data)
            except socket.timeout:
                pass
            except Exception as e:
                logging.error(f"UDP接收错误: {str(e)}")

    def start(self):
        self.running = True
        self.thread = Thread(target=self._recv_loop)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()
        self.sock.close()