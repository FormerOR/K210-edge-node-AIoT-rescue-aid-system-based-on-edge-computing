import time
from machine import UART,Timer,PWM
from fpioa_manager import fm
import json
import lcd
import image
import utime

# 映射串口引脚
fm.register(6, fm.fpioa.UART1_RX, force=True)
fm.register(7, fm.fpioa.UART1_TX, force=True)

# 初始化串口
uart = UART(UART.UART1, 115200, read_buf_len=4096)
lcd.init(type=1,freq=15000000,color=lcd.WHITE)
version_num = "version:4.2.0"
lcd.draw_string(0,0,version_num)
lcd.clear()
#PWM通过定时器配置，接到IO9引脚
tim0 = Timer(Timer.TIMER1, Timer.CHANNEL0, mode=Timer.MODE_PWM)

formatted_time = ""
total_its = 0
hit_its = 0
risk_status = False

def get_time(arg = 0):
    # 获取当前时间戳（Unix时间戳，自1970年1月1日以来的秒数）
    current_timestamp = utime.time()
    global formatted_time

    # 如果你的MicroPython固件支持，还可以获取更详细的时间信息
    if hasattr(utime, "localtime"):
        # 将时间戳转换为易读的形式（类似于Python的datetime.localtime()）
        current_time_struct = utime.localtime()
        # 格式化输出
        formatted_time = '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
            current_time_struct[0]+24,  # 年份
            current_time_struct[1]+2,  # 月份
            current_time_struct[2]+24,  # 日
            current_time_struct[3]+16,  # 时
            current_time_struct[4]+16,  # 分
            current_time_struct[5]   # 秒
        )
        #print(formatted_time)

#def print_hit(arg=0):
    #lcd.draw_string(180,20,"Hit Rate:" + str(hit_its) +"/" + str(total_its) ,lcd.GREEN)

def tim_thread(arg=0):
    beep = PWM(tim0, freq=1, duty=10, pin=9)
    beep.enable()
    global risk_status
    lcd.draw_string(180,20,"Hit Rate:" + str(hit_its) +"/" + str(total_its) ,lcd.GREEN)
    if (risk_status):
        beep.freq(1200)
    else:
        beep.disable()
        beep.deinit()

get_time()
tim2 = Timer(Timer.TIMER2, Timer.CHANNEL0, mode=Timer.MODE_PERIODIC, period=1000, callback=get_time)
tim3 = Timer(Timer.TIMER2, Timer.CHANNEL1, mode=Timer.MODE_PERIODIC, period=2000, callback=tim_thread)




# 定义一个字典用于保存解析后的数据
data_dir = {}

data_2_send = {
        "params":{
            "red":0,
            "Humidity":0,
            "temperature":0,
            "people":0,
            "FIRE":0,
            "smoke":0.434,
            "CO":0.5551,
            "Risk":0,
            "exist":0,
            "BreathingRate":0,
            "HeartRate":0,
            "active":0,
            "distance":0,
            "life":0,
            "SignalStrength":0,
            "timestamp": formatted_time
            },
    }

'''
定义火灾风险度函数
'''


def calculate_weight(value):
    # 超出正常范围时的权重因子
    DANGER_WEIGHT_FACTOR = 3
    # 取值不超过1的参数权重为1，超过1的参数权重为3
    weight = 1 if value <= 1 else DANGER_WEIGHT_FACTOR
    return weight


def calculate_risk(data):
    global risk_status
    # 从raw_data提取相关参数
    temperature = data['params']['temperature']
    smoke = data['params']['smoke']
    CO = data['params']['CO']
    humidity = data['params']['Humidity']
    dry = 100 - humidity

    # 将所有参数映射到0-1之间
    temperature_normalized = temperature / 50
    smoke_normalized = smoke / 8
    CO_normalized = CO / 20
    dry_normalized = dry / 80

    # 依次计算参数对风险度的贡献，其中取值不超过1的参数权重为1，超过1的参数权重为3
    tem_contrib = calculate_weight(temperature_normalized) * temperature_normalized
    smoke_contrib = calculate_weight(smoke_normalized) * smoke_normalized
    CO_contrib = calculate_weight(CO_normalized) * CO_normalized
    dry_contrib = calculate_weight(dry_normalized) * dry_normalized

    # 计算风险度
    risk = (tem_contrib + smoke_contrib + CO_contrib + dry_contrib) / 4

    # 如果risk大于1，说明有参数超过了正常范围，风险度为1
    if risk > 1 or data['params']['FIRE'] == 1:
        risk = 1
        risk_status = True
    else:
        risk /= 10
        risk = round(risk,4)

    # 返回风险度
    return risk


'''
END
'''



