from udp_receiver import UDPReceiver
from data_processor import DataProcessor
from vibration_ctrl import VibrationController
import time

def main():
    # 初始化模块
    vib_ctrl = VibrationController()
    udp_receiver = UDPReceiver()
    data_processor = DataProcessor(vib_ctrl)
    
    try:
        udp_receiver.start()
        data_processor.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        udp_receiver.stop()
        data_processor.stop()
        vib_ctrl.stop()

if __name__ == "__main__":
    main()