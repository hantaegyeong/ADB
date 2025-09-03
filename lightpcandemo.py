import can
import time
import sys

CHANNEL = 'PCAN_USBBUS1'
BITRATE = 500000
CAN_INTERFACE = 'pcan'

MESSAGE_ID = 0x541
DLC = 8

DATA_AWAKE_LIGHTS_OFF = [0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
DATA_AWAKE_LIGHTS_ON = [0x02, 0x00, 0x00, 0x80, 0x00, 0x00, 0x00, 0x00]

CYCLE_TIME_SECONDS = 0.1

def main():
    bus = None
    try:
        print(f"Initializing PCAN bus on channel '{CHANNEL}' at {BITRATE}bps...")
        bus = can.interface.Bus(
            channel=CHANNEL,
            bustype=CAN_INTERFACE,
            bitrate=BITRATE
        )
        print("PCAN bus initialized successfully.")
    except Exception as e:
        print(f"Error initializing PCAN bus: {e}")
        print("Please check the following:")
        print("1. Have you installed the PCAN-Basic driver from PEAK-System?")
        print(f"2. Is the PCAN adapter connected and is the channel name '{CHANNEL}' correct?")
        sys.exit(1)

    lights_on = False
    
    print("\n" + "="*40)
    print("Headlamp Control Script (PCAN Version) Started.")
    print("Press ENTER to toggle the headlights.")
    print("="*40 + "\n")

    try:
        while True:
            if lights_on:
                data_to_send = DATA_AWAKE_LIGHTS_ON
                status_text = "ON"
            else:
                data_to_send = DATA_AWAKE_LIGHTS_OFF
                status_text = "OFF"

            message = can.Message(
                arbitration_id=MESSAGE_ID,
                data=data_to_send,
                is_extended_id=False,
                dlc=DLC
            )

            print(f"Headlight Status: {status_text}. Press ENTER")
            
            timeout = time.time() + 1.0
            while time.time() < timeout:
                bus.send(message)
                time.sleep(CYCLE_TIME_SECONDS)

            input()
            
            lights_on = not lights_on

    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
    finally:
        if bus:
            bus.shutdown()
            print("PCAN bus shut down.")

if __name__ == "__main__":
    main()