def send_json_data(timer = None):
    #beep.enable()

    global data_dir
    global data_2_send
    data_2_send["params"]["Risk"] = round(data_2_send["params"]["Risk"],3)
    # 新建一个空字典用于存储转换后的内容
    data_send_ready = {"params": {}}

    # 逐级复制并转换数值为字符串
    for param_key, param_value in data_2_send["params"].items():
        if isinstance(param_value, (int, float)):
            data_send_ready["params"][param_key] = str(param_value)
        else:
            data_send_ready["params"][param_key] = param_value

    # 获取当前时间戳（Unix时间戳，自1970年1月1日以来的秒数）
    current_timestamp = utime.time()

    # 如果你的MicroPython固件支持，还可以获取更详细的时间信息
    if hasattr(utime, "localtime"):
        # 将时间戳转换为易读的形式（类似于Python的datetime.localtime()）
        current_time_struct = utime.localtime()
        # 格式化输出
        formatted_time = '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
            current_time_struct[0]+24,  # 年份
            current_time_struct[1]+2,  # 月份
            current_time_struct[2]+24,  # 日
            current_time_struct[3]+16,  # 时
            current_time_struct[4]+16,  # 分
            current_time_struct[5]   # 秒
        )

    # 将JSON消息转换为字符串
    json_message = json.dumps(data_send_ready)

    # 通过串口发送JSON消息
    uart.write(json_message.encode())

    # 打印发送成功的消息
    #print(str(int(time.time())) + " :=====Send Succeed=====")

    # LCD显示
    lcd.draw_string(0,0,version_num)
    lcd.draw_string(0,20,formatted_time)


    lcd.draw_string(0,220,str(int(time.time())) + "  :  =====Send Succeed=====",lcd.GREEN)
    #beep.freq(800)
    #beep.disable()

# 发送一次JSON数据
send_json_data()

# 每隔一段时间（如10秒）发送一次JSON数据
#定时器0初始化，周期1秒
tim = Timer(Timer.TIMER0, Timer.CHANNEL0, mode=Timer.MODE_PERIODIC, period=3000, callback=send_json_data)



'''
主循环
'''


while True:
    text = uart.read()  # 读取数据
    #print(total_its)
    total_its += 1
    if total_its > 9999:
        total_its = 0
        hit_its = 0

    #print("UART NULL")

    if text:  # 如果读取到了数据
        #beep.enable()
        try:
            received_data = text.decode('utf-8')
        except ValueError:
            print("Decode Error.")
        print("Received Data: ", received_data)  # REPL打印接收到的数据
        #lcd.fill_rectangle(160,80,150,140)


        # 可选：尝试解析接收到的数据为JSON格式
        try:
            parsed_data = json.loads(received_data)
            #print("Parsed JSON Data: ", parsed_data)

            # 遍历云端数据中的"items"部分
            for key, value in parsed_data["items"].items():
                if key in data_2_send["params"]:
                    # 更新本地数据中对应键的值
                    data_2_send["params"][key] = value["value"]

            #计算并修改风险度
            data_2_send["params"]["Risk"] = calculate_risk(data_2_send)
            if (data_2_send["params"]["Risk"] == 1):
                risk_status = True
            else:
                risk_status = False

             #修改fire数据
            if (data_2_send["params"]["FIRE"] > 30):
                data_2_send["params"]["FIRE"] = 1
                data_2_send["params"]["Risk"] = 1
                risk_status = True
            else:
                data_2_send["params"]["FIRE"] = 0
                risk_status = False

            #if (risk_status):
                #beep.freq(1200)
                ##print('beep')
            #else:
                #beep.disable()
                #beep.freq(0)

            # 获取params部分
            params = data_2_send["params"]

            # 设置初始y坐标
            y_start = 20  # 这里可以根据实际屏幕尺寸调整起始位置
            y2_start = 60

            # 遍历params字典
            for i, (key, value) in enumerate(params.items()):


                # 将键值对转换为字符串并在两边添加空格以便美观
                line_text = "%s: %s" % (key, value)

                # 在LCD上绘制字符串
                if(key == "exist" or key == "BreathingRate" or key == "HeartRate" or key == "active" or key == "life" or key == "SignalStrength" or key == "distance"):
                    y2_start += 20
                    lcd.draw_string(160, y2_start, line_text, lcd.BLUE)
                else:
                    # 计算当前行的y坐标（例如每行间隔20像素）
                    y_start += 20
                    lcd.draw_string(0, y_start, line_text, lcd.WHITE)
            hit_its += 1

            #print('\n')
        except ValueError:
            print("Invalid JSON format received.")

        #beep.disable()
        lcd.draw_string(120,0,str(int(time.time())) + ":***Had Receviced***",lcd.GREEN)

        #utime.sleep_ms(1000)
    else:
        lcd.draw_string(120,0,str(int(time.time())) + ":***Not Receviced***",lcd.RED)


'''
主循环 END
'''

