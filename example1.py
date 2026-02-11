import time
import numpy as np
import bcmcloud, threading
from PIL import Image
import colorsys

def encode_image_to_custom_format(image_path):
    """
    将图片编码为自定义格式
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        [图片高度, 图片宽度, 图片数据列表]
        图片数据列表中的每个字符串包含126个字符（除最后一个可能不足）
    """
    try:
        # 打开图片并转换为RGB模式
        img = Image.open(image_path).convert('RGB')
        width, height = img.size
        
        # 使用numpy获取像素数据，避免getdata的弃用警告，得到形状为(height*width, 3)的数组
        pixels = np.array(img).reshape(-1, 3)
        
        # 定义编码字符集
        ones_digits = "0123456789ABCDEF"  # 个位字符集（0-15）
        tens_digits = "0123456789ABCDEFGHIJKLMNO"  # 十位字符集（0-24）
        
        def value_to_custom_hex(value, max_val):
            """
            将值转换为自定义HEX编码
            
            Args:
                value: 要编码的值
                max_val: 最大值（用于限制范围）
                
            Returns:
                2位自定义HEX字符串
            """
            # 确保值在有效范围内并转为整数
            value = max(0, min(int(round(value)), max_val))
            
            # 计算个位和十位
            ones = value % 16
            tens = value // 16
            
            # 确保十位不超过24（tens_digits的范围）
            tens = min(tens, 24)
            
            # 转换为自定义HEX
            return f"{tens_digits[tens]}{ones_digits[ones]}"
        
        # 编码所有像素
        encoded_pixels = []
        for r, g, b in pixels:
            # 转换为HSL（colorsys返回的H在0-1，S和L在0-1）
            h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
            
            # 转换为目标范围
            h_val = round(h * 360) % 360  # 0-360
            s_val = round(s * 100)  # 0-100
            l_val = round(l * 100)  # 0-100
            
            # 编码为自定义HEX
            h_hex = value_to_custom_hex(h_val, 360)
            s_hex = value_to_custom_hex(s_val, 100)
            l_hex = value_to_custom_hex(l_val, 100)
            
            # 拼接为6位字符串，顺序改为H、S、L，符合标准HSL解析顺序
            encoded_pixels.append(f"{h_hex}{s_hex}{l_hex}")
        
        encoded_str = "".join(encoded_pixels)
        # 每126个字符（21个像素）分组
        group_size = 126  # 21像素 * 6字符
        encoded_groups = [encoded_str[i:i+group_size] for i in range(0, len(encoded_str), group_size)]
        
        return [int(height), int(width), encoded_groups]
        
    except Exception as e:
        print(f"处理图片时出错: {e}")
        return None

def work():
    while not bcmcloud_worker.ready:#等待准备就绪
        time.sleep(1)

    """
    server_state 变量:
    1: 服务器就绪响应
    2: 客户端就绪响应
    3: 服务器发送完成
    """
    bcmcloud_worker.var_upd("server_state", 1)
    result = encode_image_to_custom_format("./send.png")
    hex_chunks = result[2]
    h = result[0]
    w = result[1]

    while not bcmcloud_worker.cloud_vars["server_state"] == 2:  # 等待客户端准备就绪
        bcmcloud_worker.var_upd("server_state", 1)
        time.sleep(2)

    bcmcloud_worker.var_upd("hex_len", len(hex_chunks))  # 图片数据列表项数
    bcmcloud_worker.var_upd("total_x", w)  # 图片宽
    bcmcloud_worker.var_upd("total_y", h)  # 图片长
    bcmcloud_worker.var_upd("server_state", 1)

    while not bcmcloud_worker.cloud_vars["server_state"] == 2:
        time.sleep(0.1)

    begin_index = 0
    while len(hex_chunks) > begin_index:  # 发送图片数据
        for i in range(1, min(len(hex_chunks)-begin_index+1, 201)):
            bcmcloud_worker.list_replace("img_data", i, hex_chunks[begin_index + i - 1])

        bcmcloud_worker.var_upd("server_state", 1)

        while not bcmcloud_worker.cloud_vars["server_state"] == 2:
            time.sleep(0.1)

        begin_index += 200  # 服务器一次发送200项
    
    bcmcloud_worker.var_upd("server_state", 3)  # 图片数据发送完成

    while not bcmcloud_worker.cloud_vars["server_state"] == 2:  # 等待客户端回应
        time.sleep(0.1)

    bcmcloud_worker.var_upd("server_state", 1)

    print("发送完成。")

    threading.Thread(target=work).start()  # 重新启动线程以便下次再次发送图片


config = \
{
    "phone_number": "18508106180",
    "password": "Yhy3370955",
    "work": "304104073"
}
bcmcloud_worker = bcmcloud.codemao_cloud(config)
threading.Thread(target=work).start()
bcmcloud_worker.run()