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
        timeout=0,
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

def write_multiple_registers(port, baudrate, slave_address, register_address, values):
    try:
        with open_serial_port(port, baudrate) as ser:
            function_code = 0x10  # Function code for writing multiple registers
            quantity_of_registers = len(values)
            byte_count = 2 * quantity_of_registers
            header = struct.pack('>BBHHB', slave_address, function_code, register_address, quantity_of_registers, byte_count)
            data = b''.join(struct.pack('>H', value) for value in values)
            request = header + data
            print(f"Request (write multiple): {request.hex()}")
            response = send_request(ser, request, 8)
            if response is None:
                return
            print(f"Response (write multiple): {response.hex()}")
            response_slave_address, response_function_code, response_register_address, response_quantity_of_registers = struct.unpack('>BBHH', response[:6])
            if (response_slave_address == slave_address and response_function_code == function_code and
                    response_register_address == register_address and response_quantity_of_registers == quantity_of_registers):
                print(f"Successfully wrote values {values} to registers starting at {register_address} of slave {slave_address}")
            else:
                print("Error: Response does not match the request")
    except Exception as e:
        print(f"Exception: {e}")

def write_single_register(port, baudrate, slave_address, register_address, value):
    try:
        with open_serial_port(port, baudrate) as ser:
            function_code = 0x06  # Function code for writing single register
            request = struct.pack('>BBHH', slave_address, function_code, register_address, value)
            print(f"Request (write single): {request.hex()}")
            response = send_request(ser, request, 8)
            if response is None:
                return
            print(f"Response (write single): {response.hex()}")
            response_slave_address, response_function_code, response_register_address, response_value = struct.unpack('>BBHH', response[:6])
            if (response_slave_address == slave_address and response_function_code == function_code and
                    response_register_address == register_address and response_value == value):
                print(f"Successfully wrote value {value} to register {register_address} of slave {slave_address}")
            else:
                print("Error: Response does not match the request")
    except Exception as e:
        print(f"Exception: {e}")

def read_register(port, baudrate, slave_address, register_address):
    try:
        with open_serial_port(port, baudrate) as ser:
            function_code = 0x03  # Function code for reading holding registers
            request = struct.pack('>BBHH', slave_address, function_code, register_address, 1)
            print(f"Request (read): {request.hex()}")
            response = send_request(ser, request, 7)
            if response is None:
                return
            print(f"Response (read): {response.hex()}")
            if response[1] & 0x80:
                print(f"Modbus exception response: {response[2]}")
                return
            register_value = struct.unpack('>H', response[3:5])[0]
            print(f"Successfully read value {register_value} from register {register_address} of slave {slave_address}")
            return register_value
    except Exception as e:
        print(f"Exception: {e}")

def read_multiple_registers(port, baudrate, slave_address, register_address, count):
    try:
        with open_serial_port(port, baudrate) as ser:
            function_code = 0x03  # Function code for reading holding registers
            request = struct.pack('>BBHH', slave_address, function_code, register_address, count)
            print(f"Request (read multiple): {request.hex()}")
            response = send_request(ser, request, 5 + 2 * count)  # 5 bytes header + 2 bytes per register
            if response is None:
                return
            print(f"Response (read multiple): {response.hex()}")
            if response[1] & 0x80:
                print(f"Modbus exception response: {response[2]}")
                return
            values = struct.unpack('>' + 'H' * count, response[3:3 + 2 * count])
            combined_value = (values[1] << 16) | values[0]
            print(f"Successfully read values {values} from registers starting at {register_address} of slave {slave_address}")
            print(f"Combined value: {combined_value}")
            return combined_value
    except Exception as e:
        print(f"Exception: {e}")

def angle_to_pulses(angle):
    pulses_per_rotation = 100000
    degrees_per_rotation = 360
    pulses = (angle / degrees_per_rotation) * pulses_per_rotation
    return int(pulses)

def split_to_registers(value):
    lower = value & 0xFFFF
    upper = (value >> 16) & 0xFFFF
    return lower, upper

def main():
    port = 'COM3'
    baudrate = 9600
    slave_address = 1

    # Fixed Values - Specification
    gear_ratio = 30
    speed_scale_factor = 10

    # Values to be changed
    angle = 360 * gear_ratio  # Gear ratio = 30:1
    motor_speed = 1000 * speed_scale_factor  # Max Motor Speed : 2000 rpm, Max Output Speed: 2000/30 = 66.6 rpm ~ 70 rpm

    pulses = angle_to_pulses(angle)
    print("Pulses value:", pulses)

    # Convert pulses to two 16-bit registers
    lower, upper = split_to_registers(pulses)

    # Single register read
    read_register(port, baudrate, slave_address, int('0x0606', 16))
    read_register(port, baudrate, slave_address, int('0x0578', 16))
    read_register(port, baudrate, slave_address, int('0x023c', 16))

    # Read multiple registers and combine into single value
    combined_value_start = read_multiple_registers(port, baudrate, slave_address, int('0x0012', 16), 2)
    



    # Single register write - SERVOMOTOR ON
    write_single_register(port, baudrate, slave_address, int('0x023c', 16), 1)

    # Accel/Deccel Function - Value Range Time to Accel/Deccel (ms): 30 to 8000
    write_single_register(port, baudrate, slave_address, int('0x0528', 16), 3000)

    # Multiple register write - SPEED VALUE in RPM
    write_multiple_registers(port, baudrate, slave_address, int('0x0578', 16), [motor_speed, 0])

    # Multiple register write - For setting point to point PR mode
    write_multiple_registers(port, baudrate, slave_address, int('0x0604', 16), [130, 0])

    # Multiple register write - POSITION PULSES from angle conversion
    write_multiple_registers(port, baudrate, slave_address, int('0x0606', 16), [lower, upper])

    # Single register write - TRIGGER SERVO ON
    write_single_register(port, baudrate, slave_address, int('0x050e', 16), 1)

    # Read multiple registers and combine into single value
    time.sleep(6)
    combined_value_end = read_multiple_registers(port, baudrate, slave_address, int('0x0012', 16), 2)

    print(f"Combined value start from registers 0x12 and 0x13: {combined_value_start}")
    print(f"Combined value end from registers 0x12 and 0x13: {combined_value_end}")

    Diff = combined_value_end - combined_value_start
    AngleRotated = (Diff/ 8333.33333333333333333333)    #30,00,000 pulses / 360 degrees = 8333.33333333333333333333
    print(f"The Current position is: {AngleRotated}")



if __name__ == "__main__":
    main()