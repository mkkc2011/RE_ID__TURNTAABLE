import time
import serial
import struct

def calculate_crc(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def open_serial_port(port, baudrate):
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=1,
        rtscts=False,
        dsrdtr=False
    )

def send_request(ser, request, response_length):
    crc = calculate_crc(request)
    request += struct.pack('<H', crc)
    ser.write(request)
    time.sleep(0.1)
    response = ser.read(response_length)
    if len(response) < response_length:
        print(f"Error: Incomplete response (expected {response_length} bytes, got {len(response)} bytes)")
        return None
    if calculate_crc(response[:-2]) != struct.unpack('<H', response[-2:])[0]:
        print("Error: CRC check failed")
        return None
    return response

def write_single_register(ser, slave_address, register_address, value):
    function_code = 0x06
    request = struct.pack('>BBHH', slave_address, function_code, register_address, value)
    response = send_request(ser, request, 8)
    if response:
        response_slave_address, response_function_code, response_register_address, response_value = struct.unpack('>BBHH', response[:6])
        if (response_slave_address == slave_address and response_function_code == function_code and
                response_register_address == register_address and response_value == value):
            print(f"Successfully wrote value {value} to register {register_address} of slave {slave_address}")
        else:
            print("Error: Response does not match the request")

def write_multiple_registers(ser, slave_address, register_address, values):
    function_code = 0x10
    quantity_of_registers = len(values)
    byte_count = 2 * quantity_of_registers
    header = struct.pack('>BBHHB', slave_address, function_code, register_address, quantity_of_registers, byte_count)
    data = b''.join(struct.pack('>H', value) for value in values)
    request = header + data
    response = send_request(ser, request, 8)
    if response:
        response_slave_address, response_function_code, response_register_address, response_quantity_of_registers = struct.unpack('>BBHH', response[:6])
        if (response_slave_address == slave_address and response_function_code == function_code and
                response_register_address == register_address and response_quantity_of_registers == quantity_of_registers):
            print(f"Successfully wrote values {values} to registers starting at {register_address} of slave {slave_address}")
        else:
            print("Error: Response does not match the request")

def read_register(ser, slave_address, register_address):
    function_code = 0x03
    request = struct.pack('>BBHH', slave_address, function_code, register_address, 1)
    response = send_request(ser, request, 7)
    if response:
        if response[1] & 0x80:
            print(f"Modbus exception response: {response[2]}")
        else:
            register_value = struct.unpack('>H', response[3:5])[0]
            print(f"Successfully read value {register_value} from register {register_address} of slave {slave_address}")
            return register_value

def angle_to_pulses(angle):
    pulses_per_rotation = 100000
    degrees_per_rotation = 360
    return int((angle / degrees_per_rotation) * pulses_per_rotation)

def split_to_registers(value):
    return value & 0xFFFF, (value >> 16) & 0xFFFF

def rotate(port, baudrate, slave_address, angle, speed, accel_deccel):
    with open_serial_port(port, baudrate) as ser:
        pulses = angle_to_pulses(angle)
        lower, upper = split_to_registers(pulses)

        write_single_register(ser, slave_address, int('0x023c', 16), 1)
        write_single_register(ser, slave_address, int('0x0528', 16), accel_deccel)
        write_multiple_registers(ser, slave_address, int('0x0578', 16), [speed, 0])
        write_multiple_registers(ser, slave_address, int('0x0604', 16), [130, 0])
        write_multiple_registers(ser, slave_address, int('0x0606', 16), [lower, upper])
        write_single_register(ser, slave_address, int('0x050e', 16), 1)

def get_current_pos(port, baudrate, slave_address):
    with open_serial_port(port, baudrate) as ser:
        start_value = read_register(ser, slave_address, int('0x0012', 16))
        time.sleep(6)
        end_value = read_register(ser, slave_address, int('0x0012', 16))
        if start_value is not None and end_value is not None:
            diff = end_value - start_value
            return diff / 8333.333333333333

def main():
    port = 'COM3'
    baudrate = 9600
    slave_address = 1

    gear_ratio = 30
    speed_scale_factor = 10

    angle = 360 * gear_ratio
    speed = 1000 * speed_scale_factor 
    accel_deccel = 3000

    rotate(port, baudrate, slave_address, angle, speed, accel_deccel)
    angle_rotated = get_current_pos(port, baudrate, slave_address)
    if angle_rotated is not None:
        print(f"The current position is: {angle_rotated} degrees")
    else:
        print("Failed to get current position")

if __name__ == "__main__":
    main()
