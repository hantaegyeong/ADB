import can
import time
import random
import serial
import sqlite3

def setup_database(db_name="sent_data.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_payloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload BLOB NOT NULL UNIQUE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn, cursor

def main():
    bus = None
    db_conn = None
    com_port = 'COM14'

    try:
        db_conn, cursor = setup_database()
        print("데이터베이스 'sent_data.db'에 연결되었습니다.")

        bus = can.interface.Bus(
            interface='slcan',
            channel=com_port,
            fd=True,
            bitrate=500000,
            data_bitrate=2000000
        )
        print(f"CAN 버스가 {com_port}에서 CAN FD 모드로 초기화되었습니다.")
        print("DLC=15 고정, 중복되지 않는 랜덤 데이터를 전송합니다. (Ctrl+C로 중지)")

        while True:
            unique_data_found = False
            random_data_list = None
            
            while not unique_data_found:
                data_list = [random.randint(0, 255) for _ in range(64)]
                data_blob = bytes(data_list)

                try:
                    cursor.execute("INSERT INTO sent_payloads (payload) VALUES (?)", (data_blob,))
                    db_conn.commit()
                    
                    random_data_list = data_list
                    unique_data_found = True

                except sqlite3.IntegrityError:
                    time.sleep(0.01)

            random_id = random.randint(0x000, 0x7FF)
            dlc = 15

            msg = can.Message(
                arbitration_id=random_id,
                is_extended_id=False,
                is_fd=True,
                dlc=dlc,
                data=random_data_list
            )

            try:
                bus.send(msg)
                hex_data = ' '.join(f'{byte:02X}' for byte in msg.data)
                print(f"ID: {msg.arbitration_id:03X} DATA: {hex_data} (전송 성공)")
            except can.CanError as e:
                print(f"메시지 전송 실패: {e}")

            time.sleep(0.1)

    except (can.CanError, serial.SerialException) as e:
        print(f"CAN 버스 초기화 실패: {e}")
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중지되었습니다.")
    finally:
        if bus:
            bus.shutdown()
            print("CAN 버스가 종료되었습니다.")
        if db_conn:
            db_conn.close()
            print("데이터베이스 연결이 종료되었습니다.")

if __name__ == "__main__":
    main()
